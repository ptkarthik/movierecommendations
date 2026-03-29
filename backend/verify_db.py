import sqlite3
import os

db_path = r"c:\Users\Karthik\.gemini\antigravity\scratch\global-movie-intelligence\backend\master_aligned.db"
if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT count(*) FROM movies")
        movie_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT count(*) FROM movies WHERE poster_path IS NOT NULL")
        enriched_count = cursor.fetchone()[0]
        
        print(f"Total Movies: {movie_count}")
        print(f"Enriched Movies: {enriched_count}")
        conn.close()
    except Exception as e:
        print(f"Error querying database: {e}")
