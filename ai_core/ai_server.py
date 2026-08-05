import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from ai_engine import AIEngine

app = Flask(__name__)
CORS(app)

# ================= DYNAMIC PATH CONFIGURATION =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Dynamically locate frontend and database
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
DB_PATH = os.path.join(PROJECT_ROOT, "ai_memory", "indus_ai.db")

# Safety Check: Print paths to console on startup
print(f"[SERVER] Frontend Directory: {FRONTEND_DIR}")
print(f"[SERVER] Database Path: {DB_PATH}")
# ==============================================================

ai_engine = AIEngine()

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static_files(path):
    return send_from_directory(FRONTEND_DIR, path)

@app.route('/ask', methods=['POST'])
def ask_ai():
    try:
        data = request.get_json()
        user_input = data.get("user_input", "")
        history = data.get("history", [])
        conversation_id = data.get("conversation_id", None)
        context_entity = data.get("context_entity", None)

        if not user_input:
            return jsonify({"error": "No input provided"}), 400

        ai_reply, updated_history, new_context_entity = ai_engine.get_ai_response(
            user_input, 
            history, 
            context_entity
        )

        # Save interaction to DB if conversation_id is provided
        if conversation_id:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_interactions (conversation_id, user_input, ai_response) VALUES (?, ?, ?)",
                (conversation_id, user_input, ai_reply)
            )
            conn.commit()
            conn.close()

        return jsonify({
            "response": ai_reply or "I'm sorry, I couldn't generate a response.",
            "history": updated_history,
            "context_entity": new_context_entity
        })

    except Exception as e:
        print(f"[ERROR] in /ask: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/feedback', methods=['POST'])
def handle_feedback():
    data = request.get_json()
    question = data.get("question", "").strip()
    ai_response = data.get("ai_response", "").strip()
    feedback = data.get("feedback", "").strip()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_feedback (question, ai_response, feedback) VALUES (?, ?, ?)",
            (question, ai_response, feedback)
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[ERROR] in /feedback: {e}")
        return jsonify({"error": str(e)}), 500

# New endpoint: Create new conversation
@app.route('/new_chat', methods=['POST'])
def new_chat():
    try:
        data = request.get_json()
        title = data.get("title", "New Chat")  # Default title, can be updated later
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"conversation_id": conversation_id, "title": title})
    except Exception as e:
        print(f"[ERROR] in /new_chat: {e}")
        return jsonify({"error": str(e)}), 500

# New endpoint: Get list of conversations
@app.route('/chats', methods=['GET'])
def get_chats():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, created_at FROM conversations ORDER BY created_at DESC")
        chats = cursor.fetchall()
        conn.close()
        chat_list = [{"id": row[0], "title": row[1], "created_at": row[2]} for row in chats]
        return jsonify({"chats": chat_list})
    except Exception as e:
        print(f"[ERROR] in /chats: {e}")
        return jsonify({"error": str(e)}), 500

# New endpoint: Get history for a conversation
@app.route('/chat/<int:conversation_id>', methods=['GET'])
def get_chat_history(conversation_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_input, ai_response FROM user_interactions WHERE conversation_id = ? ORDER BY timestamp ASC",
            (conversation_id,)
        )
        interactions = cursor.fetchall()
        conn.close()
        history = []
        for user_input, ai_response in interactions:
            if user_input:
                history.append({"role": "user", "content": user_input})
            if ai_response:
                history.append({"role": "assistant", "content": ai_response})
        return jsonify({"history": history})
    except Exception as e:
        print(f"[ERROR] in /chat/{conversation_id}: {e}")
        return jsonify({"error": str(e)}), 500

# New endpoint: Rename conversation
@app.route('/rename_chat', methods=['POST'])
def rename_chat():
    try:
        data = request.get_json()
        conversation_id = data.get("conversation_id")
        new_title = data.get("new_title")
        if not conversation_id or not new_title:
            return jsonify({"error": "Missing parameters"}), 400
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conversation_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[ERROR] in /rename_chat: {e}")
        return jsonify({"error": str(e)}), 500

# New endpoint: Delete conversation
@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    try:
        data = request.get_json()
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            return jsonify({"error": "Missing conversation_id"}), 400
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_interactions WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[ERROR] in /delete_chat: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print(f"[SERVER] Indus AI Server (Flask) running at http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)