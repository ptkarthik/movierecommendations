import sqlite3

def check_hindi():
    conn = sqlite3.connect('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db')
    cursor = conn.cursor()
    
    print("--- Hindi Movies ---")
    cursor.execute("SELECT id, title, country, language FROM movies WHERE language = 'hi' LIMIT 20")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_hindi()
