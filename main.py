from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse  # <-- Added this!
from pydantic import BaseModel
from typing import List
import os
import sqlite3
from google import genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Database
def init_db():
    conn = sqlite3.connect('chat_memory.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            text TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Database Saving Function
def save_to_db(role, text):
    conn = sqlite3.connect('chat_memory.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (role, text) VALUES (?, ?)', (role, text))
    conn.commit()
    conn.close()

# Load Company Data 
def load_knowledge():
    if os.path.exists("knowledge.txt"):
        with open("knowledge.txt", "r") as f:
            return f.read()
    return "No specific company data provided."

COMPANY_KNOWLEDGE = load_knowledge()

# --- SECURITY FIX: No hardcoded key fallback ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("WARNING: No GEMINI_API_KEY found in environment variables!")

client = genai.Client(api_key=GEMINI_KEY)

SYSTEM_PROMPT = f"""
You are an expert AI Assistant for our company. 
Use the following Company Knowledge to answer user questions:
{COMPANY_KNOWLEDGE}
"""

class ChatMessage(BaseModel):
    role: str
    text: str

class AIRequest(BaseModel):
    prompt: str
    history: List[ChatMessage] = []

# --- NEW: Serve the Web Interface ---
@app.get("/")
def serve_ui():
    """This tells the server to display index.html when you visit the main URL"""
    # Ensure the file exists before trying to serve it
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html not found"}

@app.post("/api/generate")
def generate_ai_response(request: AIRequest):
    try:
        formatted_contents = [
            {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
            {"role": "model", "parts": [{"text": "Understood."}]}
        ]
        
        for msg in request.history:
            role = "model" if msg.role == "ai" else "user"
            formatted_contents.append({"role": role, "parts": [{"text": msg.text}]})
        
        formatted_contents.append({"role": "user", "parts": [{"text": request.prompt}]})

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=formatted_contents,
        )
        
        # Save the interaction directly to the SQL Database!
        save_to_db("user", request.prompt)
        save_to_db("ai", response.text)

        return {"status": "success", "ai_response": response.text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
def get_chat_history():
    """Fetches all past messages from the SQLite database."""
    try:
        conn = sqlite3.connect('chat_memory.db')
        cursor = conn.cursor()
        cursor.execute('SELECT role, text FROM messages ORDER BY id ASC')
        rows = cursor.fetchall()
        conn.close()
        
        history_list = [{"role": row[0], "text": row[1]} for row in rows]
        return {"status": "success", "history": history_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear")
def clear_chat_history():
    """Wipes the SQLite database clean."""
    try:
        conn = sqlite3.connect('chat_memory.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages') 
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Memory completely wiped."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)