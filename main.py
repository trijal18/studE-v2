from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import os
from modules.generate_mcqs import generate_summary, generate_questions

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage
sessions = {}

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    try:
        questions = generate_questions(file_path)
        summary = generate_summary(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate content: {e}")

    sessions[file_id] = {
        "questions": questions,
        "summary": summary
    }

    return {"session_id": file_id, "summary": summary}


@app.get("/questions/{session_id}")
def get_all_questions(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "questions": session["questions"],
        # "summary": session["summary"],
        "total": len(session["questions"])
    }

@app.get("/")
def root():
    return {"message": "MCQ FastAPI Quiz App is running."}
