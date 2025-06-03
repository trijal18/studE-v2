import uuid, os, bcrypt
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import EmailStr
from pymongo import MongoClient
from dotenv import load_dotenv
from modules.generate_mcqs import generate_summary, generate_questions

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# MongoDB setup
load_dotenv()
MONGO_URL = os.getenv("MONGO_UR")
client = MongoClient(MONGO_URL)
db = client.mcqapp
users_col = db.users
pdfs_col = db.pdfs
scores_col = db.scores

# Upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Templates & Static
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# HTML Routes
@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

# Form-based Signup
@app.post("/signup")
async def signup(
    username: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...)
):
    if users_col.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists.")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    users_col.insert_one({
        "username": username,
        "email": email,
        "password": hashed
    })
    return {"message": "Signup successful"}

# Form-based Login
@app.post("/login")
async def login(
    email: EmailStr = Form(...),
    password: str = Form(...)
):
    db_user = users_col.find_one({"email": email})
    if not db_user or not bcrypt.checkpw(password.encode(), db_user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Login successful", "user_id": str(db_user["_id"])}

# Upload and MCQ generation
@app.post("/upload/", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...), user_id: str = Form(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDFs allowed.")
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    with open(file_path, "wb") as f:
        f.write(await file.read())
    try:
        summary = generate_summary(file_path)
        questions = generate_questions(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate: {e}")
    pdfs_col.insert_one({
        "file_id": file_id,
        "file_path": file_path,
        "summary": summary,
        "questions": questions
    })
    return RedirectResponse(f"/summary/{file_id}?user_id={user_id}", status_code=303)

# View Summary Page
@app.get("/summary/{file_id}", response_class=HTMLResponse)
def summary_page(request: Request, file_id: str, user_id: str):
# def summary_page(request: Request, file_id: str):
    pdf = pdfs_col.find_one({"file_id": file_id})
    if not pdf:
        raise HTTPException(status_code=404, detail="File not found.")
    return templates.TemplateResponse("summary.html", {
        "request": request,
        "summary": pdf["summary"],
        "session_id": file_id,
        # "user_id": user_id
    })

# View MCQ Questions Page
@app.get("/questions/{session_id}", response_class=HTMLResponse)
def question_page(request: Request, session_id: str, user_id: str, index: int = 0):
    pdf = pdfs_col.find_one({"file_id": session_id})
    if not pdf:
        raise HTTPException(status_code=404, detail="File not found.")
    questions = pdf["questions"]
    if index >= len(questions):
        score_doc = scores_col.find_one({"session_id": session_id, "user_id": user_id}) or {"score": 0}
        return templates.TemplateResponse("questions.html", {
            "request": request, "completed": True,
            "score": score_doc["score"], "total": len(questions),
            "session_id": session_id, "user_id": user_id
        })
    q = questions[index]
    return templates.TemplateResponse("questions.html", {
        "request": request,
        "question": q["question"], "options": q["options"],
        "index": index + 1, "session_id": session_id,
        "user_id": user_id, "completed": False
    })

# Handle Answer Submission
@app.post("/answer/{session_id}", response_class=HTMLResponse)
async def submit_answer(request: Request, session_id: str, selected_option: str = Form(...), user_id: str = Form(...), index: int = Form(...)):
    pdf = pdfs_col.find_one({"file_id": session_id})
    questions = pdf["questions"]
    correct = questions[index - 1]["answer"].strip() == selected_option.strip()

    existing = scores_col.find_one({"session_id": session_id, "user_id": user_id})
    if correct:
        if existing:
            scores_col.update_one({"_id": existing["_id"]}, {"$inc": {"score": 1}})
        else:
            scores_col.insert_one({"session_id": session_id, "user_id": user_id, "score": 1})

    return RedirectResponse(f"/questions/{session_id}?user_id={user_id}&index={index}", status_code=303)

# Custom 404 Handler
@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
