import json
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

class TMDBServiceTest:
    BASE_URL = "https://api.themoviedb.org/3"

    def _make_request(self, url: str, params: dict):
        params["api_key"] = TMDB_API_KEY
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query_string}"
        
        print(f"DEBUG: Internal URL: {full_url}")
        
        try:
            cmd = ["curl.exe", "-4", "-s", full_url]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            print(f"DEBUG: Result returncode: {result.returncode}")
            if result.returncode == 0:
                decoded_out = result.stdout.decode('utf-8')
                print(f"DEBUG: Output snippet: {decoded_out[:200]}")
                data = json.loads(decoded_out)
                return data
            else:
                print(f"DEBUG: Curl Error: {result.stderr}")
                return {}
        except Exception as e:
            print(f"DEBUG: Exception: {e}")
            return {}

    def discover_movies(
        self,
        year: int = None,
        region: str = None,
        language: str = None,
        genre_id: int = None,
        sort_by: str = "vote_average.desc"
    ):
        url = f"{self.BASE_URL}/discover/movie"
        params = {
            "sort_by": sort_by,
            "vote_count.gte": 10,
            "vote_average.gte": 5.0,
        }
        if year: params["primary_release_year"] = year
        if region: params["with_origin_country"] = region
        if language: params["with_original_language"] = language
        if genre_id: params["with_genres"] = genre_id

        return self._make_request(url, params)

if __name__ == "__main__":
    svc = TMDBServiceTest()
    res = svc.discover_movies(region="IN", language="hi")
    print(f"\nFinal Total Results: {res.get('total_results', 'NOT FOUND')}")
