import io
import logging
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
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

def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extracts text content from DOCX file bytes using python-docx.
    """
    try:
        docx_file = io.BytesIO(file_bytes)
        doc = Document(docx_file)
        text_parts = [p.text for p in doc.paragraphs if p.text]
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        raise ValueError(f"Failed to parse DOCX document: {e}")

def extract_text_from_txt(file_bytes: bytes) -> str:
    """
    Extracts text content from TXT file bytes with decoding fallbacks.
    """
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1")
        except Exception as e:
            logger.error(f"Error decoding text file: {e}")
            raise ValueError(f"Failed to decode TXT file: {e}")

def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[str]:
    """
    Splits text into chunks using LangChain's RecursiveCharacterTextSplitter.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    return splitter.split_text(text)
