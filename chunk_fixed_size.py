import os
import json
import psycopg2
import psycopg2.extras
import fitz  # PyMuPDF
from config import DB_CONFIG
from utils import get_embedding, extract_text_and_pages, get_pages_for_chunk

def run_chunking():
#    pdf_path = os.path.join("files", "dit-course-guide.pdf")
    pdf_path = os.path.join("files", "odigos-spoudon-2023.pdf")
    chunk_size = 1000
    chunk_overlap = 100

    print(f"--- Strategy: fixed-size ---")
    
    try:
        print(f"Reading PDF: {pdf_path}...")
        raw_text, page_map = extract_text_and_pages(pdf_path)
        print(f"Total characters: {len(raw_text)}, Pages: {len(page_map)}")

        print(f"Generating chunks...")
        chunks_data = []
        start_idx = 0
        while start_idx < len(raw_text):
            end_idx = start_idx + chunk_size
            content = raw_text[start_idx:end_idx]
            
            if content.strip():
                pages = get_pages_for_chunk(start_idx, end_idx, page_map)
                chunks_data.append({
                    "content": content,
                    "pages": pages
                })
            
            start_idx = end_idx - chunk_overlap
            if start_idx >= end_idx: start_idx = end_idx # Prevent stall

        print(f"Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        source_name = os.path.basename(pdf_path)
        cur.execute("DELETE FROM chunks_fixed_size WHERE source = %s", (source_name,))
        
        for i, item in enumerate(chunks_data):
            if i % 10 == 0:
                print(f"Progress: {i}/{len(chunks_data)} chunks processed...")
            
            embedding = get_embedding(item["content"])
            
            metadata = {
                "pages": item["pages"],
                "chunk_index": i
            }
            
            sql = """
                INSERT INTO chunks_fixed_size (content, embedding, metadata, source)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(sql, (item["content"], embedding, json.dumps(metadata), os.path.basename(pdf_path)))
        
        conn.commit()
        print(f"\nSUCCESS: {len(chunks_data)} chunks stored with page metadata.")

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f"\nAn error occurred: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    run_chunking()
