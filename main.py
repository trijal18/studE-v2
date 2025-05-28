from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os

from modules.generate_mcqs import generate_summary, generate_questions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Store sessions in-memory
sessions = {}

# Templates and static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload/", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed.")

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
        "summary": summary,
        "index": 0,
        "score": 0
    }

    # Redirect to summary page
    response = RedirectResponse(url=f"/summary/{file_id}", status_code=303)
    return response

@app.get("/summary/{session_id}", response_class=HTMLResponse)
def summary_page(request: Request, session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return templates.TemplateResponse("summary.html", {
        "request": request,
        "session_id": session_id,
        "summary": session["summary"]
    })

@app.get("/questions/{session_id}", response_class=HTMLResponse)
def show_question(request: Request, session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    index = session["index"]
    if index >= len(session["questions"]):
        return templates.TemplateResponse("questions.html", {
            "request": request,
            "completed": True,
            "score": session["score"],
            "total": len(session["questions"]),
            "session_id": session_id
        })

    question = session["questions"][index]
    return templates.TemplateResponse("questions.html", {
        "request": request,
        "question": question["question"],
        "options": question["options"],
        "index": index + 1,
        "completed": False,
        "session_id": session_id
    })

@app.post("/answer/{session_id}", response_class=HTMLResponse)
async def submit_answer(request: Request, session_id: str, selected_option: str = Form(...)):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    index = session["index"]
    if index >= len(session["questions"]):
        return RedirectResponse(url=f"/questions/{session_id}", status_code=303)

    correct_answer = session["questions"][index]["answer"].strip()
    is_correct = selected_option.strip() == correct_answer

    if is_correct:
        session["score"] += 1

    session["index"] += 1

    return templates.TemplateResponse("questions.html", {
        "request": request,
        "feedback": "Correct!" if is_correct else f"Wrong. Correct answer: {correct_answer}",
        "next_url": f"/questions/{session_id}",
        "completed": session["index"] >= len(session["questions"]),
        "score": session["score"],
        "total": len(session["questions"]),
        "session_id": session_id
    })
