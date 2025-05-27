from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uuid
import os
# import project.modules.pdf_to_text as pdf_to_text
from modules.generate_mcqs import generate_summary, generate_questions

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global session store
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
        summary = generate_summary(file_path)
        questions=generate_questions(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate content: {e}")

    sessions[file_id] = {
        "questions": questions,
        "summary": summary,
        "current_index": 0,
        "score": 0
    }

    return {"session_id": file_id, "summary": summary}

@app.get("/question/{session_id}")
def get_question(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    index = session["current_index"]
    questions = session["questions"]

    if index >= len(questions):
        return {
            "message": "Quiz completed",
            "score": session["score"],
            "total": len(questions)
        }

    question_data = questions[index]
    return {
        "question": question_data["question"],
        "options": question_data["options"]
    }

class AnswerSubmission(BaseModel):
    selected_option: str

@app.post("/answer/{session_id}")
def submit_answer(session_id: str, submission: AnswerSubmission):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    index = session["current_index"]
    questions = session["questions"]

    if index >= len(questions):
        return {"message": "Quiz already completed"}

    selected_option = submission.selected_option.strip()
    correct_answer = questions[index]["answer"].strip()

    if selected_option not in [opt.strip() for opt in questions[index]["options"]]:
        raise HTTPException(status_code=400, detail="Invalid option selected.")

    is_correct = selected_option == correct_answer
    if is_correct:
        session["score"] += 1

    session["current_index"] += 1

    return {
        "correct": is_correct,
        "correct_answer": correct_answer,
        "next_question_index": session["current_index"],
        "quiz_completed": session["current_index"] >= len(questions)
    }

@app.get("/")
def root():
    return {"message": "MCQ FastAPI Quiz App is running."}
