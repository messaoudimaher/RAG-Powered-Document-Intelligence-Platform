import io
import logging
from pypdf import PdfReader

logger = logging.getLogger("docmind.ingestion")

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts text content from PDF file bytes using pypdf.
    """
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise ValueError(f"Failed to parse PDF document: {e}")
