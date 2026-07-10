import fitz  # PyMuPDF


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from all pages of a PDF file.
    """
    text = ""

    try:
        pdf_document = fitz.open(file_path)

        for page_number in range(len(pdf_document)):
            page = pdf_document[page_number]
            text += page.get_text()
            text += "\n"

        pdf_document.close()
        return text.strip()

    except Exception as e:
        return f"Error reading PDF: {str(e)}"