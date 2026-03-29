from tmdb_service import TMDBService
import json

service = TMDBService()
print("Testing TMDB Discovery...")
try:
    results = service.discover_movies()
    print(f"Count: {len(results.get('results', []))}")
    if results.get('results'):
        print(f"First result: {results['results'][0]['title']}")
    else:
        print("Empty results.")
except Exception as e:
    print(f"Error: {e}")
