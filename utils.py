import os
import fitz  # PyMuPDF
import google.generativeai as genai
from config import EMBEDDING_MODEL, EMBEDDING_DIM

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_embedding(text, task_type="retrieval_document"):
    """
    Gets the embedding vector for a single text.
    """
    result = genai.embed_content(
        model=f"models/{EMBEDDING_MODEL}",
        content=text,
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIM
    )
    return result['embedding']

def get_embeddings_batch(texts, task_type="retrieval_document"):
    """
    Gets embeddings for a list of texts in one API call.
    """
    if not texts: return []
    result = genai.embed_content(
        model=f"models/{EMBEDDING_MODEL}",
        content=texts,
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIM
    )

    embedding_data = result['embedding']
    if isinstance(embedding_data[0], list):
        return embedding_data
    else:
        return [embedding_data]

def extract_text_and_pages(pdf_path):
    """
    Extracts text from PDF and builds a map of page offsets.
    Used by Recursive and Semantic.
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    page_map = []
    current_pos = 0
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        start = current_pos
        full_text += text
        current_pos += len(text)
        page_map.append({
            "start": start,
            "end": current_pos,
            "page_num": page_num + 1
        })
    doc.close()
    return full_text, page_map

def get_pages_for_chunk(chunk_start, chunk_end, page_map):
    """
    Finds which pages a character range (chunk) overlaps with.
    """
    pages = []
    for p in page_map:
        # Check for overlap between [chunk_start, chunk_end] and [p['start'], p['end']]
        if max(chunk_start, p["start"]) < min(chunk_end, p["end"]):
            pages.append(p["page_num"])
    return pages

def cosine_similarity(v1, v2):
    """Calculates cosine similarity between two vectors."""
    import math
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0: return 0.0
    return dot_product / (norm1 * norm2)

_generation_model = genai.GenerativeModel("gemini-2.5-flash-lite")

def count_tokens(text):
    """
    Returns the token count for a given text.
    """
    if not text:
        return 0
    try:
        return _generation_model.count_tokens(text).total_tokens
    except Exception as e:
        print(f"Token counting error: {e}")
        return 0

