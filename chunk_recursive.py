import os
import json
import psycopg2
import psycopg2.extras
import fitz  # PyMuPDF
from config import DB_CONFIG
from utils import get_embedding, extract_text_and_pages, get_pages_for_chunk

def chunk_text_recursive(text, size=1000, overlap=100):
    chunks = []
    start = 0
    text_len = len(text)
    
    # Priority of separators (Paragraph, Line break, Sentence, Space)
    separators = ["\n\n", "\n", ". ", " "]
    
    while start < text_len:
        end = start + size
        
        if end >= text_len:
            content = text[start:text_len].strip()
            if content:
                chunks.append((start, text_len, content))
            break
            
        best_end = end
        found_separator = False
        
        search_window_start = max(start, end - int(size/2))
        search_window = text[search_window_start:end]
        
        for sep in separators:
            pos = search_window.rfind(sep)
            if pos != -1:
                best_end = search_window_start + pos + len(sep)
                found_separator = True
                break
                
        if not found_separator:
            best_end = end
            
        chunk_content = text[start:best_end].strip()
        if chunk_content:
            chunks.append((start, best_end, chunk_content))
            
        start = best_end - overlap
        if start >= best_end:
            start = best_end
            
    return chunks

def run_chunking():
    strategy_name = "recursive-1000-100"
#    pdf_path = os.path.join("files", "dit-course-guide.pdf")
    pdf_path = os.path.join("files", "odigos-spoudon-2023.pdf")
    chunk_size = 1000
    chunk_overlap = 100

    print(f"--- Strategy: {strategy_name} ---")
    
    try:
        print(f"Reading PDF and mapping pages: {pdf_path}...")
        raw_text, page_map = extract_text_and_pages(pdf_path)
        print(f"Total characters: {len(raw_text)}")

        print(f"Generating chunks...")
        chunks_info = chunk_text_recursive(raw_text, size=chunk_size, overlap=chunk_overlap)
        
        chunks_data = []
        for start_idx, end_idx, content in chunks_info:
            pages = get_pages_for_chunk(start_idx, end_idx, page_map)
            chunks_data.append({
                "content": content,
                "pages": pages
            })

        print(f"Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        source_name = os.path.basename(pdf_path)
        cur.execute("DELETE FROM chunks_recursive WHERE source = %s", (source_name,))
        
        for i, item in enumerate(chunks_data):
            if i % 10 == 0:
                print(f"Progress: {i}/{len(chunks_data)} chunks processed...")
            
            embedding = get_embedding(item["content"])
            
            metadata = {
                "pages": item["pages"],
                "chunk_index": i
            }
            
            sql = """
                INSERT INTO chunks_recursive (content, embedding, metadata, source)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(sql, (item["content"], embedding, json.dumps(metadata), os.path.basename(pdf_path)))
        
        conn.commit()
        print(f"\nSUCCESS: {len(chunks_data)} chunks stored in chunks_recursive.")

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f"\nAn error occurred: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    run_chunking()
