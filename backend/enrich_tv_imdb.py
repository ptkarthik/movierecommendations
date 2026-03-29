import os
import sys
import json
import subprocess
import requests
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.append(os.getcwd())

from models import TVSeries, TVRating
from config import settings
from tmdb_service import TMDBService

def fetch_omdb_tv_rating(imdb_id):
    if not settings.OMDB_API_KEY or not imdb_id:
        return None
    
    omdb_url = f"http://www.omdbapi.com/?apikey={settings.OMDB_API_KEY}&i={imdb_id}&type=series"
    try:
        # Use curl to avoid IPv6 issues
        cmd = ["curl.exe", "-4", "-k", "-s", "-L", omdb_url]
        res = subprocess.run(cmd, capture_output=True, timeout=10)
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout.decode('utf-8'))
            if data.get('Response') == 'True':
                val = data.get('imdbRating', 'N/A')
                return float(val) if val != 'N/A' else None
    except:
        pass
    return None

def enrich_tv_imdb():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    tmdb = TMDBService()
    
    print("Enriching top 200 TV Series with real IMDb ratings...")
    # Fetch most popular items that don't have real IMDb info (where we fallback to TMDB)
    # Filter for items where we want to verify real IMDb
    series = db.query(TVSeries).order_by(TVSeries.quickflix_score.desc()).limit(200).all()
    
    count = 0
    for s in series:
        rating = db.query(TVRating).filter(TVRating.tv_id == s.id).first()
        if not rating: continue
        
        # Get TMDB details to find external IMDb ID
        details = tmdb.get_tv_details(s.tmdb_id)
        imdb_id = details.get('external_ids', {}).get('imdb_id')
        
        if imdb_id:
            real_imdb = fetch_omdb_tv_rating(imdb_id)
            if real_imdb:
                rating.imdb_rating = real_imdb
                s.imdb_rating = real_imdb
                print(f"[*] '{s.title}': Found IMDb {real_imdb}")
                db.commit()
                count += 1
    
    db.close()
    print(f"Finished! Successfully enriched {count} TV series.")

if __name__ == "__main__":
    enrich_tv_imdb()
