import sqlite3

def check_ratings():
    conn = sqlite3.connect('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Recent Movies and their Ratings ---")
    query = """
    SELECT m.id, m.title, m.year, r.imdb_rating, r.rotten_critics, r.tmdb_rating, r.quickflix_score
    FROM movies m
    LEFT JOIN ratings r ON m.id = r.movie_id
    ORDER BY m.id DESC
    LIMIT 20
    """
    cursor.execute(query)
    for row in cursor.fetchall():
        print(f"ID: {row['id']} | Title: {row['title']} ({row['year']}) | IMDb: {row['imdb_rating']} | RT: {row['rotten_critics']} | TMDB: {row['tmdb_rating']} | Score: {row['quickflix_score']}")
        
    conn.close()

if __name__ == "__main__":
    check_ratings()
