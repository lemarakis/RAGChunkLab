import os
import re
import json
import psycopg2
import psycopg2.extras
import fitz  # PyMuPDF
from config import DB_CONFIG
from utils import get_embedding, extract_text_and_pages, get_pages_for_chunk

def clean_content(text):
    """
    Removes junk text
    """
    junk_patterns = [
        r"ΑΥΤΟΤΕΛΕΙΣ\s+ΔΙΔΑΚΤΙΚΕΣ\s+ΔΡΑΣΤΗΡΙΟΤΗΤΕΣ.*?πιστωτικών\s+μονάδων",
        r"Προσθέστε\s+σειρές\s+αν\s+χρειαστεί.*?στο\s+\(δ\)\.",
        r"Περιγράφονται\s+τα\s+μαθησιακά\s+αποτελέσματα.*?Μαθησιακών\s+Αποτελεσμάτων",
        r"Λαμβάνοντας\s+υπόψη\s+τις\s+γενικές\s+ικανότητες.*?Άλλες.*?[.\…\s]+",
        r"Περιγράφονται\s+αναλυτικά\s+ο\s+τρόπος\s+και.*?αρχές\s+του\s+ECTS",
        r"Περιγραφή\s+της\s+διαδικασίας\s+αξιολόγησης.*?προσβάσιμα\s+από\s+τους\s+φοιτητές[.\s\…]*",
        r"\(25\s+ώρες\s+φόρτου\s+εργασίας.*?πιστωτική\s+μονάδα\)"
    ]
    
    cleaned = text
    for pattern in junk_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)
    
    cleaned = " ".join(cleaned.split())
    
    return cleaned.strip()

def chunk_text_structural_v2(text):
    chunks = []
    
    pattern = re.compile(r'([^\n]+)\s*\n\(1\) ΓΕΝΙΚΑ')
    matches = list(pattern.finditer(text))
    
    for i in range(len(matches)):
        start_idx = matches[i].start(1) # Start of the title
        
        if i < len(matches) - 1:
            end_idx = matches[i+1].start(1)
        else:
            end_idx = len(text)
            
        course_title = matches[i].group(1).strip()
        raw_content = text[start_idx:end_idx].strip()
        
        content = clean_content(raw_content)
        
        code_match = re.search(r'ΚΩΔΙΚΟΣ ΜΑΘΗΜΑΤΟΣ[\s\n]*([^\s\n]+)', raw_content)
        course_code = code_match.group(1).strip() if code_match else 'UNKNOWN'
        
        chunks.append({
            "start_idx": start_idx,
            "end_idx": end_idx,
            "title": course_title,
            "code": course_code,
            "content": content
        })
        
    return chunks

import time

def run_chunking():
    pdf_path = os.path.join("files", "odigos-spoudon-2023.pdf")
    source_name = os.path.basename(pdf_path)

    print(f"--- Strategy: Structural (Format 2) ---")
    
    try:
        print(f"Reading PDF and mapping pages: {pdf_path}...")
        raw_text, page_map = extract_text_and_pages(pdf_path)

        print(f"Generating chunks based on V2 document structure...")
        chunks_info = chunk_text_structural_v2(raw_text)
        
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

        cur.execute("DELETE FROM chunks_structural WHERE source = %s", (source_name,))
        
        for i, item in enumerate(chunks_data):
            print(f"Processing course {i+1}/{len(chunks_data)}: {item['code']}...", end="\r")
            
            time.sleep(5.0)  # Avoid rate limiting
            embedding = get_embedding(item["content"])
            
            metadata = {
                "pages": item["pages"]
            }
            
            sql = """
                INSERT INTO chunks_structural (course_title, course_code, content, embedding, metadata, source)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (item["title"], item["code"], item["content"], embedding, json.dumps(metadata), source_name))
        
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
