import sqlite3
import time

def migrate_imdb_column():
    conn = sqlite3.connect('master_aligned.db', timeout=60)
    c = conn.cursor()
    
    try:
        # Add column to movies
        print("Adding imdb_rating to movies...")
        try:
            c.execute("ALTER TABLE movies ADD COLUMN imdb_rating FLOAT DEFAULT 0.0")
        except sqlite3.OperationalError:
            print("Column imdb_rating already exists in movies.")

        # Add column to tv_series
        print("Adding imdb_rating to tv_series...")
        try:
            c.execute("ALTER TABLE tv_series ADD COLUMN imdb_rating FLOAT DEFAULT 0.0")
        except sqlite3.OperationalError:
            print("Column imdb_rating already exists in tv_series.")

        # Create Indexes
        print("Creating indexes...")
        c.execute("CREATE INDEX IF NOT EXISTS idx_movies_imdb ON movies(imdb_rating)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tv_imdb ON tv_series(imdb_rating)")
        
        # Backfill Movies (Table is 'ratings')
        print("Backfilling movies.imdb_rating from 'ratings'...")
        c.execute("CREATE TEMP TABLE temp_movie_imdb (id INTEGER PRIMARY KEY, score FLOAT)")
        c.execute("INSERT INTO temp_movie_imdb (id, score) SELECT movie_id, imdb_rating FROM ratings WHERE movie_id IS NOT NULL")
        c.execute("""
            UPDATE movies 
            SET imdb_rating = (SELECT score FROM temp_movie_imdb WHERE temp_movie_imdb.id = movies.id) 
            WHERE EXISTS (SELECT 1 FROM temp_movie_imdb WHERE temp_movie_imdb.id = movies.id)
        """)

        # Backfill TV (Table is 'tv_ratings')
        print("Backfilling tv_series.imdb_rating from 'tv_ratings'...")
        c.execute("CREATE TEMP TABLE temp_tv_imdb (id INTEGER PRIMARY KEY, score FLOAT)")
        c.execute("INSERT INTO temp_tv_imdb (id, score) SELECT tv_id, imdb_rating FROM tv_ratings WHERE tv_id IS NOT NULL")
        c.execute("""
            UPDATE tv_series 
            SET imdb_rating = (SELECT score FROM temp_tv_imdb WHERE temp_tv_imdb.id = tv_series.id) 
            WHERE EXISTS (SELECT 1 FROM temp_tv_imdb WHERE temp_tv_imdb.id = tv_series.id)
        """)
        
        conn.commit()
        print("Migration and Backfill Complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_imdb_column()
