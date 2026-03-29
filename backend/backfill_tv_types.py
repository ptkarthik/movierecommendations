import os
import sys
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.append(os.getcwd())

from models import TVSeries
from config import settings
from aggregation_service import DataAggregationService

def backfill_tv_types():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    agg = DataAggregationService(db)
    
    print("Backfilling TV series types for top 1000 items...")
    # Prioritize items with high scores or those already 'scripted'
    series = db.query(TVSeries).order_by(desc(TVSeries.quickflix_score)).limit(1000).all()
    
    count = 0
    for s in series:
        if not s.type:
            try:
                agg.light_enrichment_tv(s)
                print(f"[*] '{s.title}': Type={s.type}")
                count += 1
            except Exception as e:
                print(f"Error enriching {s.title}: {e}")
                
    print(f"Backfill complete! Updated {count} items.")
    db.close()

if __name__ == "__main__":
    backfill_tv_types()
