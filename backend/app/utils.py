import logging
import time
import xml.etree.ElementTree as ET

import httpx

# Configure basic logging format
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("cogniflow.utils")

# Global startup tracker
START_TIME = time.time()


def get_uptime_seconds() -> float:
    """
    Returns the server uptime in seconds.
    """
    return time.time() - START_TIME


async def fetch_arxiv_paper(arxiv_id: str) -> tuple[str, bytes]:
    """
    Downloads metadata and PDF content from arXiv.
    Returns: (title, pdf_bytes)
    """
    cleaned_id = arxiv_id.strip()

    # 1. Fetch metadata to extract title
    meta_url = f"https://export.arxiv.org/api/query?id_list={cleaned_id}"
    logger.info(f"Fetching arXiv metadata from: {meta_url}")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Fetch metadata
        meta_resp = await client.get(meta_url, timeout=15.0)
        meta_resp.raise_for_status()

        # Parse XML to find title
        try:
            root = ET.fromstring(meta_resp.text)
            # Standard Atom feed namespace
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entry = root.find("atom:entry", ns)
            if entry is None:
                raise ValueError("arXiv ID not found in database.")

            title_node = entry.find("atom:title", ns)
            if title_node is None or not title_node.text:
                raise ValueError("Paper title not found in metadata.")

            title = title_node.text.strip().replace("\n", " ")
            # Remove double spaces
            title = " ".join(title.split())
        except Exception as e:
            logger.error(f"Failed to parse arXiv XML metadata: {e}")
            title = f"arXiv Paper {cleaned_id}"

        # 2. Download the PDF
        pdf_url = f"https://arxiv.org/pdf/{cleaned_id}.pdf"
        logger.info(f"Downloading arXiv PDF from: {pdf_url}")

        # Use custom headers to avoid bot blockers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        pdf_resp = await client.get(pdf_url, headers=headers, timeout=30.0)

        # Handle cases where PDF doesn't exist
        if pdf_resp.status_code != 200:
            # Try alternative export url
            alt_url = f"https://export.arxiv.org/pdf/{cleaned_id}"
            logger.info(f"Failed to fetch PDF from primary URL. Trying alternative: {alt_url}")
            pdf_resp = await client.get(alt_url, headers=headers, timeout=30.0)

        pdf_resp.raise_for_status()

        # Confirm we actually got a PDF
        content_type = pdf_resp.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and len(pdf_resp.content) < 5000:
            # Sometimes arXiv returns a HTML page for access errors
            raise ValueError("The server did not return a valid PDF file. Check arXiv ID.")

        logger.info(f"Successfully retrieved paper: {title} ({len(pdf_resp.content)} bytes)")
        return title, pdf_resp.content
