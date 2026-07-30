"""
Lekhantra Backend API
AI Study Assistant for PDFs, Exams, and Viva

Lazy imports: Heavy ML libraries (sentence-transformers, chromadb, fitz, openai,
firebase-admin) are deferred until the route or service function that needs them
runs. This keeps startup fast so Render detects the open port within its 120s
timeout before any ML models load. Initialization happens on first use, not at
server start.
"""

import os
import uuid
import traceback
from pathlib import Path
from datetime import datetime

# FastAPI core — lightweight, loads in milliseconds
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ============================================================
# STARTUP BANNER — shows immediately, before any heavy imports
# ============================================================
print("=" * 60)
print("  Lekhantra Backend Starting...")
print("=" * 60)
print("  [1/6] FastAPI core loaded")

# ============================================================
# Constants
# ============================================================
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("LEKHANTRA_DATA_DIR", BACKEND_DIR))
UPLOAD_DIR = str(DATA_DIR / "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_PDF_SIZE_MB = 5
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024
MAX_QUESTIONS = 10
MAX_AI_TEXT_CHARS = 10000

# ============================================================
# Lazy Dependency Helpers
# These import firebase-admin / sentence-transformers only when
# a route that needs auth is actually called — not at startup.
# ============================================================

def _lazy_get_current_user():
    """Wrapper so Depends() works with a lazy import inside."""
    from auth_utils import get_current_user
    return get_current_user

def _lazy_get_firestore_client():
    """Wrapper so Depends() works with a lazy import inside."""
    from auth_utils import get_firestore_client
    return get_firestore_client

# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="Lekhantra API",
    description="AI Study Assistant for PDFs, Exams, and Viva",
    version="1.0.0"
)

# CORS configuration
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5500",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost",
    "http://127.0.0.1",
    "https://lekhantra.onrender.com",
    "https://lekhantra-backend.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[BACKEND ERROR] Unhandled exception on {request.method} {request.url.path}")
    print(f"[BACKEND ERROR] Exception: {exc}")
    print(f"[BACKEND ERROR] Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc) if hasattr(exc, '__str__') else "Internal server error"
        }
    )

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[MIDDLEWARE] {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        print(f"[MIDDLEWARE] Response status: {response.status_code}")
        return response
    except Exception as e:
        print(f"[MIDDLEWARE] Error: {e}")
        print(f"[MIDDLEWARE] Traceback: {traceback.format_exc()}")
        raise

@app.get("/me")
def get_me(current_user: dict = Depends(_lazy_get_current_user())):
    return {
        "status": "success",
        "user": current_user
    }

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    for error in exc.errors():
        field = error.get("loc", ["unknown"])[-1]
        error_type = error.get("type")

        if field == "number_of_questions":
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "message": f"Number of questions must be between 1 and {MAX_QUESTIONS}."
                }
            )

    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Invalid input. Please check your request data.",
            "details": exc.errors()
        }
    )

class ChatRequest(BaseModel):
    message: str

class QuestionRequest(BaseModel):
    text_file: str

class AIQuestionRequest(BaseModel):
    text_file: str
    number_of_questions: int = Field(default=5, ge=1, le=MAX_QUESTIONS)

class AskPDFRequest(BaseModel):
    text_file: str
    question: str

class AskRAGRequest(BaseModel):
    question: str
    document_ids: list[str] | None = None  # Optional filter for specific documents

class CreateConversationRequest(BaseModel):
    title: str = "New Chat"
    document_id: str | None = None

class UpdateConversationRequest(BaseModel):
    title: str | None = None
    is_deleted: bool | None = None

class AddMessageRequest(BaseModel):
    role: str  # "user" or "assistant"
    content: str

# RAG-specific response models
class SourceReference(BaseModel):
    text: str
    page_number: int
    chunk_id: str
    filename: str
    similarity: float

class RAGAnswerResponse(BaseModel):
    status: str
    answer: str
    sources: list[SourceReference]
    question: str

# Profile Management Models
class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    photo_url: str | None = None

class UpdatePreferencesRequest(BaseModel):
    response_style: str | None = None  # "concise", "balanced", "detailed"
    retrieval_depth: int | None = None  # 3, 5, or 10
    show_sources: bool | None = None

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Lekhantra backend"
    }

@app.head("/health")
def health_check_head():
    return Response(status_code=200)


@app.head("/")
def root_head():
    return Response(status_code=200)


