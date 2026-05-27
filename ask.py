import os
import sys
import psycopg2
import google.generativeai as genai
from config import DB_CONFIG, LLM_MODEL
from utils import get_embedding

def ask_question(question):
    try:
        # 1. Get embedding
        q_emb = get_embedding(question, task_type="retrieval_query")

        # 2. Connect to DB
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Vector search
        sql = """
            SELECT course_title, course_code, content, metadata->'pages' as pages, (embedding <=> %s::vector) AS distance, source 
            FROM chunks_structural
            ORDER BY distance ASC LIMIT 5
        """
        cur.execute(sql, (q_emb,))
        results = cur.fetchall()
        
    except Exception as e:
        print(f"Σφάλμα: {e}")
        return
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

    if not results:
        print("Δεν βρέθηκαν σχετικά μαθήματα στη βάση δεδομένων.")
        return

    # 3. Build Context and Sources
    context = ""
    sources = []
    for i, (title, code, content, pages, distance, source) in enumerate(results, 1):
        similarity = 1.0 - float(distance)
        pages_str = ", ".join(str(p) for p in pages) if pages else "Άγνωστη"
        
        context += f"--- [{i}] Μάθημα: {title} ({code}) ---\n{content}\n\n"
        sources.append(f"[{i}] {title} ({code}) | Αρχείο: {source} | Σελίδες: {pages_str} (Score: {similarity:.2f})")

    # 4. LLM Prompt
    prompt = f"""
Είσαι ένας έμπειρος βοηθός φοιτητών για τον Οδηγό Σπουδών.
Απάντησε στην ερώτηση χρησιμοποιώντας ΜΟΝΟ το "Context" που ακολουθεί.
Κάθε πηγή στο Context έχει έναν αριθμό σε αγκύλες, π.χ. [1]. 
Στην απάντησή σου, ΠΡΕΠΕΙ να βάζεις παραπομπές στο τέλος των προτάσεων χρησιμοποιώντας αυτούς τους αριθμούς, π.χ. [1].

Context:
{context}

Ερώτηση: {question}

Απάντηση:
"""
    
    try:
        model = genai.GenerativeModel(LLM_MODEL)
        response = model.generate_content(prompt)

        # 5. Output results
        print("\n" + "="*80)
        print(f"ΕΡΩΤΗΣΗ: {question}")
        print("="*80)
        print(response.text.strip())
        print("\n" + "-"*80)
        print("ΠΛΗΡΟΦΟΡΙΕΣ ΠΗΓΩΝ (PDF & ΣΕΛΙΔΕΣ):")
        for s in sources:
            print(s)
        print("="*80)

    except Exception as e:
        print(f"Σφάλμα Gemini: {e}")

if __name__ == "__main__":
    # dit-course-guide.pdf
    #query = "Πόσες μονάδες ECTS έχει το μάθημα της Εισαγωγής στην Πληροφορική;"
    #query = 'Ποιο είναι το eclass URL του μαθήματος "Μικροκύματα και κυματοδηγοί";'
    #query = 'Το μάθημα "Κατανεμημένη διαχείριση πληροφορίας" προσφέρεται σε φοιτητές Erasmus;'
    query = 'Πως εξετάζεται το μάθημα [κρυ];'
    #query = 'Σε ποιο μάθημα θα διδαχθώ αρχιτεκτονικές κυψελωτών συστημάτων και Τεχνικές βελτίωσης της απόδοσης ασύρματου συστήματος;'
    #query = 'Δώσε μου την βιβλιογραφία του [αρχ-τηλ-συσ] και το URL του eclass'
    
    # odigos-spoudon-2023.pdf
    #query = 'Δώσε μου τον κωδικό του μαθήματος "Οπτικοποίηση δεδομένων"'
    #query = 'Ποια μαθήματα έχουν στην βιβλιογραφία το "A playcentric approach to creating innovative games."?'
    #query = 'Δώσε μου την βιβλιογραφία του "ηλε-παι"?'
    #query = 'ποια είναι η βιβλιογραφία του "αν-περ-εφα-παι"?'
    #query = 'ποια μαθήματα ασχολούνται με "Internet of Things"?'
    #query = 'πως γίνεται η σξιολόγηση στο μάθημα "θε-κρυ-ασ";'
    #query = 'Πόσα ECTS δίνει το "Πολιτισμική πληροφορική" και πόσες ώρες διδάσκεται την εβδομάδα;'
    #query = 'Σε ποια μαθήματα θα ασχοληθώ με βάσεις δεδομένων (MySQL, SQLite);'


    ask_question(query)
