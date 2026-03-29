import requests
import json
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

def test_mx(vote_count, vote_avg):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "sort_by": "popularity.desc",
        "with_origin_country": "MX",
        "with_original_language": "es",
        "vote_count.gte": vote_count,
        "vote_average.gte": vote_avg
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    full_url = f"{url}?{query_string}"
    
    print(f"\nTesting MX/es (Votes >= {vote_count}, Avg >= {vote_avg})")
    cmd = ["curl.exe", "-4", "-k", "-s", full_url]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode == 0:
        data = json.loads(res.stdout.decode('utf-8'))
        print(f"Total Results: {data.get('total_results', 0)}")
        for m in data.get('results', [])[:3]:
            print(f" - {m.get('title')} (Votes: {m.get('vote_count')}, Avg: {m.get('vote_average')})")
    else:
        print(f"Error: {res.stderr}")

if __name__ == "__main__":
    test_mx(10, 5.0)
    test_mx(0, 0)
