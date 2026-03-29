import json
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

def _make_request(url: str, params: dict):
    params["api_key"] = TMDB_API_KEY
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    full_url = f"{url}?{query_string}"
    
    print(f"URL: {full_url}")
    try:
        cmd = ["curl.exe", "-4", "-k", "-s", full_url]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        print(f"Returncode: {result.returncode}")
        print(f"Stdout type: {type(result.stdout)}")
        print(f"Stdout value: {result.stdout}")
        
        if result.returncode == 0:
            decoded = result.stdout.decode('utf-8')
            print(f"Decoded type: {type(decoded)}")
            print(f"Decoded value: {decoded[:100]}")
            data = json.loads(decoded)
            return data
        else:
            return {}
    except Exception as e:
        print(f"CAUGHT ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {}

if __name__ == "__main__":
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "sort_by": "vote_average.desc",
        "vote_count.gte": 10,
        "vote_average.gte": 5.0,
        "page": 1,
        "with_origin_country": "MX",
        "with_original_language": "es"
    }
    _make_request(url, params)
