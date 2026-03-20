from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import json
import os
from google import genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SECURITY FIX: Use Environment Variables ---
# On Render, you will add a variable named GEMINI_API_KEY
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "your-local-test-key-here")
client = genai.Client(api_key=GEMINI_KEY)

HISTORY_FILE = "chat_history.json"

class ChatMessage(BaseModel):
    role: str
    text: str

class AIRequest(BaseModel):
    prompt: str
    history: List[ChatMessage] = []

def save_to_json(user_text, ai_text):
    data = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
        except:
            data = []
    
    data.append({"role": "user", "text": user_text})
    data.append({"role": "ai", "text": ai_text})
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.get("/")
def home():
    return {"message": "API is running! Use /api/generate for chat."}

@app.post("/api/generate")
def generate_ai_response(request: AIRequest):
    try:
        formatted_contents = []
        for msg in request.history:
            gemini_role = "model" if msg.role == "ai" else "user"
            formatted_contents.append({"role": gemini_role, "parts": [{"text": msg.text}]})
        
        formatted_contents.append({"role": "user", "parts": [{"text": request.prompt}]})

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=formatted_contents,
        )
        
        ai_response_text = response.text
        save_to_json(request.prompt, ai_response_text)

        return {
            "status": "success",
            "ai_response": ai_response_text
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- DEPLOYMENT FIX: Helping Render find the port ---
if __name__ == "__main__":
    import uvicorn
    # Render provides a PORT environment variable automatically
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)