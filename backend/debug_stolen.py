import sqlite3
import json

def debug_stolen():
    db_path = 'c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.id, m.title, m.tmdb_id, r.imdb_rating, r.rotten_critics, r.tmdb_rating, r.quickflix_score, rec.ai_summary
        FROM movies m
        LEFT JOIN ratings r ON m.id = r.movie_id
        LEFT JOIN recommendations rec ON m.id = rec.movie_id
        WHERE m.title LIKE '%Stolen%'
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    
    with open('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/stolen_debug.json', 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2)
    
    conn.close()
    print(f"Dumped {len(rows)} movies to stolen_debug.json")

if __name__ == "__main__":
    debug_stolen()
