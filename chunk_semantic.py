import os
import re
import json
import math
import psycopg2
import psycopg2.extras
import fitz  # PyMuPDF
from config import DB_CONFIG
from utils import get_embeddings_batch, extract_text_and_pages, get_pages_for_chunk, cosine_similarity

def run_chunking():
#    pdf_path = os.path.join("files", "dit-course-guide.pdf")
    pdf_path = os.path.join("files", "odigos-spoudon-2023.pdf")

    print(f"--- Strategy: semantic-similarity ---")
    
    try:
        # 1. Extract text
        print("Reading PDF...")
        raw_text, page_map = extract_text_and_pages(pdf_path)

        # 2. Split into Base Units (Sentences or small blocks)
        # We split by dot+space, or double newline
        print("Splitting into base semantic units...")
        pattern = re.compile(r'[^.?!]+[.?!]+(?=\s|$)|[^\n]+\n\n')
        
        base_units = []
        for match in pattern.finditer(raw_text):
            content = match.group().strip()
            if len(content) > 10:  # Ignore tiny artifacts
                base_units.append({
                    "start": match.start(),
                    "end": match.end(),
                    "content": content
                })
        
        if not base_units:
            print("Error parsing base units.")
            return

        print(f"Generated {len(base_units)} base units. Fetching embeddings...")

        # 3. Get embeddings for all base units in batches
        batch_size = 100
        for i in range(0, len(base_units), batch_size):
            batch = base_units[i:i+batch_size]
            texts = [u["content"] for u in batch]
            print(f"Embedding batch {i//batch_size + 1}/{(len(base_units)//batch_size)+1}...", end="\r")
            embs = get_embeddings_batch(texts)
            for j, u in enumerate(batch):
                u["embedding"] = embs[j]
        print("\nEmbeddings fetched.")

        # 4. Calculate similarities and group chunks
        print("Calculating semantic similarities to form chunks...")
        similarity_threshold = 0.65  # If similarity drops below this, we start a new chunk
        max_chunk_size = 1500        # Safety limit

        final_chunks = []
        current_chunk = {"start": base_units[0]["start"], "content": "", "units": []}

        for i in range(len(base_units)):
            unit = base_units[i]
            
            # If it's the first unit in the chunk, just add it
            if not current_chunk["content"]:
                current_chunk["content"] = unit["content"]
                current_chunk["units"].append(unit)
                continue
                
            # Compare current unit with the previous unit
            prev_unit = base_units[i-1]
            sim = cosine_similarity(unit["embedding"], prev_unit["embedding"])
            
            new_length = len(current_chunk["content"]) + len(unit["content"])
            
            # If similar enough and not too big, merge
            if sim >= similarity_threshold and new_length < max_chunk_size:
                current_chunk["content"] += " " + unit["content"]
                current_chunk["units"].append(unit)
            else:
                # Similarity dropped or too big -> Finalize chunk and start new
                current_chunk["end"] = prev_unit["end"]
                final_chunks.append(current_chunk)
                current_chunk = {"start": unit["start"], "content": unit["content"], "units": [unit]}
        
        # Add the last chunk
        if current_chunk["content"]:
            current_chunk["end"] = base_units[-1]["end"]
            final_chunks.append(current_chunk)

        print(f"Formed {len(final_chunks)} semantic chunks.")

        # 5. Store in DB
        print("Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        source_name = os.path.basename(pdf_path)
        cur.execute("DELETE FROM chunks_semantic WHERE source = %s", (source_name,))
        
        for i, chunk in enumerate(final_chunks):
            if (i + 1) % 10 == 0 or i == len(final_chunks) - 1:
                print(f"Saving chunk {i+1}/{len(final_chunks)}...")
            
            # Generate final embedding for the combined chunk
            chunk_embedding = get_embeddings_batch([chunk["content"]])[0]
            pages = get_pages_for_chunk(chunk["start"], chunk["end"], page_map)
            
            metadata = {
                "pages": pages,
                "base_units_count": len(chunk["units"])
            }
            
            sql = "INSERT INTO chunks_semantic (content, embedding, metadata, source) VALUES (%s, %s, %s, %s)"
            cur.execute(sql, (chunk["content"], chunk_embedding, json.dumps(metadata), os.path.basename(pdf_path)))
        
        conn.commit()
        print(f"\nSUCCESS: {len(final_chunks)} chunks stored.")

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f"\nAn error occurred: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    run_chunking()