def create_error_response(message: str, details: str | None = None):
    response = {
        "status": "error",
        "message": message
    }

    if details:
        response["details"] = details

    return response


def get_safe_pdf_filename(original_filename: str) -> str:
    file_extension = Path(original_filename).suffix.lower()

    if file_extension != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=create_error_response("Only PDF files are allowed.")
        )

    safe_name = f"{uuid.uuid4().hex}.pdf"
    return safe_name


def get_text_path(text_file: str) -> str:
    safe_name = Path(text_file).name
    return os.path.join(UPLOAD_DIR, safe_name)     

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
async def upload_pdf(file: UploadFile = File(...), current_user: dict = Depends(_lazy_get_current_user())):

    # --- Lazy imports (heavy: rag_service triggers sentence-transformers + fitz) ---
    from rag_service import process_and_index_document
    from pdf_service import extract_text_from_pdf_legacy
    from usage_utils import log_usage
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response("No file was uploaded.")
        )

    safe_pdf_filename = get_safe_pdf_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_pdf_filename)

    file_content = await file.read()

    if len(file_content) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=create_error_response(
                f"PDF is too large. Maximum allowed size is {MAX_PDF_SIZE_MB} MB."
            )
        )

    with open(file_path, "wb") as buffer:
        buffer.write(file_content)

    user_id = current_user.get("uid")

    try:
        # Process PDF with RAG pipeline (extract text, chunk, embed, store)
        rag_result = process_and_index_document(
            file_path=file_path,
            user_id=user_id,
            filename=file.filename
        )

        if rag_result["status"] == "error":
            # Clean up the uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail=create_error_response(rag_result["message"])
            )

        # For backward compatibility, also extract text to .txt file
        try:
            extracted_text = extract_text_from_pdf_legacy(file_path)
            text_filename = safe_pdf_filename.replace(".pdf", ".txt")
            text_path = os.path.join(UPLOAD_DIR, text_filename)
            with open(text_path, "w", encoding="utf-8") as text_file:
                text_file.write(extracted_text)
        except Exception as e:
            print(f"[BACKEND] Warning: Could not create text file: {e}")
            extracted_text = ""
            text_filename = ""

        log_usage(
            current_user,
            "upload_pdf",
            {
                "original_filename": file.filename,
                "saved_pdf": safe_pdf_filename,
                "text_file": text_filename,
                "file_size_mb": round(len(file_content) / (1024 * 1024), 2),
                "total_characters": rag_result.get("total_characters", 0),
                "chunk_count": rag_result.get("chunk_count", 0),
                "document_id": rag_result.get("document_id"),
                "is_duplicate": rag_result.get("is_duplicate", False)
            }
        )

        response_data = {
            "status": "success",
            "original_filename": file.filename,
            "saved_pdf": safe_pdf_filename,
            "text_file": text_filename,
            "document_id": rag_result.get("document_id"),
            "message": "PDF uploaded and processed successfully.",
            "text_preview": extracted_text[:1000] if extracted_text else "",
            "total_characters": rag_result.get("total_characters", 0),
            "file_size_mb": round(len(file_content) / (1024 * 1024), 2)
        }

        # Add duplicate info if applicable
        if rag_result.get("is_duplicate"):
            response_data["is_duplicate"] = True
            response_data["message"] = "Document already exists. Using existing embeddings."

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        print(f"[BACKEND] Upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to process PDF: {str(e)}")
        )


@app.post("/generate-viva")
def generate_viva(request: QuestionRequest):
    from question_utils import generate_viva_questions

    text_path = get_text_path(request.text_file)

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
    from question_utils import generate_exam_questions

    text_path = get_text_path(request.text_file)

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
def ai_generate_viva(request: AIQuestionRequest, current_user: dict = Depends(_lazy_get_current_user())):
    from ai_utils import generate_ai_response
    from usage_utils import log_usage

    text_path = get_text_path(request.text_file)

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
{text[:MAX_AI_TEXT_CHARS]}
"""

    ai_output = generate_ai_response(prompt)

    log_usage(
    current_user,
    "ai_generate_viva",
    {
        "text_file": request.text_file,
        "number_of_questions": request.number_of_questions,
        "text_characters_used": min(len(text), MAX_AI_TEXT_CHARS),
    }
)
    return {
        "status": "success",
        "text_file": request.text_file,
        "type": "ai_viva",
        "output": ai_output
    }

@app.post("/ai-generate-exam")
def ai_generate_exam(request: AIQuestionRequest, current_user: dict = Depends(_lazy_get_current_user())):
    from ai_utils import generate_ai_response
    from usage_utils import log_usage

    text_path = get_text_path(request.text_file)

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
{text[:MAX_AI_TEXT_CHARS]}
"""

    ai_output = generate_ai_response(prompt)

    log_usage(
    current_user,
    "ai_generate_exam",
    {
        "text_file": request.text_file,
        "number_of_questions": request.number_of_questions,
        "text_characters_used": min(len(text), MAX_AI_TEXT_CHARS),
    }
)

    return {
        "status": "success",
        "text_file": request.text_file,
        "type": "ai_exam",
        "output": ai_output
    }

