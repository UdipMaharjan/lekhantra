import os
import shutil
import uuid
import traceback
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Response, Request
from pydantic import BaseModel, Field
from question_utils import generate_viva_questions, generate_exam_questions
from pdf_service import extract_text_from_pdf_legacy, PDFProcessingError
from ai_utils import generate_ai_response
from rag_service import process_and_index_document, generate_rag_answer, retrieve_relevant_chunks
from vector_store import get_user_documents, delete_document_chunks, get_collection_stats
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from auth_utils import get_current_user, get_firestore_client
from usage_utils import log_usage
from datetime import datetime
import uuid


app = FastAPI(
    title="Lekhantra API",
    description="AI Study Assistant for PDFs, Exams, and Viva",
    version="1.0.0"
)

# CORS configuration - allow localhost and production origins
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
    "*"  # Allow all for development
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
def get_me(current_user: dict = Depends(get_current_user)):
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

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_PDF_SIZE_MB = 5
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024

MAX_QUESTIONS = 10
MAX_AI_TEXT_CHARS = 10000


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
async def upload_pdf(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
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
def ai_generate_viva(request: AIQuestionRequest, current_user: dict = Depends(get_current_user)):
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
def ai_generate_exam(request: AIQuestionRequest,  current_user: dict = Depends(get_current_user)):
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
def ask_pdf(request: AskPDFRequest, current_user: dict = Depends(get_current_user)):
    """
    Legacy endpoint for backward compatibility.
    Uses the old method of reading entire text file.
    """
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
def ask_rag(request: AskRAGRequest, current_user: dict = Depends(get_current_user)):
    """
    RAG-powered question answering endpoint.
    Uses semantic retrieval to find relevant chunks before generating answer.
    """
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
def list_documents(current_user: dict = Depends(get_current_user)):
    """
    List all indexed documents for the current user.
    """
    user_id = current_user.get("uid")

    documents = get_user_documents(user_id)

    return {
        "status": "success",
        "documents": documents
    }


@app.delete("/documents/{document_id}")
def delete_document_endpoint(document_id: str, current_user: dict = Depends(get_current_user)):
    """
    Delete a document and its embeddings from the vector store.
    """
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
def get_vector_stats(current_user: dict = Depends(get_current_user)):
    """
    Get statistics about the vector store.
    Admin/debug endpoint.
    """
    stats = get_collection_stats()
    return {
        "status": "success",
        "stats": stats
    }


@app.get("/conversations")
def list_conversations(current_user: dict = Depends(get_current_user)):
    """List all conversations for the current user"""
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
    current_user: dict = Depends(get_current_user)
):
    """Create a new conversation"""
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
def get_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific conversation with its messages"""
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
    current_user: dict = Depends(get_current_user)
):
    """Update a conversation (rename, delete)"""
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
def delete_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Soft delete a conversation"""
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
    current_user: dict = Depends(get_current_user)
):
    """Add a message to a conversation"""
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
def get_usage_logs(current_user: dict = Depends(get_current_user)):
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

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )