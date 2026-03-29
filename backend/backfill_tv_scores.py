import sqlite3
import time

def backfill_tv_scores():
    conn = sqlite3.connect('master_aligned.db', timeout=60)
    c = conn.cursor()
    
    try:
        # Create Temp Table for TV
        print("Creating temp_tv_scores...")
        c.execute("CREATE TEMP TABLE temp_tv_scores (id INTEGER PRIMARY KEY, score FLOAT)")
        
        # Populate Temp Table from TV Ratings
        print("Populating temp_tv_scores from tv_ratings...")
        c.execute("INSERT INTO temp_tv_scores (id, score) SELECT tv_id, quickflix_score FROM tv_ratings WHERE tv_id IS NOT NULL")
        
        # Perform Bulk Update
        print("Bulk updating tv_series table...")
        c.execute("""
            UPDATE tv_series 
            SET quickflix_score = (SELECT score FROM temp_tv_scores WHERE temp_tv_scores.id = tv_series.id) 
            WHERE EXISTS (SELECT 1 FROM temp_tv_scores WHERE temp_tv_scores.id = tv_series.id)
        """)
        
        conn.commit()
        print("TV Optimization Complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    start = time.time()
    backfill_tv_scores()
    print(f"Total time: {time.time() - start:.2f} seconds")
