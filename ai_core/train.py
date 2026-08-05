import sqlite3
import os
import time
import numpy as np
import torch
import torch.optim as optim
import torch.nn as nn
import json
import random
from torch.utils.data import DataLoader, TensorDataset
from my_transformers import CustomTransformer
from ai_engine import learn_new_knowledge

# ================= DYNAMIC PATH CONFIGURATION =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

MEMORY_DIR = os.path.join(PROJECT_ROOT, 'ai_memory')
DATA_DIR = os.path.join(PROJECT_ROOT, 'learning_data')

# Ensure memory directory exists
os.makedirs(MEMORY_DIR, exist_ok=True)

# Set file paths
db_path = os.path.join(MEMORY_DIR, 'indus_ai.db')
knowledge_path = os.path.join(DATA_DIR, 'knowledge.json')
model_path = os.path.join(MEMORY_DIR, 'model.pt')
vocab_path = os.path.join(MEMORY_DIR, 'vocab.json')
# ==============================================================


def train_model():
    print("[Training] Starting...")
    start_time = time.time()

    # Load data from learning_data folder (JSON file)
    if not os.path.exists(knowledge_path):
        print("[Training] WARNING: knowledge.json not found in learning_data.")
        return

    with open(knowledge_path, 'r') as f:
        results = json.load(f)

    if not results:
        print("[Training] WARNING: No data in knowledge.json.")
        return

    db_questions = [row['question'] for row in results]
    db_answers = [row['answer'] for row in results]
    print(f"[Training] Loaded {len(db_questions)} Q/A pairs from learning_data/knowledge.json.")

    # Sync the loaded data to the database (insert if not exists)
    print("[Training] Syncing data to database...")
    for q, a in zip(db_questions, db_answers):
        learn_new_knowledge(q, a, "learning_data")
    print("[Training] Data sync complete.")

    # Build vocab
    all_text = ' '.join(db_questions + db_answers).split()
    vocab = {word: i for i, word in enumerate(set(all_text))}
    vocab['<EOS>'] = len(vocab)
    vocab_size = len(vocab)
    inv_vocab = {i: word for word, i in vocab.items()}

    # Init model
    transformer = CustomTransformer(vocab_size)
    transformer.eos_token_id = vocab['<EOS>']

    # Prepare sequences
    sequences = []
    for q, a in zip(db_questions, db_answers):
        seq_str = f"Question: {q} Answer: {a} <EOS>"
        seq = [vocab.get(word, 0) for word in seq_str.split()]
        sequences.append(seq)

    # Sample/truncate
    train_subset = random.sample(sequences, min(10000, len(sequences)))
    print(f"[Training] Sampling {len(train_subset)} sequences.")
    TRUNCATE_LEN = 512
    train_subset = [s[:TRUNCATE_LEN] if len(s) > TRUNCATE_LEN else s for s in train_subset]

    # Pad
    max_len = min(TRUNCATE_LEN, max(len(s) for s in train_subset))
    padded_inputs = []
    padded_targets = []
    for seq in train_subset:
        pad_len = max_len - len(seq) + 1
        padded_input = seq[:-1] + [0] * pad_len
        padded_target = seq[1:] + [0] * pad_len
        padded_inputs.append(padded_input[:max_len])
        padded_targets.append(padded_target[:max_len])

    inputs_tensor = torch.tensor(padded_inputs)
    targets_tensor = torch.tensor(padded_targets)
    dataset = TensorDataset(inputs_tensor, targets_tensor)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    optimizer = optim.Adam(transformer.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss(ignore_index=0)

    print("[Training] Training model...")
    for epoch in range(15):  # 15 epochs as requested
        total_loss = 0
        for batch_inputs, batch_targets in dataloader:
            output = transformer(batch_inputs)
            loss = criterion(output.view(-1, vocab_size), batch_targets.view(-1))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1}: Avg Loss = {total_loss / len(dataloader):.4f}")

    # Save model weights to .pt file in ai_memory
    torch.save(transformer.state_dict(), model_path)
    print(f"[Training] Model weights saved to {model_path}.")

    # Save vocab to .json file in ai_memory
    with open(vocab_path, 'w') as f:
        json.dump(vocab, f)
    print(f"[Training] Vocab saved to {vocab_path}.")

    print("[Training] Complete!")
    print(f"[Training] Took {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    train_model()