@app.post("/ask-pdf")
def ask_pdf(request: AskPDFRequest, current_user: dict = Depends(_lazy_get_current_user())):
    """
    Legacy endpoint for backward compatibility.
    Uses the old method of reading entire text file.
    """
    from ai_utils import generate_ai_response
    from usage_utils import log_usage

    text_path = get_text_path(request.text_file)

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
{text[:MAX_AI_TEXT_CHARS]}

User question:
{request.question}
"""

    ai_output = generate_ai_response(prompt)

    log_usage(
    current_user,
    "ask_pdf",
    {
        "text_file": request.text_file,
        "question": request.question,
        "text_characters_used": min(len(text), MAX_AI_TEXT_CHARS),
    }
)

    return {
        "status": "success",
        "text_file": request.text_file,
        "question": request.question,
        "answer": ai_output
    }


@app.post("/ask-rag")
def ask_rag(request: AskRAGRequest, current_user: dict = Depends(_lazy_get_current_user())):
    """
    RAG-powered question answering endpoint.
    Uses semantic retrieval to find relevant chunks before generating answer.
    """
    from rag_service import generate_rag_answer
    from usage_utils import log_usage

    user_id = current_user.get("uid")

    if not request.question or not request.question.strip():
        return {
            "status": "error",
            "message": "Question cannot be empty."
        }

    # Generate answer using RAG pipeline
    rag_response = generate_rag_answer(
        question=request.question,
        user_id=user_id,
        document_ids=request.document_ids
    )

    # Format sources for response
    sources = [
        {
            "text": source.text,
            "page_number": source.page_number,
            "chunk_id": source.chunk_id,
            "filename": source.filename,
            "similarity": source.similarity
        }
        for source in rag_response.sources
    ]

    log_usage(
        current_user,
        "ask_rag",
        {
            "question": request.question,
            "document_ids": request.document_ids,
            "sources_count": len(sources),
            "context_chars": len(rag_response.context_used)
        }
    )

    return {
        "status": "success",
        "answer": rag_response.answer,
        "sources": sources,
        "question": request.question
    }


@app.get("/documents")
def list_documents(current_user: dict = Depends(_lazy_get_current_user())):
    """
    List all indexed documents for the current user.
    """
    from vector_store import get_user_documents

    user_id = current_user.get("uid")
    documents = get_user_documents(user_id)

    return {
        "status": "success",
        "documents": documents
    }


@app.delete("/documents/{document_id}")
def delete_document_endpoint(document_id: str, current_user: dict = Depends(_lazy_get_current_user())):
    """
    Delete a document and its embeddings from the vector store.
    """
    from vector_store import delete_document_chunks
    from usage_utils import log_usage

    user_id = current_user.get("uid")
    success = delete_document_chunks(document_id, user_id)

    if success:
        log_usage(
            current_user,
            "delete_document",
            {"document_id": document_id}
        )
        return {
            "status": "success",
            "message": "Document deleted successfully"
        }
    else:
        return {
            "status": "error",
            "message": "Failed to delete document"
        }


@app.get("/vector-stats")
def get_vector_stats(current_user: dict = Depends(_lazy_get_current_user())):
    """
    Get statistics about the vector store.
    Admin/debug endpoint.
    """
    from vector_store import get_collection_stats

    stats = get_collection_stats()
    return {
        "status": "success",
        "stats": stats
    }


@app.get("/conversations")
def list_conversations(current_user: dict = Depends(_lazy_get_current_user())):
    """List all conversations for the current user"""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    conversations_ref = (
        db.collection("conversations")
        .where("user_id", "==", uid)
        .where("is_deleted", "==", False)
        .order_by("updated_at", direction="DESCENDING")
    )

    conversations = []
    for doc in conversations_ref.stream():
        data = doc.to_dict()
        conversations.append({
            "id": doc.id,
            "title": data.get("title", "New Chat"),
            "document_id": data.get("document_id"),
            "created_at": data.get("created_at").isoformat() if data.get("created_at") else None,
            "updated_at": data.get("updated_at").isoformat() if data.get("updated_at") else None,
        })

    return {
        "status": "success",
        "conversations": conversations
    }


@app.post("/conversations")
def create_conversation(
    request: CreateConversationRequest,
    current_user: dict = Depends(_lazy_get_current_user())
):
    """Create a new conversation"""
    from auth_utils import get_firestore_client
    print(f"[BACKEND] create_conversation called by user: {current_user.get('uid')}")
    print(f"[BACKEND] Request data: {request}")

    db = get_firestore_client()
    uid = current_user.get("uid")

    conversation_data = {
        "user_id": uid,
        "title": request.title,
        "document_id": request.document_id,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "is_deleted": False,
    }

    doc_ref = db.collection("conversations").add(conversation_data)
    print(f"[BACKEND] Created conversation with ID: {doc_ref[1].id}")

    return {
        "status": "success",
        "conversation": {
            "id": doc_ref[1].id,
            "title": request.title,
            "document_id": request.document_id,
            "created_at": conversation_data["created_at"].isoformat(),
            "updated_at": conversation_data["updated_at"].isoformat(),
        }
    }


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, current_user: dict = Depends(_lazy_get_current_user())):
    """Get a specific conversation with its messages"""
    from auth_utils import get_firestore_client
    print(f"[BACKEND] get_conversation called, ID: {conversation_id}")
    print(f"[BACKEND] User: {current_user.get('uid')}")

    db = get_firestore_client()
    uid = current_user.get("uid")

    # Get conversation
    conv_ref = db.collection("conversations").document(conversation_id)
    conv_doc = conv_ref.get()

    if not conv_doc.exists:
        print(f"[BACKEND] Conversation not found: {conversation_id}")
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Conversation not found"})

    conv_data = conv_doc.to_dict()
    print(f"[BACKEND] Conversation data: {conv_data}")

    # Security check - ensure user owns this conversation
    if conv_data.get("user_id") != uid:
        print(f"[BACKEND] User mismatch!")
        raise HTTPException(status_code=403, detail={"status": "error", "message": "Access denied"})

    if conv_data.get("is_deleted"):
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Conversation not found"})

    # Get messages - without ordering first to avoid index issues
    messages_ref = (
        db.collection("conversations")
        .document(conversation_id)
        .collection("messages")
    )

    messages = []
    try:
        for doc in messages_ref.stream():
            data = doc.to_dict()
            messages.append({
                "id": doc.id,
                "role": data.get("role"),
                "content": data.get("content"),
                "created_at": data.get("created_at").isoformat() if data.get("created_at") else None,
            })
        print(f"[BACKEND] Retrieved {len(messages)} messages")
    except Exception as e:
        print(f"[BACKEND] Error retrieving messages: {e}")
        # Return empty messages if there's an indexing issue
        messages = []

    return {
        "status": "success",
        "conversation": {
            "id": conv_doc.id,
            "title": conv_data.get("title", "New Chat"),
            "document_id": conv_data.get("document_id"),
            "created_at": conv_data.get("created_at").isoformat() if conv_data.get("created_at") else None,
            "updated_at": conv_data.get("updated_at").isoformat() if conv_data.get("updated_at") else None,
        },
        "messages": messages
    }


@app.put("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    current_user: dict = Depends(_lazy_get_current_user())
):
    """Update a conversation (rename, delete)"""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    conv_ref = db.collection("conversations").document(conversation_id)
    conv_doc = conv_ref.get()

    if not conv_doc.exists:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Conversation not found"})

    conv_data = conv_doc.to_dict()

    if conv_data.get("user_id") != uid:
        raise HTTPException(status_code=403, detail={"status": "error", "message": "Access denied"})

    # Build update data
    update_data = {}
    if request.title is not None:
        update_data["title"] = request.title
    if request.is_deleted is not None:
        update_data["is_deleted"] = request.is_deleted

    update_data["updated_at"] = datetime.now()

    conv_ref.update(update_data)

    return {
        "status": "success",
        "message": "Conversation updated"
    }


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, current_user: dict = Depends(_lazy_get_current_user())):
    """Soft delete a conversation"""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    conv_ref = db.collection("conversations").document(conversation_id)
    conv_doc = conv_ref.get()

    if not conv_doc.exists:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Conversation not found"})

    conv_data = conv_doc.to_dict()

    if conv_data.get("user_id") != uid:
        raise HTTPException(status_code=403, detail={"status": "error", "message": "Access denied"})

    # Soft delete
    conv_ref.update({
        "is_deleted": True,
        "updated_at": datetime.now()
    })

    return {
        "status": "success",
        "message": "Conversation deleted"
    }


@app.post("/conversations/{conversation_id}/messages")
def add_message(
    conversation_id: str,
    request: AddMessageRequest,
    current_user: dict = Depends(_lazy_get_current_user())
):
    """Add a message to a conversation"""
    from auth_utils import get_firestore_client
    print(f"[BACKEND] add_message called")
    print(f"[BACKEND] conversation_id: {conversation_id}")
    print(f"[BACKEND] user: {current_user.get('uid')}")
    print(f"[BACKEND] request: {request}")

    db = get_firestore_client()
    uid = current_user.get("uid")

    # Verify conversation exists and user owns it
    conv_ref = db.collection("conversations").document(conversation_id)
    conv_doc = conv_ref.get()

    print(f"[BACKEND] Conversation exists: {conv_doc.exists}")

    if not conv_doc.exists:
        print(f"[BACKEND] Conversation not found!")
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Conversation not found"})

    conv_data = conv_doc.to_dict()
    print(f"[BACKEND] Conversation data: {conv_data}")

    if conv_data.get("user_id") != uid:
        print(f"[BACKEND] User mismatch! conv_user={conv_data.get('user_id')}, req_user={uid}")
        raise HTTPException(status_code=403, detail={"status": "error", "message": "Access denied"})

    if conv_data.get("is_deleted"):
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Conversation not found"})

    # Create message
    message_data = {
        "role": request.role,
        "content": request.content,
        "created_at": datetime.now()
    }

    msg_ref = db.collection("conversations").document(conversation_id).collection("messages").add(message_data)

    # Update conversation timestamp
    conv_ref.update({"updated_at": datetime.now()})

    return {
        "status": "success",
        "message": {
            "id": msg_ref[1].id,
            "role": request.role,
            "content": request.content,
            "created_at": message_data["created_at"].isoformat(),
        }
    }


@app.get("/usage-logs")
def get_usage_logs(current_user: dict = Depends(_lazy_get_current_user())):
    from auth_utils import get_firestore_client
    db = get_firestore_client()

    logs_ref = (
        db.collection("usage_logs")
        .order_by("timestamp", direction="DESCENDING")
        .limit(20)
    )

    logs = []

    for doc in logs_ref.stream():
        data = doc.to_dict()

        timestamp = data.get("timestamp")
        if timestamp:
            data["timestamp"] = timestamp.isoformat()

        logs.append({
            "id": doc.id,
            **data
        })

    return {
        "status": "success",
        "logs": logs
    }


# =============================================================================
# PROFILE MANAGEMENT ENDPOINTS
# =============================================================================

def get_user_preferences_document(db, uid):
    """Get or create user preferences document."""
    prefs_ref = db.collection("user_preferences").document(uid)
    prefs_doc = prefs_ref.get()

    if not prefs_doc.exists:
        # Create default preferences
        prefs_ref.set({
            "response_style": "balanced",
            "retrieval_depth": 5,
            "show_sources": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })
        return prefs_ref.get()
    return prefs_doc


def calculate_real_stats(db, uid):
    """
    Calculate real statistics by querying actual data from Firestore.
    """
    from vector_store import get_user_documents

    stats = {
        "documents_uploaded": 0,
        "conversations_created": 0,
        "questions_asked": 0,
        "ai_responses": 0,
        "storage_used_bytes": 0,
        "last_upload_date": None,
    }

    # Count conversations
    try:
        convs_ref = db.collection("conversations").where("user_id", "==", uid).where("is_deleted", "==", False)
        stats["conversations_created"] = sum(1 for _ in convs_ref.stream())
    except Exception as e:
        print(f"[STATS] Error counting conversations: {e}")

    # Count documents from ChromaDB
    try:
        chroma_docs = get_user_documents(uid)
        stats["documents_uploaded"] = len(chroma_docs)

        # Estimate storage: 50KB per document average
        stats["storage_used_bytes"] = len(chroma_docs) * 50 * 1024

        # Get last upload date from user_stats if available
        stats_ref = db.collection("user_stats").document(uid).get()
        if stats_ref.exists:
            stats_data = stats_ref.to_dict()
            stats["last_upload_date"] = stats_data.get("last_upload_date")
            # Use stored storage if more accurate
            if stats_data.get("storage_used_bytes"):
                stats["storage_used_bytes"] = stats_data.get("storage_used_bytes")
    except Exception as e:
        print(f"[STATS] Error getting documents: {e}")

    # Count messages (questions + responses)
    try:
        # Get all conversations and count their messages
        convs_ref = db.collection("conversations").where("user_id", "==", uid)
        for conv_doc in convs_ref.stream():
            messages_ref = db.collection("conversations").document(conv_doc.id).collection("messages")
            for msg_doc in messages_ref.stream():
                role = msg_doc.to_dict().get("role")
                if role == "user":
                    stats["questions_asked"] += 1
                elif role == "assistant":
                    stats["ai_responses"] += 1
    except Exception as e:
        print(f"[STATS] Error counting messages: {e}")

    return stats


@app.get("/profile")
def get_profile(current_user: dict = Depends(_lazy_get_current_user())):
    """Get user profile information with real calculated statistics."""
    from auth_utils import get_firestore_client

    db = get_firestore_client()
    uid = current_user.get("uid")

    # Get preferences before composing the profile, since profile edits are
    # stored there rather than in Firebase Auth.
    prefs_doc = get_user_preferences_document(db, uid)
    prefs_data = prefs_doc.to_dict()

    # Get user info from Firebase Auth (from token)
    profile_data = {
        "uid": uid,
        "email": current_user.get("email", ""),
        "display_name": prefs_data.get("display_name") or current_user.get("name", current_user.get("email", "").split("@")[0]),
        "photo_url": prefs_data.get("photo_url") or current_user.get("picture", ""),
        "provider": current_user.get("provider", "email"),
        "email_verified": current_user.get("email_verified", False)
    }

    # Calculate real stats from actual data
    stats_data = calculate_real_stats(db, uid)

    # Calculate storage MB
    storage_bytes = stats_data.get("storage_used_bytes", 0)
    storage_mb = round(storage_bytes / (1024 * 1024), 2)

    return {
        "status": "success",
        "profile": {
            "uid": profile_data["uid"],
            "email": profile_data["email"],
            "display_name": profile_data["display_name"],
            "photo_url": profile_data["photo_url"],
            "provider": profile_data["provider"],
            "email_verified": profile_data["email_verified"],
            "member_since": current_user.get("user_id_creation_timestamp", None)
        },
        "statistics": {
            "documents_uploaded": stats_data.get("documents_uploaded", 0),
            "conversations_created": stats_data.get("conversations_created", 0),
            "questions_asked": stats_data.get("questions_asked", 0),
            "ai_responses": stats_data.get("ai_responses", 0),
            "storage_used_mb": storage_mb,
            "storage_used_bytes": storage_bytes,
            "last_upload_date": stats_data.get("last_upload_date").isoformat() if stats_data.get("last_upload_date") else None
        },
        "preferences": {
            "response_style": prefs_data.get("response_style", "balanced"),
            "retrieval_depth": prefs_data.get("retrieval_depth", 5),
            "show_sources": prefs_data.get("show_sources", True)
        }
    }


@app.put("/profile")
def update_profile(request: UpdateProfileRequest, current_user: dict = Depends(_lazy_get_current_user())):
    """Update user profile (display name, photo URL)."""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    # Note: Full profile updates require Firebase Admin SDK user management
    # For now, we store display preferences in Firestore
    prefs_ref = db.collection("user_preferences").document(uid)
    update_data = {"updated_at": datetime.now()}
    if request.display_name is not None:
        update_data["display_name"] = request.display_name
    if request.photo_url is not None:
        update_data["photo_url"] = request.photo_url

    prefs_ref.set(update_data, merge=True)

    return {
        "status": "success",
        "message": "Profile updated successfully"
    }


@app.get("/profile/documents")
def get_profile_documents(current_user: dict = Depends(_lazy_get_current_user())):
    """Get all documents uploaded by the user."""
    from vector_store import get_user_documents

    user_id = current_user.get("uid")
    documents = get_user_documents(user_id)

    return {
        "status": "success",
        "documents": documents
    }


@app.delete("/profile/documents/{document_id}")
def delete_profile_document(document_id: str, current_user: dict = Depends(_lazy_get_current_user())):
    """Delete a document from user's library."""
    from vector_store import delete_document_chunks
    from auth_utils import get_firestore_client

    user_id = current_user.get("uid")
    success = delete_document_chunks(document_id, user_id)

    if success:
        db = get_firestore_client()
        stats_ref = db.collection("user_stats").document(user_id)
        stats_doc = stats_ref.get()

        if stats_doc.exists:
            stats_data = stats_doc.to_dict()
            new_storage = max(0, stats_data.get("storage_used_bytes", 0) - (50 * 1024))
            stats_ref.update({
                "storage_used_bytes": new_storage,
                "updated_at": datetime.now()
            })

        return {
            "status": "success",
            "message": "Document deleted successfully"
        }
    else:
        return {
            "status": "error",
            "message": "Failed to delete document"
        }


