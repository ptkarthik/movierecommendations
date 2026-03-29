import os
import sys
import socket
import urllib3.util.connection as uint_connection

# Force IPv4
def allowed_gai_family():
    return socket.AF_INET
uint_connection.allowed_gai_family = allowed_gai_family

# Add backend to path
sys.path.append('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend')

from models import Movie, Rating
from config import settings
from tmdb_service import TMDBService
from scoring_service import ScoringService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def force_update(movie_ids):
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    scoring = ScoringService()
    tmdb = TMDBService()
    
    for mid in movie_ids:
        movie = db.query(Movie).filter(Movie.id == mid).first()
        if not movie: continue
        
        print(f"[*] Force updating '{movie.title}' (ID: {mid})...")
        
        # Get latest TMDB data
        details = tmdb.get_movie_details(movie.tmdb_id)
        tmdb_avg = details.get('vote_average', 0.0) if details else 0.0
        popularity = details.get('popularity', 0.0) if details else 0.0
        
        rating = db.query(Rating).filter(Rating.movie_id == movie.id).first()
        if not rating:
            rating = Rating(movie_id=movie.id)
            db.add(rating)
        
        # New Standardized Logic: Use TMDB avg as fallback for internal logic
        effective_imdb = rating.imdb_rating if (rating.imdb_rating and rating.imdb_rating > 0) else tmdb_avg
        
        rating.tmdb_rating = tmdb_avg
        rating.quickflix_score = scoring.calculate_quickflix_score(
            imdb_rating=effective_imdb,
            rt_critics=rating.rotten_critics,
            tmdb_popularity=popularity
        )
        
        # Final safety
        if rating.quickflix_score == 0 and tmdb_avg > 0:
            rating.quickflix_score = tmdb_avg * 10.0
            
        print(f"  + New Score: {rating.quickflix_score} (TMDB: {tmdb_avg})")
        db.commit()
    
    db.close()

if __name__ == "__main__":
    # IDs from screenshot
    target_ids = [466971, 601384, 532671, 1168075] # Added some from previous check too
    force_update(target_ids)
