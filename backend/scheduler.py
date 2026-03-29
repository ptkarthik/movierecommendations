import time
import schedule
from database import SessionLocal
from aggregation_service import DataAggregationService

def daily_job():
    print("Running Proactive Film Intelligence Update...")
    db = SessionLocal()
    try:
        aggregator = DataAggregationService(db)
        
        # Proactively discover in different segments
        segments = [
            {"year": 2025}, # Upcoming/New
            {"language": "ko"}, # Korean
            {"language": "hi"}, # Bollywood
            {"region": "FR"}, # European (France)
        ]
        
        for seg in segments:
            print(f"Discovering for segment: {seg}")
            aggregator.discover_and_process_top_picks(**seg)
            
        print("Proactive update complete.")
    except Exception as e:
        print(f"Error during update: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # For demonstration, run once
    daily_job()
    
    # To keep running as a background worker:
    # Run every 2 hours as requested by the user
    schedule.every(2).hours.do(daily_job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
