import requests
import os
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")

def test_discover(region, language):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "sort_by": "vote_average.desc",
        "vote_count.gte": 50,
        "vote_average.gte": 6.0,
        "with_origin_country": region,
        "with_original_language": language
    }
    print(f"Testing TMDB Discover for {region}/{language}...")
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Total Results: {data.get('total_results')}")
            print(f"Results Count on Page: {len(data.get('results', []))}")
            for m in data.get('results', [])[:3]:
                print(f" - {m.get('title')} ({m.get('release_date')})")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    if not TMDB_API_KEY:
        print("TMDB_API_KEY not found in env.")
    else:
        test_discover("US", "en")
        test_discover("IN", "hi")
        test_discover("IT", "it")
