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
    print("Starting process_movie for Parasite...")
    movie = service.process_movie("Parasite", 2019)
    if movie:
        print(f"SUCCESS: Processed {movie.title}")
    else:
        print("FAILED: process_movie returned None")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
