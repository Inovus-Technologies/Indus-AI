import sqlite3
import os
import time
from datetime import datetime
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import torch
import torch.nn as nn
import json
from .my_transformers import CustomTransformer

# ================= DYNAMIC PATH CONFIGURATION =================
# Get the directory where this script (ai_engine.py) is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Go up one level to the main Project Folder
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Define the paths relative to the Project Root
MEMORY_DIR = os.path.join(PROJECT_ROOT, 'ai_memory')

# Create ai_memory folder if it doesn't exist (prevents crashes on new laptops)
os.makedirs(MEMORY_DIR, exist_ok=True)

# Set the final file paths
db_path = os.path.join(MEMORY_DIR, 'indus_ai.db')
model_path = os.path.join(MEMORY_DIR, 'model.pt')
vocab_path = os.path.join(MEMORY_DIR, 'vocab.json')
# ==============================================================


# ================= PYTORCH TRANSFORMER ===================
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=500):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))
        pe = torch.zeros(1, max_len, d_model)  # batch_first=True
        pe[0, :, 0::2] = torch.sin(position * div_term)
        pe[0, :, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]

class DecoderOnlyTransformer(nn.Module):
    def __init__(self, vocab_size, d_model=128, nhead=4, num_layers=2, dim_feedforward=256, max_seq_len=512):  # Increased max_seq_len
        super().__init__()
        self.d_model = d_model
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.pos_encoder = PositionalEncoding(d_model, max_seq_len)
        encoder_layer = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers)
        self.fc_out = nn.Linear(d_model, vocab_size)
        self.device = torch.device('cpu')  # CPU for Android compatibility
        self.to(self.device)

    def forward(self, src, src_mask=None):
        src = self.embedding(src) * np.sqrt(self.d_model)
        src = self.pos_encoder(src)
        output = self.transformer_encoder(src, mask=src_mask)
        return self.fc_out(output)

    def generate_square_subsequent_mask(self, sz):
        mask = torch.triu(torch.ones(sz, sz) * float('-inf'), diagonal=1)
        mask = mask.to(self.device)
        return mask

    def generate(self, prompt_tokens, max_length=20, temperature=1.0, beam_width=3):
        self.eval()
        prompt_tokens = torch.tensor([prompt_tokens], device=self.device)  # [1, seq_len]
        sequences = [(prompt_tokens, 0.0)]  # (tensor [1, len], log_prob)
        with torch.no_grad():
            for _ in range(max_length):
                all_candidates = []
                for seq_tensor, score in sequences:
                    mask = self.generate_square_subsequent_mask(seq_tensor.size(1))
                    logits = self.forward(seq_tensor, mask)[:, -1, :] / temperature
                    probs = torch.softmax(logits, dim=-1)
                    topk_probs, topk_indices = torch.topk(probs, beam_width, dim=-1)
                    for i in range(beam_width):
                        next_token = topk_indices[0, i].unsqueeze(0).unsqueeze(0)  # [1,1]
                        next_seq = torch.cat([seq_tensor, next_token], dim=1)
                        next_score = score + torch.log(topk_probs[0, i]).item()
                        all_candidates.append((next_seq, next_score))
                sequences = sorted(all_candidates, key=lambda x: x[1], reverse=True)[:beam_width]
                if sequences[0][0][0, -1].item() == self.eos_token_id:
                    break
            best_seq = sequences[0][0].squeeze(0).tolist()  # list of tokens
        return best_seq[len(prompt_tokens.squeeze(0).tolist()):]  # generated part

