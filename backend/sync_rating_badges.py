import sqlite3

def sync_rating_badges():
    conn = sqlite3.connect('master_aligned.db', timeout=60)
    c = conn.cursor()
    
    try:
        # Sync the 'rating' column that the UI uses
        print("Syncing Movie rating badges...")
        c.execute("""
            UPDATE ratings 
            SET imdb_rating = tmdb_rating 
            WHERE (imdb_rating IS NULL OR imdb_rating = 0.0)
            AND tmdb_rating > 0
        """)
        print(f"Movie ratings updated: {c.rowcount}")

        print("Syncing TV rating badges...")
        c.execute("""
            UPDATE tv_ratings 
            SET imdb_rating = tmdb_rating 
            WHERE (imdb_rating IS NULL OR imdb_rating = 0.0)
            AND tmdb_rating > 0
        """)
        print(f"TV ratings updated: {c.rowcount}")
        
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    sync_rating_badges()
