from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import os
from modules import genrate_mcqs
# from modules.genrate_mcqs import genrate_content

# import genrate_mcqs

app = FastAPI()

# CORS (for frontend interaction)
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
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    try:
        questions, summary = genrate_mcqs.genrate_content(file_path)
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
        return {"message": "Quiz completed", "score": session["score"], "total": len(questions)}

    question_data = questions[index]
    return {"question": question_data["question"], "options": question_data["options"]}

@app.post("/answer/{session_id}")
def submit_answer(session_id: str, selected_option: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    index = session["current_index"]
    questions = session["questions"]

    if index >= len(questions):
        return {"message": "Quiz already completed"}

    correct_answer = questions[index]["answer"]
    is_correct = selected_option.strip() == correct_answer.strip()
    
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
