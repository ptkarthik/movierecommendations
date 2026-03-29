import sqlite3

def check_in():
    conn = sqlite3.connect('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db')
    cursor = conn.cursor()
    
    print("--- Movies with country 'IN' ---")
    cursor.execute("SELECT id, title, country, language FROM movies WHERE country = 'IN'")
    rows = cursor.fetchall()
    print(f"Total Found: {len(rows)}")
    for row in rows[:10]:
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_in()
