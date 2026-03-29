import requests
import os
import socket
from dotenv import load_dotenv
import urllib3.util.connection as uint_connection

# Force IPv4
def allowed_gai_family():
    return socket.AF_INET
uint_connection.allowed_gai_family = allowed_gai_family

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")

def test_discover(region, language, vote_count=50, vote_avg=6.0):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "sort_by": "popularity.desc",
        "with_origin_country": region,
        "with_original_language": language,
        "vote_count.gte": vote_count,
        "vote_average.gte": vote_avg
    }
        
    print(f"\nTesting TMDB Discover for {region}/{language} (Votes >= {vote_count}, Avg >= {vote_avg})...")
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            total = data.get('total_results', 0)
            print(f"Total Results: {total}")
            results = data.get('results', [])
            print(f"Results Count: {len(results)}")
            for m in results[:3]:
                print(f" - {m.get('title')} (Votes: {m.get('vote_count')}, Avg: {m.get('vote_average')})")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    if not TMDB_API_KEY:
        print("TMDB_API_KEY not found in env.")
    else:
        # Bollywood (IN, hi)
        test_discover("IN", "hi", 50, 6.0)
        test_discover("IN", "hi", 10, 5.0)
        test_discover("IN", "hi", 0, 0)
        # Hollywood (US, en)
        test_discover("US", "en", 50, 6.0)