@app.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str, current_user: dict = Depends(_lazy_get_current_user())):
    """
    Re-index a document by deleting and regenerating its embeddings.
    Note: This requires the original PDF file to be available.
    For now, we just confirm the document exists in ChromaDB.
    """
    from vector_store import get_document_chunks

    user_id = current_user.get("uid")
    chunks = get_document_chunks(document_id, user_id)

    if not chunks:
        return {
            "status": "error",
            "message": "Document not found"
        }

    # In a full implementation, we would:
    # 1. Look up the original PDF file path from a document metadata store
    # 2. Re-process the PDF and regenerate embeddings
    # For now, return success as the document is already indexed
    return {
        "status": "success",
        "message": "Document is already indexed",
        "chunk_count": len(chunks)
    }


@app.get("/profile/preferences")
def get_profile_preferences(current_user: dict = Depends(_lazy_get_current_user())):
    """Get user preferences."""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    prefs_doc = get_user_preferences_document(db, uid)
    prefs_data = prefs_doc.to_dict()

    return {
        "status": "success",
        "preferences": {
            "response_style": prefs_data.get("response_style", "balanced"),
            "retrieval_depth": prefs_data.get("retrieval_depth", 5),
            "show_sources": prefs_data.get("show_sources", True)
        }
    }


@app.put("/profile/preferences")
def update_profile_preferences(request: UpdatePreferencesRequest, current_user: dict = Depends(_lazy_get_current_user())):
    """Update user preferences."""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    update_data = {"updated_at": datetime.now()}

    if request.response_style is not None:
        if request.response_style not in ["concise", "balanced", "detailed"]:
            raise HTTPException(status_code=400, detail={"status": "error", "message": "Invalid response style"})
        update_data["response_style"] = request.response_style

    if request.retrieval_depth is not None:
        if request.retrieval_depth not in [3, 5, 10]:
            raise HTTPException(status_code=400, detail={"status": "error", "message": "Invalid retrieval depth"})
        update_data["retrieval_depth"] = request.retrieval_depth

    if request.show_sources is not None:
        update_data["show_sources"] = request.show_sources

    prefs_ref = db.collection("user_preferences").document(uid)
    prefs_ref.set(update_data, merge=True)

    return {
        "status": "success",
        "message": "Preferences updated successfully"
    }


