import os
import sys
import json
import subprocess
import requests
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.append(os.getcwd())

import socket
import urllib3.util.connection as uint_connection

# Global Fix: Force IPv4 to avoid hangs in environments with broken IPv6
def allowed_gai_family():
    return socket.AF_INET

uint_connection.allowed_gai_family = allowed_gai_family

from models import Movie, Rating, Recommendation
from config import settings
from tmdb_service import TMDBService
from scoring_service import ScoringService

def test_omdb(imdb_id=None, title=None, year=None):
    if not settings.OMDB_API_KEY:
        return None, None
        
    omdb_url = ""
    if imdb_id:
        omdb_url = f"http://www.omdbapi.com/?apikey={settings.OMDB_API_KEY}&i={imdb_id}"
    elif title:
        year_str = str(year) if year else ''
        omdb_url = f"http://www.omdbapi.com/?apikey={settings.OMDB_API_KEY}&t={requests.utils.quote(title)}&y={year_str}&type=movie"
    else:
        return None, None

    try:
        cmd = ["curl.exe", "-4", "-k", "-s", "-L", "--connect-timeout", "5", omdb_url]
        res = subprocess.run(cmd, capture_output=True, timeout=10)
        if res.returncode == 0 and res.stdout:
            odata = json.loads(res.stdout.decode('utf-8', errors='ignore'))
            if odata.get('Response') == 'True':
                imdb_val = odata.get('imdbRating', 'N/A')
                imdb_rating = float(imdb_val) if imdb_val != 'N/A' else None
                rt_critics = None
                for src in odata.get('Ratings', []):
                    if src['Source'] == 'Rotten Tomatoes':
                        rt_critics = float(src['Value'].replace('%', ''))
                return imdb_rating, rt_critics
            elif odata.get('Error') == 'Request limit reached!':
                print("  ! OMDb API: Request limit reached (Daily quota used).")
                return -1, -1 # Signal rate limit
    except Exception as e:
        print(f"Error calling OMDb: {e}")
    return None, None

def get_imdb_id(tmdb_id):
    svc = TMDBService()
    try:
        details = svc.get_movie_details(tmdb_id)
        if details:
            return details.get('imdb_id')
    except Exception as e:
        print(f"Error calling TMDB: {e}")
    return None

def enrich_existing():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    scoring = ScoringService()
    
    # Strictly limit to 300 for broader UI fix
    recs = db.query(Recommendation).order_by(desc(Recommendation.id)).limit(300).all()
    movie_ids = []
    seen = set()
    for r in recs:
        if r.movie_id not in seen:
            movie_ids.append(r.movie_id)
            seen.add(r.movie_id)
    
    fixing_count = 0
    limit_reached = False
    print(f"Checking {len(movie_ids)} most recent recommended movies...")
    
    for m_id in movie_ids:
        
        movie = db.query(Movie).filter(Movie.id == m_id).first()
        if not movie: continue
        
        rating = db.query(Rating).filter(Rating.movie_id == movie.id).first()
        if not rating:
            rating = Rating(movie_id=movie.id)
            db.add(rating)
            
        # Process all recent movies to ensure they have the new standardized score
        if True: # Always process
            print(f"[*] Updating rating for '{movie.title}'...")
            print(f"[*] Enriching '{movie.title}'...")
            
            # Ensure we have TMDB data at minimum
            tmdb_id = movie.tmdb_id
            imdb_id = get_imdb_id(tmdb_id)
            
            imdb_score, rt_score = None, None
            if not limit_reached:
                imdb_score, rt_score = test_omdb(imdb_id=imdb_id, title=movie.title, year=movie.year)
                if imdb_score == -1:
                    limit_reached = True
                    print("  ! OMDb limit reached. Falling back to TMDB for remaining records.")
                    imdb_score, rt_score = None, None

            if imdb_score:
                rating.imdb_rating = imdb_score
                print(f"  + IMDb: {imdb_score}")
            if rt_score:
                rating.rotten_critics = rt_score
                print(f"  + RT: {rt_score}%")
            
            # Always recalculate score using standardization
            # If IMDB is missing, use TMDB as fallback for internal logic
            effective_imdb = rating.imdb_rating if (rating.imdb_rating and rating.imdb_rating > 0) else rating.tmdb_rating

            rating.quickflix_score = scoring.calculate_quickflix_score(
                imdb_rating=effective_imdb,
                rt_critics=rating.rotten_critics,
                tmdb_popularity=0.0 # Unknown here
            )
            
            # Final fallback
            if rating.quickflix_score == 0 and rating.tmdb_rating:
                rating.quickflix_score = rating.tmdb_rating * 10.0
                
            db.commit()
            fixing_count += 1
            
    db.close()
    print(f"Batch enrichment complete. Fixed {fixing_count} records.")

if __name__ == "__main__":
    enrich_existing()
