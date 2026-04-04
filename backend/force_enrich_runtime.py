import os
import sys
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.append(os.getcwd())

from models import Movie
from config import settings
from aggregation_service import DataAggregationService

def force_enrich_top():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    agg = DataAggregationService(db)
    
    print("Forcing enrichment for top 50 movies to ensure runtimes...")
    # These are likely the ones the user sees first
    movies = db.query(Movie).order_by(desc(Movie.quickflix_score)).limit(50).all()
    
    for m in movies:
        print(f"[*] Checking '{m.title}' (runtime={m.runtime})...")
        try:
            agg.light_enrichment(m)
            print(f"    -> Updated Runtime: {m.runtime}m")
        except Exception as e:
            print(f"    Error: {e}")
            
    db.commit()
    db.close()

if __name__ == "__main__":
    force_enrich_top()
