
import os
import sys
sys.path.append(os.getcwd())
from config import settings
from tmdb_service import TMDBService

def test():
    print(f"Testing TMDB API Key: {settings.TMDB_API_KEY[:5]}...{settings.TMDB_API_KEY[-5:]}")
    service = TMDBService()
    result = service.search_movie("Inception")
    if result.get("results"):
        print("SUCCESS: Search worked.")
        print(f"Found {len(result['results'])} results.")
    else:
        print(f"FAILURE: Search failed. Result: {result}")

    print("\nTesting Discover...")
    result = service.discover_movies(region="ES", language="es")
    if result.get("results"):
        print("SUCCESS: Discover worked.")
        print(f"Found {len(result['results'])} Spanish movies.")
    else:
        print(f"FAILURE: Discover failed. Result: {result}")

if __name__ == "__main__":
    test()
