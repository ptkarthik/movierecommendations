import requests

BASE_URL = "http://127.0.0.1:8558"

def test_movies_range(start, end):
    print(f"Testing range: {start} to {end}")
    response = requests.get(f"{BASE_URL}/movies?year_start={start}&year_end={end}")
    if response.status_code == 200:
        data = response.json()
        movies = data.get("movies", [])
        print(f"  Found {len(movies)} movies out of {data.get('total', 0)} total.")
        for m in movies[:5]:
            print(f"    - {m['title']} ({m['year']})")
        
        # Verify no movie is outside the range
        outside = [m for m in movies if m['year'] < start or m['year'] > end]
        if outside:
            print(f"  FAILED: Found movies outside range: {[f'{m.title} ({m.year})' for m in outside]}")
        else:
            print("  SUCCESS: All movies within range.")
    else:
        print(f"  FAILED: Status code {response.status_code}")

def test_movies_single(year):
    print(f"Testing single year: {year}")
    response = requests.get(f"{BASE_URL}/movies?year={year}")
    if response.status_code == 200:
        data = response.json()
        movies = data.get("movies", [])
        print(f"  Found {len(movies)} movies.")
        outside = [m for m in movies if m['year'] != year]
        if outside:
            print(f"  FAILED: Found movies with different years: {[f'{m.title} ({m.year})' for m in outside]}")
        else:
            print("  SUCCESS: All movies match year.")
    else:
        print(f"  FAILED: Status code {response.status_code}")

if __name__ == "__main__":
    try:
        test_movies_range(2000, 2010)
        test_movies_range(2020, 2025)
        test_movies_single(2024)
    except Exception as e:
        print(f"Error connecting to backend: {e}")
