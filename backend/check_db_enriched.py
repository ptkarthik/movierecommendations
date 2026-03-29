import sqlite3

def check_enriched():
    conn = sqlite3.connect('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db')
    cursor = conn.cursor()
    
    print("--- Enriched Movie Samples ---")
    cursor.execute("SELECT id, title, country, language, genre FROM movies WHERE language IS NOT NULL LIMIT 10")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Summary of Languages ---")
    cursor.execute("SELECT language, COUNT(*) FROM movies WHERE language IS NOT NULL GROUP BY language")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Summary of Countries ---")
    cursor.execute("SELECT country, COUNT(*) FROM movies WHERE country IS NOT NULL GROUP BY country")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_enriched()
