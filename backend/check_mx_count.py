import sqlite3
import os

db_path = r'c:\Users\Karthik\.gemini\antigravity\scratch\global-movie-intelligence\backend\master_aligned.db'

def check_db():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM movies WHERE country = 'MX'")
    count = cursor.fetchone()[0]
    print(f"Movies with country 'MX': {count}")
    
    if count > 0:
        cursor.execute("SELECT title, language, country FROM movies WHERE country = 'MX' LIMIT 5")
        rows = cursor.fetchall()
        print("\nSample 'MX' movies:")
        for row in rows:
            print(f" - {row[0]} (Lang: {row[1]}, Country: {row[2]})")
            
    conn.close()

if __name__ == "__main__":
    check_db()
