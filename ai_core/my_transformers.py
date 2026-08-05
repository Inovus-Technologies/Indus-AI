import torch
import torch.nn as nn
import torch.optim as optim
import math
import numpy as np
from torch.utils.data import DataLoader, TensorDataset

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=512):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        return x + self.pe[:, :x.size(1)]

class MultiHeadSelfAttention(nn.Module):
    def __init__(self, d_model, num_heads):
        super().__init__()
        self.num_heads = num_heads
        self.d_model = d_model
        self.head_dim = d_model // num_heads

        self.query = nn.Linear(d_model, d_model)
        self.key = nn.Linear(d_model, d_model)
        self.value = nn.Linear(d_model, d_model)
        self.fc_out = nn.Linear(d_model, d_model)

    def forward(self, x, mask=None):
        Q = self.query(x).view(x.shape[0], -1, self.num_heads, self.head_dim).permute(0, 2, 1, 3)
        K = self.key(x).view(x.shape[0], -1, self.num_heads, self.head_dim).permute(0, 2, 1, 3)
        V = self.value(x).view(x.shape[0], -1, self.num_heads, self.head_dim).permute(0, 2, 1, 3)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.head_dim)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))
        attn = torch.softmax(scores, dim=-1)
        out = torch.matmul(attn, V).permute(0, 2, 1, 3).contiguous().view(x.shape[0], -1, self.d_model)
        return self.fc_out(out)

class FeedForward(nn.Module):
    def __init__(self, d_model, d_ff=512, dropout=0.1):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff)
        self.dropout = nn.Dropout(dropout)
        self.linear2 = nn.Linear(d_ff, d_model)

    def forward(self, x):
        x = self.dropout(torch.relu(self.linear1(x)))
        x = self.linear2(x)
        return x

class DecoderLayer(nn.Module):
    def __init__(self, d_model, num_heads, d_ff=512, dropout=0.1):
        super().__init__()
        self.self_attn = MultiHeadSelfAttention(d_model, num_heads)
        self.feed_forward = FeedForward(d_model, d_ff, dropout)
        self.layernorm1 = nn.LayerNorm(d_model)
        self.layernorm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        attn_output = self.self_attn(x, mask)
        x = self.layernorm1(x + self.dropout(attn_output))
        ff_output = self.feed_forward(x)
        x = self.layernorm2(x + self.dropout(ff_output))
        return x

class CustomTransformer(nn.Module):
    def __init__(self, vocab_size, d_model=128, num_heads=4, num_layers=2, d_ff=256, max_seq_len=512, dropout=0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.pos_encoding = PositionalEncoding(d_model, max_len=max_seq_len)
        self.layers = nn.ModuleList([DecoderLayer(d_model, num_heads, d_ff, dropout) for _ in range(num_layers)])
        self.fc_out = nn.Linear(d_model, vocab_size)
        self.dropout = nn.Dropout(dropout)

    def generate_mask(self, size):
        mask = torch.tril(torch.ones(size, size)).unsqueeze(0).unsqueeze(0)
        return mask

    def forward(self, x):
        seq_len = x.size(1)
        mask = self.generate_mask(seq_len)
        x = self.embedding(x)
        x = self.pos_encoding(x)
        x = self.dropout(x)
        for layer in self.layers:
            x = layer(x, mask)
        return self.fc_out(x)

    def generate(self, prompt_tokens, max_length=50, temperature=0.8, top_k=50):
        self.eval()
        output = prompt_tokens
        with torch.no_grad():
            for _ in range(max_length):
                logits = self.forward(torch.tensor([output]))[:, -1, :]
                logits = logits / temperature
                probs = torch.softmax(logits, dim=-1)
                topk_probs, topk_indices = torch.topk(probs, top_k, dim=-1)
                next_token = torch.multinomial(topk_probs, num_samples=1).squeeze(1)
                next_token = topk_indices.gather(-1, next_token.unsqueeze(-1)).squeeze(-1)
                output = np.append(output, next_token.item())
                if next_token.item() == 0:  # Assume 0 is EOS
                    break
        return output
        