from database import SessionLocal
from aggregation_service import DataAggregationService
import socket
import urllib3.util.connection as uint_connection

# Force IPv4
def allowed_gai_family():
    return socket.AF_INET

uint_connection.allowed_gai_family = allowed_gai_family

db = SessionLocal()
service = DataAggregationService(db)

try:
    print("Testing Aggregator Discovery (Top 3)...")
    results = service.discover_and_process_top_picks(limit=3)
    print(f"Count: {len(results)}")
    for r in results:
        print(f"Processed: {r.title}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
