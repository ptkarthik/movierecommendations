import sqlite3
import os

def check_ratings():
    db_path = 'c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db'
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    output_file = 'c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/ratings_dump.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("--- Recent Movies and their Ratings ---\n")
        query = """
        SELECT m.id, m.title, m.year, r.imdb_rating, r.rotten_critics, r.tmdb_rating, r.quickflix_score
        FROM movies m
        LEFT JOIN ratings r ON m.id = r.movie_id
        ORDER BY m.id DESC
        LIMIT 50
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            line = f"ID: {row['id']} | Title: {row['title']} ({row['year']}) | IMDb: {row['imdb_rating']} | RT: {row['rotten_critics']} | TMDB: {row['tmdb_rating']} | Score: {row['quickflix_score']}\n"
            f.write(line)
            
    conn.close()
    print(f"Results written to {output_file}")

if __name__ == "__main__":
    check_ratings()
