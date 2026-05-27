import psycopg2
from config import DB_CONFIG
from utils import count_tokens

def run_evaluation():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
    except Exception as e:
        print(f"Connection error: {e}")
        return

    cur.execute("SELECT id, question, approx_page, question_embedding FROM qa_pairs ORDER BY id")
    qa_rows = cur.fetchall()

    if not qa_rows:
        print("No evaluation data found in qa_pairs table.")
        return

    total_questions = len(qa_rows)
    hits_at_1 = 0
    hits_at_5 = 0
    mrr_sum = 0
    errors = 0
    
    total_retrieved_tokens = 0
    total_retrieved_chunks = 0

    print(f"--- Evaluation: Structural Chunking ---")
    print(f"Total questions to test: {total_questions}\n")

    for idx, (qid, question, expected_page, q_emb) in enumerate(qa_rows):
        sql = """
            SELECT course_title, course_code, metadata->'pages' as pages, content
            FROM chunks_structural
            ORDER BY embedding <=> %s::vector
            LIMIT 5
        """
        try:
            cur.execute(sql, (q_emb,))
            results = cur.fetchall()
        except Exception as e:
            print(f"Search error for {qid}: {e}")
            errors += 1
            continue

        found_at_rank = 0
        combined_content = ""
        
        for rank, (title, code, pages, content) in enumerate(results, 1):
            combined_content += content + "\n\n"
            if found_at_rank == 0 and expected_page in pages:
                found_at_rank = rank
        
        # Token calculation for the combined Top-5 context
        tokens = count_tokens(combined_content)
        total_retrieved_tokens += tokens
        total_retrieved_chunks += len(results)

        if found_at_rank == 1:
            hits_at_1 += 1
        
        if found_at_rank > 0:
            hits_at_5 += 1
            mrr_sum += 1.0 / found_at_rank
        else:
            print(f"[X] {qid}: Not found in Top-5 (Expected page {expected_page})")
            
        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{total_questions} queries...")

    valid_questions = total_questions - errors
    if valid_questions > 0:
        top1_rate = (hits_at_1 / valid_questions) * 100
        top5_rate = (hits_at_5 / valid_questions) * 100
        mrr = mrr_sum / valid_questions
        
        avg_tokens_per_chunk = total_retrieved_tokens / total_retrieved_chunks if total_retrieved_chunks > 0 else 0
        avg_context_load = total_retrieved_tokens / valid_questions if valid_questions > 0 else 0

        print("\n" + "="*45)
        print(" RETRIEVAL PERFORMANCE & METRICS SUMMARY")
        print(" Strategy: Structural (1 Chunk = 1 Course)")
        print("="*45)
        print(f" Top-1 Hit Rate:       {top1_rate:>8.2f}%")
        print(f" Top-5 Hit Rate:       {top5_rate:>8.2f}%")
        print(f" MRR:                  {mrr:>8.3f}")
        print("-" * 45)
        print(f" Avg Tokens / Chunk:   {avg_tokens_per_chunk:>8.0f} tokens")
        print(f" Avg Context Load:     {avg_context_load:>8.0f} tokens/query")
        print("="*45)
        print(f" (Tested on {valid_questions} questions)")
    else:
        print("Evaluation failed or no valid questions processed.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    run_evaluation()
