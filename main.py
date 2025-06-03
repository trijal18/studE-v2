import os
import uuid
import bcrypt
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from modules.generate_mcqs import generate_summary, generate_questions  

load_dotenv()
key = os.getenv("SESSION_SECRET")
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=key)

MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client.mcqapp
users_col = db.users
pdfs_col = db.pdfs
scores_col = db.scores

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Helper functions ---
def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = users_col.find_one({"_id": ObjectId(user_id)})
    return user


def require_login(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = users_col.find_one({"email": email})
    if not user or not bcrypt.checkpw(password.encode(), user["password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or password"})
    request.session["user_id"] = str(user["_id"])
    return RedirectResponse("/home", status_code=303)


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})


@app.post("/signup")
def signup(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if users_col.find_one({"email": email}):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Email already registered"})
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    result = users_col.insert_one({"username": username, "email": email, "password": hashed})
    request.session["user_id"] = str(result.inserted_id)
    return RedirectResponse("/home", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request):
    user = require_login(request)
    return templates.TemplateResponse("home.html", {"request": request, "user": user})


@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    user = require_login(request)
    return templates.TemplateResponse("upload.html", {"request": request, "user": user})


@app.post("/upload", response_class=HTMLResponse)
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    user = require_login(request)
    if file.content_type != "application/pdf":
        return templates.TemplateResponse("upload.html", {"request": request, "user": user, "error": "Only PDF files allowed"})
    filename = f"{uuid.uuid4()}.pdf"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    try:
        summary = generate_summary(file_path)
        questions = generate_questions(file_path)
    except Exception as e:
        return templates.TemplateResponse("upload.html", {"request": request, "user": user, "error": f"Failed to generate quiz: {e}"})

    pdf_doc = {
        "file_path": file_path,
        "summary": summary,
        "questions": questions,
        "user_id": ObjectId(user["_id"]),
        "filename": filename
    }
    result = pdfs_col.insert_one(pdf_doc)
    pdf_id = str(result.inserted_id)
    return RedirectResponse(f"/summary/{pdf_id}", status_code=303)


@app.get("/summary/{pdf_id}", response_class=HTMLResponse)
def summary_page(request: Request, pdf_id: str):
    user = require_login(request)
    pdf = pdfs_col.find_one({"_id": ObjectId(pdf_id)})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    return templates.TemplateResponse("summary.html", {"request": request, "summary": pdf["summary"], "pdf_id": pdf_id})


@app.get("/quiz_redirect", response_class=HTMLResponse)
def quiz_redirect_page(request: Request):
    user = require_login(request)
    return templates.TemplateResponse("quiz_redirect.html", {"request": request})


@app.post("/quiz_redirect")
def handle_quiz_redirect(pdf_id: str = Form(...)):
    return RedirectResponse(f"/summary/{pdf_id}", status_code=303)


@app.get("/questions/{pdf_id}", response_class=HTMLResponse)
def questions_page(request: Request, pdf_id: str, index: int = 0):
    user = require_login(request)
    pdf = pdfs_col.find_one({"_id": ObjectId(pdf_id)})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    questions = pdf.get("questions", [])
    if index >= len(questions):
        # Show score summary
        score_doc = scores_col.find_one({"pdf_id": pdf_id, "user_id": user["_id"]})
        score = score_doc["score"] if score_doc else 0
        return templates.TemplateResponse(
            "questions.html",
            {
                "request": request,
                "completed": True,
                "score": score,
                "total": len(questions),
                "pdf_id": pdf_id
            }
        )
    q = questions[index]
    return templates.TemplateResponse(
        "questions.html",
        {
            "request": request,
            "question": q["question"],
            "options": q["options"],
            "index": index + 1,
            "pdf_id": pdf_id,
            "completed": False
        }
    )


@app.post("/answer/{pdf_id}")
def submit_answer(pdf_id: str, index: int = Form(...), selected_option: str = Form(...), request: Request = None):
    user = require_login(request)
    pdf = pdfs_col.find_one({"_id": ObjectId(pdf_id)})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    questions = pdf.get("questions", [])
    if index < 1 or index > len(questions):
        raise HTTPException(status_code=400, detail="Invalid question index")

    correct_answer = questions[index - 1]["answer"].strip()
    is_correct = (correct_answer == selected_option.strip())

    score_doc = scores_col.find_one({"pdf_id": pdf_id, "user_id": user["_id"]})
    if not score_doc:
        scores_col.insert_one({"pdf_id": pdf_id, "user_id": user["_id"], "score": 0})
        score_doc = scores_col.find_one({"pdf_id": pdf_id, "user_id": user["_id"]})

    if is_correct:
        scores_col.update_one({"_id": score_doc["_id"]}, {"$inc": {"score": 1}})

    return RedirectResponse(f"/questions/{pdf_id}?index={index}", status_code=303)


@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard_page(request: Request):
    user = require_login(request)

    # Aggregate total scores by user across all PDFs
    pipeline = [
        {
            "$group": {
                "_id": "$user_id",
                "total_score": {"$sum": "$score"}
            }
        },
        {
            "$sort": {"total_score": -1}
        },
        {
            "$limit": 10
        }
    ]
    top_scores = list(scores_col.aggregate(pipeline))

    # Lookup user details
    leaderboard = []
    for item in top_scores:
        user_doc = users_col.find_one({"_id": item["_id"]})
        if user_doc:
            leaderboard.append({"username": user_doc["username"], "score": item["total_score"]})

    return templates.TemplateResponse("leaderboard.html", {"request": request, "leaderboard": leaderboard})


# Admin panel

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    user = require_login(request)
    if user.get("email") != os.getenv("ADMIN_EMAIL"):
        raise HTTPException(status_code=403, detail="Forbidden")
    pdfs = list(pdfs_col.find())
    return templates.TemplateResponse("admin.html", {"request": request, "pdfs": pdfs})


@app.post("/admin/delete")
def admin_delete_pdf(pdf_id: str = Form(...), request: Request = None):
    user = require_login(request)
    # if user.get("email") != os.getenv("ADMIN_EMAIL"):
    #     raise HTTPException(status_code=403, detail="Forbidden")
    pdfs_col.delete_one({"_id": ObjectId(pdf_id)})
    return RedirectResponse("/admin", status_code=303)

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
