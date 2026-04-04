import os
import sys
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.append(os.getcwd())

from models import Movie
from config import settings
from aggregation_service import DataAggregationService

def backfill_movie_runtimes():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    agg = DataAggregationService(db)
    
    print("Backfilling movie runtimes for top 1000 items...")
    # Prioritize items with high quickflix_score or imdb_rating
    movies = db.query(Movie).order_by(desc(Movie.quickflix_score)).limit(1000).all()
    
    count = 0
    for m in movies:
        if not m.runtime or m.runtime <= 0:
            try:
                # Use light_enrichment to fetch basic details including runtime
                agg.light_enrichment(m)
                print(f"[*] '{m.title}': Runtime={m.runtime}m")
                count += 1
            except Exception as e:
                print(f"Error enriching {m.title}: {e}")
                
    print(f"Backfill complete! Updated {count} items.")
    db.close()

if __name__ == "__main__":
    backfill_movie_runtimes()
