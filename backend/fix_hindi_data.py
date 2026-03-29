import sqlite3

def fix_hindi():
    conn = sqlite3.connect('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db')
    cursor = conn.cursor()
    
    print("Fixing Hindi movies...")
    cursor.execute("UPDATE movies SET country = 'IN' WHERE language = 'hi' AND country IS NULL")
    count = conn.total_changes
    print(f"Updated {count} movies.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_hindi()
