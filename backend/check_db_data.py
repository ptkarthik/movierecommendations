import sqlite3

def check_db():
    conn = sqlite3.connect('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db')
    cursor = conn.cursor()
    
    print("--- Movie Stats ---")
    cursor.execute("SELECT COUNT(*) FROM movies")
    print(f"Total Movies: {cursor.fetchone()[0]}")
    
    print("\n--- Last 5 Movies ---")
    cursor.execute("SELECT id, title, country, language, genre FROM movies ORDER BY id DESC LIMIT 5")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Movies with language 'hi' ---")
    cursor.execute("SELECT COUNT(*) FROM movies WHERE language = 'hi'")
    print(f"Count: {cursor.fetchone()[0]}")
    
    print("\n--- Diverse Countries ---")
    cursor.execute("SELECT country, COUNT(*) FROM movies GROUP BY country")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_db()
