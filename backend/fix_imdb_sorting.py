import sqlite3
import time

def backfill_imdb_fallbacks():
    conn = sqlite3.connect('master_aligned.db', timeout=60)
    c = conn.cursor()
    
    try:
        # 1. Backfill Movies
        print("Backfilling Movie IMDb ratings with TMDB fallbacks...")
        # Join with ratings table to get tmdb_rating where imdb_rating is missing
        c.execute("""
            UPDATE movies 
            SET imdb_rating = (
                SELECT tmdb_rating FROM ratings WHERE ratings.movie_id = movies.id
            )
            WHERE (imdb_rating IS NULL OR imdb_rating = 0.0)
            AND EXISTS (SELECT 1 FROM ratings WHERE ratings.movie_id = movies.id AND tmdb_rating > 0)
        """)
        print(f"Movies updated: {c.rowcount}")

        # 2. Backfill TV
        print("Backfilling TV IMDb ratings with TMDB fallbacks...")
        c.execute("""
            UPDATE tv_series 
            SET imdb_rating = (
                SELECT tmdb_rating FROM tv_ratings WHERE tv_ratings.tv_id = tv_series.id
            )
            WHERE (imdb_rating IS NULL OR imdb_rating = 0.0)
            AND EXISTS (SELECT 1 FROM tv_ratings WHERE tv_ratings.tv_id = tv_series.id AND tmdb_rating > 0)
        """)
        print(f"TV Series updated: {c.rowcount}")
        
        conn.commit()
        print("Backfill Complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    backfill_imdb_fallbacks()