# ================ HIGH-PERFORMANCE AI ENGINE ================
class AIEngine:
    def __init__(self):
        print("[AI Engine] Initializing...")
        start_time = time.time()

        # Load DB data (for TF-IDF)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer FROM knowledge_base")
        results = cursor.fetchall()

        if not results:
            print("[AI Engine] WARNING: Knowledge base is empty.")
            self.db_questions = []
            self.db_answers = []
            self.vectorizer = None
            self.db_vectors = None
            self.transformer = None
            conn.close()
            return

        self.db_questions = [row[0] for row in results]
        self.db_answers = [row[1] for row in results]
        print(f"[AI Engine] Loaded {len(self.db_questions)} Q/A pairs from the database.")

        # Build TF-IDF
        print("[AI Engine] Building TF-IDF model...")
        self.vectorizer = TfidfVectorizer()
        self.db_vectors = self.vectorizer.fit_transform(self.db_questions)

        # Load CustomTransformer from files in ai_memory
        print("[AI Engine] Handling CustomTransformer model...")

        all_text = ' '.join(self.db_questions + self.db_answers).split()
        self.vocab = {word: i for i, word in enumerate(set(all_text))}
        self.vocab['<EOS>'] = len(self.vocab)
        vocab_size = len(self.vocab)
        self.inv_vocab = {i: word for word, i in self.vocab.items()}

        self.transformer = CustomTransformer(vocab_size)
        self.transformer.eos_token_id = self.vocab['<EOS>']

        if os.path.exists(vocab_path) and os.path.exists(model_path):
            with open(vocab_path, 'r') as f:
                loaded_vocab = json.load(f)
            if loaded_vocab == self.vocab:
                loaded_state = torch.load(model_path, map_location='cpu')
                self.transformer.load_state_dict(loaded_state)
                print("[CustomTransformer] Loaded saved weights from files.")
            else:
                print("[WARNING] Vocab mismatch detected (possible new data added); skipping model load. Run train.py to update.")
                self.transformer = None  # Don't load on mismatch
        else:
            print("[WARNING] No saved files in ai_memory; generation disabled. Run train.py first.")
            self.transformer = None

        conn.close()
        end_time = time.time()
        print(f"[AI Engine] Initialization complete! Model built in {end_time - start_time:.2f} seconds.")

    def _extract_entity(self, text):
        words = text.split()
        entities = [word.strip(',.?') for i, word in enumerate(words) if i > 0 and word[0].isupper()]
        if not entities and len(words) > 0 and words[0][0].isupper():
            if len(words) == 1:
                 entities = [words[0].strip(',.?')]
        return " ".join(entities) if entities else None

    def get_ai_response(self, user_input, history, context_entity=None):
        history.append({"role": "user", "content": user_input})
        
        # --- Start of Tool Use Logic ---
        # First, check if the input triggers a real-time tool
        time_triggers = ['time', 'date', 'day', 'month', 'year']
        if any(trigger in user_input.lower() for trigger in time_triggers):
            now = datetime.now()
            # More specific checks
            if 'date' in user_input.lower():
                response = now.strftime("Today's date is %A, %B %d, %Y.")
            elif 'time' in user_input.lower():
                response = now.strftime("The current time is %I:%M %p.")
            else:
                response = now.strftime("It is %A, %B %d, %Y, and the time is %I:%M %p.")
            
            history.append({"role": "assistant", "content": response})
            return response, history, None # Return immediately after using the tool

        # --- If no tool was used, proceed with database search ---
        rewritten_input = user_input
        pronouns = ['he', 'she', 'it', 'they', 'his', 'her', 'its', 'their', 'him']
        if context_entity and any(pronoun in user_input.lower().split() for pronoun in pronouns):
            for pronoun in pronouns:
                if pronoun in rewritten_input.lower():
                    rewritten_input = rewritten_input.lower().replace(pronoun, context_entity)
                    print(f"[CONTEXT] Rewrote query to: '{rewritten_input}'")
                    break
        
        search_input = rewritten_input
        best_match = None
        new_context_entity = None

        # --- The Fast Search ---
        # Check if the model was successfully built
        if self.vectorizer is None or len(self.db_questions) == 0:
            ai_response = "I'm sorry, my knowledge base is empty or could not be loaded."
        else:
            user_vector = self.vectorizer.transform([search_input])
            similarities = cosine_similarity(user_vector, self.db_vectors)
            most_similar_idx = np.argmax(similarities)
            highest_similarity = similarities[0, most_similar_idx]

            SIMILARITY_THRESHOLD = 0.5
            if highest_similarity > SIMILARITY_THRESHOLD:
                best_match = self.db_answers[most_similar_idx]
                matched_question = self.db_questions[most_similar_idx]
                new_context_entity = self._extract_entity(matched_question)
                print(f"[INFO] Found match with score {highest_similarity:.2f}.")

        if best_match:
            ai_response = best_match
        else:
            # Fallback to CustomTransformer Generation
            if self.transformer:
                print("[INFO] No TF-IDF match; generating with CustomTransformer.")
                prompt = f"Question: {search_input} Answer:"
                prompt_tokens = np.array([self.vocab.get(word, 0) for word in prompt.split()])
                generated_tokens = self.transformer.generate(prompt_tokens)
                generated_text = ' '.join([self.inv_vocab.get(t, '<UNK>') for t in generated_tokens if t != self.transformer.eos_token_id])
                ai_response = generated_text or "I'm generating a response, but my training is limited."
            else:
                ai_response = "I'm sorry, I don't have information on that topic yet."
            new_context_entity = None 

        history.append({"role": "assistant", "content": ai_response})
        return ai_response, history, new_context_entity

# ================ LEARNING FUNCTION ================
def learn_new_knowledge(user_input, user_answer, learned_from="importer"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    normalized_input = user_input.strip().lower()
    cursor.execute("SELECT 1 FROM knowledge_base WHERE LOWER(question) = ?", (normalized_input,))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("INSERT INTO knowledge_base (question, answer, learned_from) VALUES (?, ?, ?)",
                       (user_input.strip(), user_answer.strip(), learned_from))
        conn.commit()
        print(f"Learned: {user_input}")
    else:
        print(f"Already knew: {user_input}")
    conn.close()