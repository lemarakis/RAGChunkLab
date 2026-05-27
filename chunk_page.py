import os
import json
import psycopg2
import psycopg2.extras
import fitz  # PyMuPDF
from config import DB_CONFIG
from utils import get_embedding



def extract_pages(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at {pdf_path}")
        
    doc = fitz.open(pdf_path)
    pages_data = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():
            pages_data.append({
                "content": text,
                "page_num": page_num + 1
            })
    doc.close()
    return pages_data

def run_chunking():
#    pdf_path = os.path.join("files", "dit-course-guide.pdf")
    pdf_path = os.path.join("files", "odigos-spoudon-2023.pdf")
    strategy_name = "page-based"

    print(f"--- Strategy: {strategy_name} ---")
    
    try:
        # 1. Extract text page by page
        print(f"Reading PDF: {pdf_path}...")
        pages_data = extract_pages(pdf_path)
        print(f"Total pages with text: {len(pages_data)}")

        # 2. Connect to DB
        print(f"Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 3. Process and store
        source_name = os.path.basename(pdf_path)
        cur.execute("DELETE FROM chunks_page WHERE source = %s", (source_name,))
        
        for i, item in enumerate(pages_data):
            if i % 5 == 0:
                print(f"Progress: {i}/{len(pages_data)} pages processed...")
            
            # Generate embedding
            embedding = get_embedding(item["content"])
            
            # Metadata with pages
            metadata = {
                "pages": [item["page_num"]],
                "chunk_index": i
            }
            
            sql = """
                INSERT INTO chunks_page (content, embedding, metadata, source)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(sql, (item["content"], embedding, json.dumps(metadata), source_name))
        
        conn.commit()
        print(f"\nSUCCESS: {len(pages_data)} pages stored in chunks_page.")

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f"\nAn error occurred: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    run_chunking()
