import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.append(os.getcwd())

from models import Movie
from config import settings
from aggregation_service import DataAggregationService

def targeted_enrich():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    agg = DataAggregationService(db)
    
    titles = ['Love Untangled', 'A Melody to Remember', 'BTS: Yet to Come in Cinemas']
    print(f"Targeted enrichment for: {titles}")
    
    for title in titles:
        m = db.query(Movie).filter(Movie.title == title).first()
        if m:
            print(f"[*] Enriching '{title}'...")
            try:
                agg.light_enrichment(m)
                print(f"    -> Runtime: {m.runtime}m")
            except Exception as e:
                print(f"    Error: {e}")
        else:
            print(f"[!] '{title}' not found in DB.")
            
    db.commit()
    db.close()

if __name__ == "__main__":
    targeted_enrich()
