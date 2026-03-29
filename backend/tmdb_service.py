import requests
import json
import subprocess
import logging
from config import settings

logger = logging.getLogger(__name__)

class TMDBService:
    BASE_URL = "http://api.themoviedb.org/3"

    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.session = requests.Session()

    def _make_request(self, url: str, params: dict):
        # Add API Key
        params["api_key"] = self.api_key
        
        # Construct full URL for curl fallback
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query_string}"
        
        logger.info(f"TMDB Request (curl fallback): {url}")
        
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Try subprocess curl with -4 -k for maximum reliability in this environment
                cmd = ["curl.exe", "-4", "-k", "-s", "-L", "--connect-timeout", "10", full_url]
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                
                if result.returncode == 0 and result.stdout:
                    try:
                        out_str = result.stdout.decode('utf-8', errors='ignore')
                        if not out_str:
                            if attempt < max_retries - 1: continue
                            logger.error("TMDB curl returned empty stdout")
                            return {}
                        data = json.loads(out_str)
                        if "status_code" in data and data["status_code"] != 1 and data["status_code"] != 34: # 34 is "Resource not found"
                            logger.error(f"TMDB API Error: {data.get('status_message')}")
                            return {}
                        return data
                    except Exception as parse_e:
                        if attempt < max_retries - 1: continue
                        logger.error(f"Failed to parse TMDB JSON: {parse_e} | Output: {result.stdout[:200]}")
                        return {}
                else:
                    if attempt < max_retries - 1:
                        time.sleep(1 * (attempt + 1))
                        continue
                    stderr_str = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No stderr"
                    logger.error(f"Curl failed with code {result.returncode} after {max_retries} attempts: {stderr_str}")
                    return {}
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                logger.error(f"TMDB curl fallback fatal error for {full_url}")
                return {}
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                logger.error(f"TMDB request crash for {full_url}: {e}")
                return {}
        return {}

    def search_movie(self, query: str):
        url = f"{self.BASE_URL}/search/movie"
        return self._make_request(url, {"query": query})

    def get_movie_details(self, tmdb_id: int):
        url = f"{self.BASE_URL}/movie/{tmdb_id}"
        return self._make_request(url, {"append_to_response": "credits,release_dates,videos,watch/providers"})

    def discover_movies(
        self,
        year: int = None,
        year_start: int = None,
        year_end: int = None,
        region: str = None,
        language: str = None,
        genre_id: int = None,
        sort_by: str = "primary_release_date.desc",
        page: int = 1
    ):
        url = f"{self.BASE_URL}/discover/movie"
        params = {
            "sort_by": sort_by,
            "vote_count.gte": 10,
            "vote_average.gte": 5.0,
            "page": page
        }
        if year: 
            params["primary_release_year"] = year
        elif year_start and year_end:
            params["primary_release_date.gte"] = f"{year_start}-01-01"
            params["primary_release_date.lte"] = f"{year_end}-12-31"
        elif year_start:
            params["primary_release_date.gte"] = f"{year_start}-01-01"
        elif year_end:
            params["primary_release_date.lte"] = f"{year_end}-12-31"

        if region: params["with_origin_country"] = region
        if language: params["with_original_language"] = language
        if genre_id: params["with_genres"] = genre_id

        return self._make_request(url, params)

    def search_tv(self, query: str):
        url = f"{self.BASE_URL}/search/tv"
        return self._make_request(url, {"query": query})

    def get_tv_details(self, tmdb_id: int):
        url = f"{self.BASE_URL}/tv/{tmdb_id}"
        return self._make_request(url, {"append_to_response": "credits,videos,watch/providers"})

    def discover_tv(
        self,
        year: int = None,
        year_start: int = None,
        year_end: int = None,
        region: str = None,
        language: str = None,
        genre_id: int = None,
        sort_by: str = "first_air_date.desc",
        page: int = 1
    ):
        url = f"{self.BASE_URL}/discover/tv"
        params = {
            "sort_by": sort_by,
            "vote_count.gte": 5,
            "vote_average.gte": 5.0,
            "page": page
        }
        if year:
            params["first_air_date_year"] = year
        elif year_start and year_end:
            params["first_air_date.gte"] = f"{year_start}-01-01"
            params["first_air_date.lte"] = f"{year_end}-12-31"
        elif year_start:
            params["first_air_date.gte"] = f"{year_start}-01-01"
        elif year_end:
            params["first_air_date.lte"] = f"{year_end}-12-31"

        if region: params["with_origin_country"] = region
        if language: params["with_original_language"] = language
        if genre_id: params["with_genres"] = genre_id

        return self._make_request(url, params)
