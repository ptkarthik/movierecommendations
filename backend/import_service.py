import subprocess
import json
import gzip
import os
from datetime import datetime, timedelta
from sqlalchemy import text
from database import SessionLocal
from models import Movie

import threading
import time

class ImportService:
    _stats = {
        "total_seeded": 0,
        "total_enriched": 0,
        "is_running": False,
        "last_import_date": None,
        "current_batch_count": 0
    }

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()

    def fetch_tmdb_daily_ids(self, date_str=None):
        """
        Downloads and processes the TMDB daily movie ID export.
        URL Format: http://files.tmdb.org/p/exports/movie_ids_MM_DD_YYYY.json.gz
        """
        if not date_str:
            # Try yesterday's export as today's might not be ready
            date = datetime.now() - timedelta(days=1)
            date_str = date.strftime("%m_%d_%Y")

        filename = f"movie_ids_{date_str}.json.gz"
        url = f"http://files.tmdb.org/p/exports/{filename}"
        
        print(f"Starting bulk import for {date_str}...")
        
        try:
            # Download using curl.exe for speed and resilience
            subprocess.run(
                f'curl.exe -L -o "{filename}" "{url}"',
                shell=True, check=True, capture_output=True
            )
            
            if not os.path.exists(filename):
                return {"error": "Failed to download export file."}

            count = 0
            batch = []
            batch_size = 1000
            
            with gzip.open(filename, 'rt', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        tmdb_id = data.get('id')
                        title = data.get('original_title')
                        # Note: Export only contains id, adult, video, and original_title
                        # We seed with minimal data; enrichment happens on demand
                        
                        batch.append({
                            "tmdb_id": tmdb_id,
                            "title": title
                        })
                        
                        count += 1
                        if len(batch) >= batch_size:
                            self._batch_upsert(batch)
                            batch = []
                            if count % 10000 == 0:
                                print(f"Imported {count} movies...")
                                
                    except Exception as e:
                        continue
            
            # Final batch
            if batch:
                self._batch_upsert(batch)
                
            # Cleanup
            os.remove(filename)
            
            return {"status": "success", "count": count}
            
        except Exception as e:
            return {"error": f"Import failed: {str(e)}"}

    def fetch_tmdb_daily_tv_ids(self, date_str=None):
        """
        Downloads and processes the TMDB daily TV series ID export.
        URL Format: http://files.tmdb.org/p/exports/tv_series_ids_MM_DD_YYYY.json.gz
        """
        if not date_str:
            date = datetime.now() - timedelta(days=1)
            date_str = date.strftime("%m_%d_%Y")

        filename = f"tv_series_ids_{date_str}.json.gz"
        url = f"http://files.tmdb.org/p/exports/{filename}"
        
        print(f"Starting bulk TV import for {date_str}...")
        
        try:
            subprocess.run(
                f'curl.exe -L -o "{filename}" "{url}"',
                shell=True, check=True, capture_output=True
            )
            
            if not os.path.exists(filename):
                return {"error": "Failed to download TV export file."}

            count = 0
            batch = []
            batch_size = 1000
            
            with gzip.open(filename, 'rt', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        tmdb_id = data.get('id')
                        title = data.get('original_name')
                        
                        batch.append({
                            "tmdb_id": tmdb_id,
                            "title": title
                        })
                        
                        count += 1
                        if len(batch) >= batch_size:
                            self._batch_upsert_tv(batch)
                            batch = []
                    except:
                        continue
            
            if batch:
                self._batch_upsert_tv(batch)
                
            os.remove(filename)
            return {"status": "success", "count": count}
        except Exception as e:
            return {"error": f"TV Import failed: {str(e)}"}

    def start_infinite_ingest(self):
        """
        Launches the ingestion worker in a background thread.
        """
        if ImportService._stats["is_running"]:
            return {"message": "Worker already running"}
            
        thread = threading.Thread(target=self._ingest_worker_loop, daemon=True)
        thread.start()
        ImportService._stats["is_running"] = True
        return {"message": "Infinite Ingest Worker started"}

    def _ingest_worker_loop(self):
        """
        Continuous loop to check for and process TMDB exports.
        """
        while True:
            try:
                date_str = datetime.now().strftime("%m_%d_%Y")
                if ImportService._stats["last_import_date"] != date_str:
                    print(f"Worker: Starting daily import for {date_str}...")
                    m_result = self.fetch_tmdb_daily_ids(date_str)
                    tv_result = self.fetch_tmdb_daily_tv_ids(date_str)
                    
                    if "status" in m_result:
                        ImportService._stats["last_import_date"] = date_str
                        ImportService._stats["total_seeded"] += m_result["count"]
                    if "status" in tv_result:
                        ImportService._stats["total_seeded"] += tv_result["count"]
                
                # Sleep between checks (e.g., 6 hours)
                time.sleep(21600)
            except Exception as e:
                print(f"Worker Error: {e}")
                time.sleep(3600)

    @classmethod
    def get_stats(cls, db_session):
        """
        Returns real-time ingestion and enrichment statistics for movies and TV.
        """
        from models import Movie, TVSeries
        total_movies = db_session.query(Movie).count()
        enriched_movies = db_session.query(Movie).filter(Movie.poster_path != None).count()
        
        total_tv = db_session.query(TVSeries).count()
        enriched_tv = db_session.query(TVSeries).filter(TVSeries.poster_path != None).count()
        
        total_all = total_movies + total_tv
        enriched_all = enriched_movies + enriched_tv
        
        return {
            "total_movies": total_movies,
            "enriched_movies": enriched_movies,
            "total_tv": total_tv,
            "enriched_tv": enriched_tv,
            "is_ingesting": cls._stats["is_running"],
            "last_import": cls._stats["last_import_date"],
            "global_intelligence_depth": f"{round((enriched_all/max(total_all, 1))*100, 1)}%"
        }

    def _batch_upsert(self, movies_data):
        """
        Perform a batch upsert (INSERT OR IGNORE for SQLite).
        """
        # SQLite specific: INSERT OR IGNORE
        stmt = text("""
            INSERT OR IGNORE INTO movies (tmdb_id, title)
            VALUES (:tmdb_id, :title)
        """)
        try:
            self.db.execute(stmt, movies_data)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Batch upsert error: {e}")

    def _batch_upsert_tv(self, tv_data):
        """
        Perform a batch upsert for TV series.
        """
        stmt = text("""
            INSERT OR IGNORE INTO tv_series (tmdb_id, title)
            VALUES (:tmdb_id, :title)
        """)
        try:
            self.db.execute(stmt, tv_data)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Batch upsert (TV) error: {e}")

if __name__ == "__main__":
    # Test with a small subset if run directly
    service = ImportService()
    # result = service.fetch_tmdb_daily_ids()
    # print(result)
