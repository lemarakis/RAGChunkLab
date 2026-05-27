import os
import json
import psycopg2
import google.generativeai as genai
from config import DB_CONFIG, EMBEDDING_MODEL, EMBEDDING_DIM

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_embedding(text):
    result = genai.embed_content(
        model=f"models/{EMBEDDING_MODEL}",
        content=text,
        task_type="retrieval_document",
        output_dimensionality=EMBEDDING_DIM
    )
    return result['embedding']

def run_import():
    # 1. Load the evaluation datasets
    files_to_import = [
        os.path.join("files", "dit_course_qa_eval.json"),
        os.path.join("files", "odigos_2023_qa_eval.json")
    ]
    
    qa_pairs = []
    for json_path in files_to_import:
        if os.path.exists(json_path):
            print(f"Loading evaluation dataset from {json_path}...")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                qa_pairs.extend(data.get("qa_pairs", []))
        else:
            print(f"Warning: File {json_path} not found.")

    if not qa_pairs:
        print("No QA pairs found to import.")
        return

    print(f"Total QA pairs to import: {len(qa_pairs)}")

    # 2. Connect to the db
    print(f"Connecting to database {DB_CONFIG['database']} at {DB_CONFIG['host']}...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
    except Exception as e:
        print(f"Connection error: {e}")
        return

    try:
        for item in qa_pairs:
            qid = item.get("id")
            question = item.get("question")
            answer = item.get("answer")
            
            print(f"Processing {qid}...")

            # Generate embeddings
            try:
                q_emb = get_embedding(question)
                a_emb = get_embedding(answer)
            except Exception as e:
                print(f"Error generating embedding for {qid}: {e}")
                continue

            # SQL Insert
            sql = """
                INSERT INTO qa_pairs (
                    id, question, answer, approx_page, 
                    question_embedding, answer_embedding, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    question = EXCLUDED.question,
                    answer = EXCLUDED.answer,
                    question_embedding = EXCLUDED.question_embedding,
                    answer_embedding = EXCLUDED.answer_embedding,
                    source = EXCLUDED.source,
                    updated_at = NOW();
            """
            
            cur.execute(sql, (
                qid, 
                question, 
                answer, 
                item.get("page"),
                q_emb, 
                a_emb, 
                item.get("source_pdf")
            ))

        # Commit
        conn.commit()
        print("\nSUCCESS: Dataset imported successfully.")

    except Exception as e:
        conn.rollback()
        print(f"Error during import: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_import()
