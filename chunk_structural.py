import os
import re
import json
import psycopg2
import psycopg2.extras
import fitz  # PyMuPDF
from config import DB_CONFIG
from utils import get_embedding, extract_text_and_pages, get_pages_for_chunk

def chunk_text_structural(text):
    """
    Splits text based on the course description pattern:
    Line 1: Title
    Line 2: [course-code]
    """
    chunks = []
    
    # Regex to find: (start of line) (Title) \n ([code]) (end of line)
    pattern = re.compile(r'^([^\n]+)\n\[([α-ωa-zA-Z0-9\-]+)\]$', re.MULTILINE)
    
    matches = list(pattern.finditer(text))
    
    for i in range(len(matches)):
        match = matches[i]
        start_idx = match.start()
        
        if i < len(matches) - 1:
            end_idx = matches[i+1].start()
        else:
            end_idx = len(text)
            
        course_title = match.group(1).strip()
        course_code = match.group(2).strip()
        content = text[start_idx:end_idx].strip()
        
        chunks.append({
            "start_idx": start_idx,
            "end_idx": end_idx,
            "title": course_title,
            "code": course_code,
            "content": content
        })
        
    return chunks

def run_chunking():
    pdf_path = os.path.join("files", "dit-course-guide.pdf")

    print(f"--- Strategy: structural-courses ---")
    
    try:
        print(f"Reading PDF and mapping pages: {pdf_path}...")
        raw_text, page_map = extract_text_and_pages(pdf_path)

        print(f"Generating chunks based on document structure...")
        chunks_info = chunk_text_structural(raw_text)
        
        chunks_data = []
        for c in chunks_info:
            pages = get_pages_for_chunk(c["start_idx"], c["end_idx"], page_map)
            chunks_data.append({
                "title": c["title"],
                "code": c["code"],
                "content": c["content"],
                "pages": pages
            })

        print(f"Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        source_name = os.path.basename(pdf_path)
        cur.execute("DELETE FROM chunks_structural WHERE source = %s", (source_name,))
        
        for i, item in enumerate(chunks_data):
            print(f"Processing course {i+1}/{len(chunks_data)}: {item['code']}...", end="\r")
            
            embedding = get_embedding(item["content"])
            
            metadata = {
                "pages": item["pages"]
            }
            
            sql = """
                INSERT INTO chunks_structural (course_title, course_code, content, embedding, metadata, source)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (item["title"], item["code"], item["content"], embedding, json.dumps(metadata), os.path.basename(pdf_path)))
        
        conn.commit()
        print(f"\nSUCCESS: {len(chunks_data)} courses stored in chunks_structural.")

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f"\nAn error occurred: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    run_chunking()
