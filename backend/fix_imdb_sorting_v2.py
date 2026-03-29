import sqlite3
import time

def backfill_imdb_optimized():
    conn = sqlite3.connect('master_aligned.db', timeout=60)
    c = conn.cursor()
    
    try:
        # 1. Movies Optimization
        print("Movies: Creating temp mapping...")
        c.execute("CREATE TEMPORARY TABLE movie_mapping (id INTEGER PRIMARY KEY, score REAL)")
        c.execute("INSERT INTO movie_mapping (id, score) SELECT movie_id, tmdb_rating FROM ratings WHERE tmdb_rating > 0")
        
        print("Movies: Applying bulk update...")
        c.execute("""
            UPDATE movies 
            SET imdb_rating = (SELECT score FROM movie_mapping WHERE movie_mapping.id = movies.id)
            WHERE id IN (SELECT id FROM movie_mapping)
            AND (imdb_rating IS NULL OR imdb_rating = 0.0)
        """)
        print(f"Movies updated: {c.rowcount}")
        
        # 2. TV Optimization
        print("TV: Creating temp mapping...")
        c.execute("CREATE TEMPORARY TABLE tv_mapping (id INTEGER PRIMARY KEY, score REAL)")
        c.execute("INSERT INTO tv_mapping (id, score) SELECT tv_id, tmdb_rating FROM tv_ratings WHERE tmdb_rating > 0")
        
        print("TV: Applying bulk update...")
        c.execute("""
            UPDATE tv_series 
            SET imdb_rating = (SELECT score FROM tv_mapping WHERE tv_mapping.id = tv_series.id)
            WHERE id IN (SELECT id FROM tv_mapping)
            AND (imdb_rating IS NULL OR imdb_rating = 0.0)
        """)
        print(f"TV Series updated: {c.rowcount}")
        
        conn.commit()
        print("Optimized Backfill Complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    backfill_imdb_optimized()