@app.get("/profile/export")
def export_user_data(current_user: dict = Depends(_lazy_get_current_user())):
    """Export all user data (conversations and messages)."""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    # Get all conversations
    conversations_ref = db.collection("conversations").where("user_id", "==", uid)
    conversations = []

    for conv_doc in conversations_ref.stream():
        conv_data = conv_doc.to_dict()

        # Get messages for this conversation
        messages_ref = db.collection("conversations").document(conv_doc.id).collection("messages")
        messages = []

        for msg_doc in messages_ref.stream():
            msg_data = msg_doc.to_dict()
            messages.append({
                "id": msg_doc.id,
                "role": msg_data.get("role"),
                "content": msg_data.get("content"),
                "created_at": msg_data.get("created_at").isoformat() if msg_data.get("created_at") else None
            })

        conversations.append({
            "id": conv_doc.id,
            "title": conv_data.get("title"),
            "created_at": conv_data.get("created_at").isoformat() if conv_data.get("created_at") else None,
            "updated_at": conv_data.get("updated_at").isoformat() if conv_data.get("updated_at") else None,
            "messages": messages
        })

    # Get user stats
    stats_ref = db.collection("user_stats").document(uid)
    stats_doc = stats_ref.get()
    stats_data = stats_doc.to_dict() if stats_doc.exists else {}

    return {
        "status": "success",
        "export": {
            "exported_at": datetime.now().isoformat(),
            "user_id": uid,
            "statistics": {
                "documents_uploaded": stats_data.get("documents_uploaded", 0),
                "conversations_created": stats_data.get("conversations_created", 0),
                "questions_asked": stats_data.get("questions_asked", 0),
                "ai_responses": stats_data.get("ai_responses", 0)
            },
            "conversations": conversations
        }
    }


