import sqlite3
import os

db_path = r'c:\Users\Karthik\.gemini\antigravity\scratch\global-movie-intelligence\backend\master_aligned.db'

def analyze_db():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total count
    cursor.execute("SELECT COUNT(*) FROM movies")
    total = cursor.fetchone()[0]
    print(f"Total Movies: {total}")
    
    # Counts by country
    print("\nMovies by Country:")
    cursor.execute("SELECT country, COUNT(*) FROM movies GROUP BY country ORDER BY COUNT(*) DESC")
    for row in cursor.fetchall():
        print(f" - {row[0] or 'UNKNOWN'}: {row[1]}")
        
    # Counts by language
    print("\nMovies by Language:")
    cursor.execute("SELECT language, COUNT(*) FROM movies GROUP BY language ORDER BY COUNT(*) DESC")
    for row in cursor.fetchall():
        print(f" - {row[0] or 'UNKNOWN'}: {row[1]}")
            
    conn.close()

if __name__ == "__main__":
    analyze_db()
