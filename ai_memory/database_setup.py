# Modified: database_setup.py (no changes needed, but re-run if DB issues)
import sqlite3
import os

db_path = '/storage/emulated/0/Documents/Indus AI Project/ai_memory/indus_ai.db'
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# --- Existing tables ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS knowledge_base (id INTEGER PRIMARY KEY, question TEXT UNIQUE, answer TEXT, learned_from TEXT)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_feedback (id INTEGER PRIMARY KEY, question TEXT, ai_response TEXT, feedback TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
''')

# Modified user_interactions to include conversation_id
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_interactions (
    id INTEGER PRIMARY KEY, 
    conversation_id INTEGER, 
    user_input TEXT, 
    ai_response TEXT, 
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# New table for conversations
cursor.execute('''
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY, 
    title TEXT, 
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()
print("Database setup completed. Added conversations table and modified user_interactions.")