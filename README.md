# Lekhantra

Lekhantra is an AI-powered study assistant that helps students upload PDFs, ask questions from their notes, and generate exam or viva preparation material instantly.

## Features

- Upload PDF study materials
- Extract text from uploaded PDFs
- Ask questions based on uploaded notes
- Generate AI-powered viva questions and answers
- Generate AI-powered exam questions with answers
- Copy, clear, and download generated responses
- Premium Nepali-inspired frontend UI
- FastAPI backend with a simple HTML, CSS, and JavaScript frontend

## Tech Stack

### Backend
- Python
- FastAPI
- uv
- PyMuPDF
- OpenAI API

### Frontend
- HTML
- CSS
- JavaScript

## Project Structure

```text
lekhantra/
├── backend/
│   ├── main.py
│   ├── ai_utils.py
│   ├── pdf_utils.py
│   ├── question_utils.py
│   ├── pyproject.toml
│   └── uv.lock
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── .gitignore
└── README.md