@app.delete("/profile/conversations")
def delete_all_conversations(current_user: dict = Depends(_lazy_get_current_user())):
    """Delete all user conversations."""
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    # Get all conversations
    conversations_ref = db.collection("conversations").where("user_id", "==", uid)

    deleted_count = 0
    for conv_doc in conversations_ref.stream():
        conv_doc.reference.update({
            "is_deleted": True,
            "updated_at": datetime.now()
        })
        deleted_count += 1

    # Update stats
    stats_ref = db.collection("user_stats").document(uid)
    stats_ref.set({
        "conversations_created": 0,
        "questions_asked": 0,
        "ai_responses": 0,
        "updated_at": datetime.now()
    }, merge=True)

    return {
        "status": "success",
        "message": f"Deleted {deleted_count} conversations"
    }


@app.delete("/profile/documents")
def delete_all_documents(current_user: dict = Depends(_lazy_get_current_user())):
    """Delete all user documents."""
    from vector_store import get_user_documents, delete_document_chunks
    from auth_utils import get_firestore_client

    user_id = current_user.get("uid")
    db = get_firestore_client()
    documents = get_user_documents(user_id)

    deleted_count = 0
    for doc in documents:
        doc_id = doc.get("document_id")
        if doc_id:
            success = delete_document_chunks(doc_id, user_id)
            if success:
                deleted_count += 1

    # Update stats
    stats_ref = db.collection("user_stats").document(user_id)
    stats_ref.set({
        "documents_uploaded": 0,
        "storage_used_bytes": 0,
        "last_upload_date": None,
        "updated_at": datetime.now()
    }, merge=True)

    return {
        "status": "success",
        "message": f"Deleted {deleted_count} documents"
    }


