import os
import shutil
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from question_utils import generate_viva_questions, generate_exam_questions
from pdf_utils import extract_text_from_pdf
from ai_utils import generate_ai_response
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="Lekhantra API",
    description="AI Study Assistant for PDFs, Exams, and Viva",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ChatRequest(BaseModel):
    message: str

class QuestionRequest(BaseModel):
    text_file: str

class AIQuestionRequest(BaseModel):
    text_file: str
    number_of_questions: int = 5    

class AskPDFRequest(BaseModel):
    text_file: str
    question: str    

@app.get("/")
def home():
    return {
        "message": "Lekhantra API is running",
        "app": "Lekhantra",
        "status": "success"
    }


@app.post("/chat")
def chat(request: ChatRequest):
    user_message = request.message.lower()

    if "hello" in user_message or "hi" in user_message:
        reply = "Hello! I am Lekhantra, your AI study assistant. Upload notes or ask me study questions."
    elif "exam" in user_message:
        reply = "I can help you prepare for exams by explaining topics and generating probable questions."
    elif "viva" in user_message:
        reply = "I can generate viva questions and answers from your notes or any topic."
    elif "pdf" in user_message:
        reply = "Soon you will be able to upload PDFs and ask questions from them."
    else:
        reply = f"You said: {request.message}. Soon I will answer using AI."

    return {
        "user_message": request.message,
        "reply": reply
    }


@app.post("/upload-pdf")
def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        return {
            "status": "error",
            "message": "Only PDF files are allowed."
        }

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted_text = extract_text_from_pdf(file_path)

    text_filename = file.filename.replace(".pdf", ".txt")
    text_path = os.path.join(UPLOAD_DIR, text_filename)

    with open(text_path, "w", encoding="utf-8") as text_file:
        text_file.write(extracted_text)

    return {
        "status": "success",
        "filename": file.filename,
        "text_file": text_filename,
        "message": "PDF uploaded and text extracted successfully.",
        "text_preview": extracted_text[:1000],
        "total_characters": len(extracted_text)
    }

@app.post("/generate-viva")
def generate_viva(request: QuestionRequest):
    text_path = os.path.join(UPLOAD_DIR, request.text_file)

    if not os.path.exists(text_path):
        return {
            "status": "error",
            "message": "Text file not found. Please upload a PDF first."
        }

    with open(text_path, "r", encoding="utf-8") as file:
        text = file.read()

    questions = generate_viva_questions(text)

    return {
        "status": "success",
        "text_file": request.text_file,
        "type": "viva",
        "questions": questions
    }


@app.post("/generate-exam")
def generate_exam(request: QuestionRequest):
    text_path = os.path.join(UPLOAD_DIR, request.text_file)

    if not os.path.exists(text_path):
        return {
            "status": "error",
            "message": "Text file not found. Please upload a PDF first."
        }

    with open(text_path, "r", encoding="utf-8") as file:
        text = file.read()

    questions = generate_exam_questions(text)

    return {
        "status": "success",
        "text_file": request.text_file,
        "type": "exam",
        "questions": questions
    }

@app.post("/ai-generate-viva")
def ai_generate_viva(request: AIQuestionRequest):
    text_path = os.path.join(UPLOAD_DIR, request.text_file)

    if not os.path.exists(text_path):
        return {
            "status": "error",
            "message": "Text file not found. Please upload a PDF first."
        }

    with open(text_path, "r", encoding="utf-8") as file:
        text = file.read()

    prompt = f"""
You are Lekhantra, an AI study assistant.

Based on the following study notes, generate {request.number_of_questions} viva questions with short, easy-to-understand answers.

Rules:
- Questions should be exam/viva friendly.
- Answers should be simple and clear.
- Use only the content from the provided notes.
- Format the output as numbered Q&A.

Study notes:
{text[:3000]}
"""

    ai_output = generate_ai_response(prompt)

    return {
        "status": "success",
        "text_file": request.text_file,
        "type": "ai_viva",
        "output": ai_output
    }

@app.post("/ai-generate-exam")
def ai_generate_exam(request: AIQuestionRequest):
    text_path = os.path.join(UPLOAD_DIR, request.text_file)

    if not os.path.exists(text_path):
        return {
            "status": "error",
            "message": "Text file not found. Please upload a PDF first."
        }

    with open(text_path, "r", encoding="utf-8") as file:
        text = file.read()

    prompt = f"""
You are Lekhantra, an AI study assistant.

Based on the following study notes, generate {request.number_of_questions} exam-style questions with answers.

Rules:
- Use only the provided notes.
- Include a mix of short questions and long questions.
- Mention marks for each question.
- Give clear student-friendly answers.
- Format output clearly.

Study notes:
{text[:3000]}
"""

    ai_output = generate_ai_response(prompt)

    return {
        "status": "success",
        "text_file": request.text_file,
        "type": "ai_exam",
        "output": ai_output
    }

@app.post("/ask-pdf")
def ask_pdf(request: AskPDFRequest):
    text_path = os.path.join(UPLOAD_DIR, request.text_file)

    if not os.path.exists(text_path):
        return {
            "status": "error",
            "message": "Text file not found. Please upload a PDF first."
        }

    with open(text_path, "r", encoding="utf-8") as file:
        text = file.read()

    prompt = f"""
You are Lekhantra, an AI study assistant.

Answer the user's question using only the PDF notes provided below.

Rules:
- If the answer is in the notes, explain it clearly.
- If the answer is not in the notes, say: "I could not find this in the uploaded notes."
- Keep the answer simple and student-friendly.

PDF notes:
{text[:3000]}

User question:
{request.question}
"""

    ai_output = generate_ai_response(prompt)

    return {
        "status": "success",
        "text_file": request.text_file,
        "question": request.question,
        "answer": ai_output
    }