# =============================================================================
# STATS INCREMENT ENDPOINTS (called by frontend automatically)
# =============================================================================

class IncrementStatRequest(BaseModel):
    stat: str
    value: int = 1

@app.post("/stats/increment")
def increment_stat(request: IncrementStatRequest, current_user: dict = Depends(_lazy_get_current_user())):
    """
    Increment a user statistic.
    Called automatically by frontend after actions.
    """
    from auth_utils import get_firestore_client
    db = get_firestore_client()
    uid = current_user.get("uid")

    valid_stats = [
        "documents_uploaded",
        "conversations_created",
        "questions_asked",
        "ai_responses",
        "storage_used_bytes"
    ]

    if request.stat not in valid_stats:
        raise HTTPException(status_code=400, detail={"status": "error", "message": f"Invalid stat: {request.stat}"})

    stats_ref = db.collection("user_stats").document(uid)
    stats_doc = stats_ref.get()

    if not stats_doc.exists:
        # Initialize stats
        stats_ref.set({
            "documents_uploaded": 0,
            "conversations_created": 0,
            "questions_asked": 0,
            "ai_responses": 0,
            "storage_used_bytes": 0,
            "last_upload_date": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })

    current_value = stats_doc.to_dict().get(request.stat, 0) if stats_doc.exists else 0
    new_value = current_value + request.value

    stats_ref.update({
        request.stat: new_value,
        "updated_at": datetime.now()
    })

    # Special handling for last_upload_date
    if request.stat == "documents_uploaded":
        stats_ref.update({"last_upload_date": datetime.now()})

    return {
        "status": "success",
        "stat": request.stat,
        "previous_value": current_value,
        "new_value": new_value
    }


if __name__ == "__main__":
    import uvicorn

    print("  [5/6] Server ready — waiting for first request")
    print("  [6/6] Heavy services (Firebase, ChromaDB, Embeddings) init on first use")
    print("=" * 60)

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
