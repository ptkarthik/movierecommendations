import socket
import urllib3
import urllib3.util.connection as uint_connection
import logging

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Global Fix: Force IPv4 to avoid hangs in environments with broken IPv6
def allowed_gai_family():
    return socket.AF_INET

uint_connection.allowed_gai_family = allowed_gai_family

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from typing import List

from database import SessionLocal, engine, get_db
from models import Base, Movie, Recommendation, Rating, TVSeries, TVRating, TVRecommendation
from tmdb_service import TMDBService
from gemini_service import GeminiService
from aggregation_service import DataAggregationService
from config import settings
from scoring_service import ScoringService
from import_service import ImportService
from pydantic import BaseModel
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

COUNTRY_MAP = {
    'US': 'United States of America', 'GB': 'United Kingdom', 'IN': 'India', 'KR': 'South Korea',
    'JP': 'Japan', 'FR': 'France', 'ES': 'Spain', 'IT': 'Italy', 'DE': 'Germany',
    'CN': 'China', 'NG': 'Nigeria', 'EG': 'Egypt', 'TR': 'Turkey', 'BR': 'Brazil',
    'MX': 'Mexico', 'CA': 'Canada', 'AU': 'Australia', 'HK': 'Hong Kong', 'TW': 'Taiwan',
    'TH': 'Thailand', 'VN': 'Vietnam', 'PH': 'Philippines', 'ID': 'Indonesia',
    'IR': 'Iran', 'SA': 'Saudi Arabia', 'IL': 'Israel', 'ZA': 'South Africa',
    'GH': 'Ghana', 'PL': 'Poland', 'RO': 'Romania', 'CZ': 'Czech Republic',
    'HU': 'Hungary', 'DK': 'Denmark', 'SE': 'Sweden', 'NO': 'Norway', 'FI': 'Finland',
    'AR': 'Argentina', 'CO': 'Colombia', 'CL': 'Chile', 'PK': 'Pakistan', 'BD': 'Bangladesh',
    'BE': 'Belgium', 'NL': 'Netherlands', 'PT': 'Portugal', 'GR': 'Greece',
    'RU': 'Russia', 'UA': 'Ukraine', 'IE': 'Ireland', 'NZ': 'New Zealand',
}


class UserRating(BaseModel):
    rating: float

# Initialize DB
Base.metadata.create_all(bind=engine)

app = FastAPI(title="QuickFlix4U - Global Movie Intelligence")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """
    Infinite Ingest Worker can be triggered manually via admin endpoints if needed.
    Disabled by default on startup to ensure interactive scan stability.
    """
    # service = ImportService()
    # service.start_infinite_ingest()
    pass


# ── Global background scan state ──────────────────────────────────────────────
import threading, time as _time

_scan_lock = threading.Lock()
_scan_state: dict = {
    "active": False,
    "region": None,
    "scanned": 0,
    "total_pages": None,
    "current_page": 0,
    "error": None,
    "type": "movie" # "movie" or "tv"
}


def _run_full_scan_bg(year, region, language, genre_id, year_start=None, year_end=None):
    """Background thread: pages through ALL TMDB results until exhausted."""
    global _scan_state
    from database import SessionLocal

    with _scan_lock:
        _scan_state.update({
            "active": True, "region": region, "scanned": 0,
            "total_pages": None, "current_page": 0, "error": None
        })

    aggregator = DataAggregationService(None)
    
    from concurrent.futures import ThreadPoolExecutor
    stop_event = threading.Event()
    
    def process_page_batch(current_page):
        if stop_event.is_set(): return {"new": 0, "total": 0}
        page_db = SessionLocal()
        try:
            svc = DataAggregationService(page_db)
            discovery = svc.tmdb.discover_movies(
                year=year, region=region, language=language,
                genre_id=genre_id, page=current_page,
                year_start=year_start, year_end=year_end
            )
            if not discovery or not discovery.get('results'):
                return {"new": 0, "total": 0}
            
            new_count = 0
            for mv in discovery['results']:
                if svc.quick_ingest_movie(mv, region=region):
                    new_count += 1
            
            # Incremental logic: if a page has 0 new movies, it might be the "end" of the delta
            return {"new": new_count, "total": len(discovery['results'])}
        except Exception as e:
            print(f"Error processing page {current_page}: {e}")
            return {"new": 0, "total": 0}
        finally:
            page_db.close()

    try:
        # First page to get total_pages
        first_page = aggregator.tmdb.discover_movies(
            year=year, region=region, language=language,
            genre_id=genre_id, page=1,
            year_start=year_start, year_end=year_end
        )
        total_pages = 1 # Default to 1 page if no results
        if first_page:
            total_pages = min(first_page.get("total_pages", 1), 500)
            with _scan_lock: _scan_state["total_pages"] = total_pages
        
        consecutive_duplicates = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            # We process pages in order to stop early
            for p in range(1, total_pages + 1):
                if stop_event.is_set(): break
                
                future = executor.submit(process_page_batch, p)
                res = future.result()
                
                with _scan_lock:
                    _scan_state["current_page"] = p
                    _scan_state["scanned"] += res["total"]
                
                if res["new"] == 0 and res["total"] > 0:
                    consecutive_duplicates += 1
                else:
                    consecutive_duplicates = 0
                
                # If we see 3 pages (60 movies) of 100% duplicates, stop scanning historical data
                if consecutive_duplicates >= 3:
                    print(f"Incremental Scan: Reached historical data at page {p}. Stopping.", flush=True)
                    stop_event.set()
                    break

    except Exception as e:
        import traceback
        print(f"Scan Thread Crashed: {traceback.format_exc()}", flush=True)
        with _scan_lock: _scan_state["error"] = str(e)
    finally:
        with _scan_lock: _scan_state["active"] = False

def _run_tv_scan_bg(year, region, language, genre_id, year_start=None, year_end=None):
    """Background thread for TV discovery."""
    global _scan_state
    from database import SessionLocal

    with _scan_lock:
        _scan_state.update({
            "active": True, "region": region, "scanned": 0,
            "total_pages": None, "current_page": 0, "error": None, "type": "tv"
        })

    aggregator = DataAggregationService(None)
    from concurrent.futures import ThreadPoolExecutor
    stop_event = threading.Event()

    def process_tv_page(p):
        if stop_event.is_set(): return {"new": 0, "total": 0}
        db = SessionLocal()
        try:
            svc = DataAggregationService(db)
            res = svc.tmdb.discover_tv(year=year, region=region, language=language, genre_id=genre_id, page=p, year_start=year_start, year_end=year_end)
            if not res or not res.get('results'): return {"new": 0, "total": 0}
            new_count = 0
            for show in res['results']:
                if svc.quick_ingest_tv(show, region=region):
                    new_count += 1
            return {"new": new_count, "total": len(res['results'])}
        except Exception as e:
            print(f"TV Scan Page {p} Error: {e}")
            return {"new": 0, "total": 0}
        finally: db.close()

    try:
        first = aggregator.tmdb.discover_tv(year=year, region=region, language=language, genre_id=genre_id, page=1, year_start=year_start, year_end=year_end)
        tp = 1 # Default to 1 page if no results
        if first:
            tp = min(first.get("total_pages", 1), 500)
            with _scan_lock: _scan_state["total_pages"] = tp
            consecutive_duplicates = 0
            with ThreadPoolExecutor(max_workers=5) as ex:
                for p in range(1, tp + 1):
                    if stop_event.is_set(): break
                    fut = ex.submit(process_tv_page, p)
                    res = fut.result()
                    with _scan_lock:
                        _scan_state["current_page"] = p
                        _scan_state["scanned"] += res["total"]
                    
                    if res["new"] == 0 and res["total"] > 0:
                        consecutive_duplicates += 1
                    else:
                        consecutive_duplicates = 0
                    
                    if consecutive_duplicates >= 3:
                        print(f"Incremental TV Scan: Reached historical data at page {p}. Stopping.", flush=True)
                        stop_event.set()
                        break
    except Exception as e:
        with _scan_lock: _scan_state["error"] = str(e)
    finally:
        with _scan_lock: _scan_state["active"] = False

@app.get("/admin/stats")
def get_global_stats(db: Session = Depends(get_db)):
    """
    Fetch real-time ingestion and enrichment statistics.
    """
    return ImportService.get_stats(db)

@app.post("/admin/import/tv")
def import_tv_series(db: Session = Depends(get_db)):
    """Manually trigger daily TV series ID import."""
    from import_service import ImportService
    service = ImportService(db)
    return service.fetch_tmdb_daily_tv_ids()

@app.post("/movies/{movie_id}/rate")
def rate_movie(movie_id: int, user_data: UserRating, db: Session = Depends(get_db)):
    """
    Submit a community rating (1-10) for a specific movie.
    """
    rating = db.query(Rating).filter(Rating.movie_id == movie_id).first()
    if not rating:
        rating = Rating(movie_id=movie_id, user_rating=0.0, user_votes=0)
        db.add(rating)
    
    # Update running average
    new_votes = (rating.user_votes or 0) + 1
    old_avg = rating.user_rating or 0.0
    rating.user_rating = ((old_avg * (new_votes - 1)) + user_data.rating) / new_votes
    rating.user_votes = new_votes
    
    db.commit()
    return {"status": "success", "new_rating": rating.user_rating, "total_votes": rating.user_votes}

@app.post("/tv/{tv_id}/rate")
def rate_tv(tv_id: int, user_data: UserRating, db: Session = Depends(get_db)):
    """
    Submit a community rating (1-10) for a specific TV show.
    """
    from models import TVRating
    rating = db.query(TVRating).filter(TVRating.tv_id == tv_id).first()
    if not rating:
        rating = TVRating(tv_id=tv_id, user_rating=0.0, user_votes=0)
        db.add(rating)
    
    new_votes = (rating.user_votes or 0) + 1
    old_avg = rating.user_rating or 0.0
    rating.user_rating = ((old_avg * (new_votes - 1)) + user_data.rating) / new_votes
    rating.user_votes = new_votes
    
    db.commit()
    return {"status": "success", "new_rating": rating.user_rating, "total_votes": rating.user_votes}

@app.get("/")
def read_root():
    return {"status": "Global Film Intelligence API is active"}

@app.get("/genres/movie")
def get_movie_genres():
    """Fetch all movie genres from TMDB."""
    svc = TMDBService()
    return svc.get_movie_genres()

@app.get("/genres/tv")
def get_tv_genres():
    """Fetch all TV genres from TMDB."""
    svc = TMDBService()
    return svc.get_tv_genres()


@app.post("/recommendations/generate")
def generate_recommendation(title: str, year: str = None, db: Session = Depends(get_db)):
    """
    Trigger analysis for a specific movie title.
    """
    if not settings.TMDB_API_KEY or not settings.GEMINI_API_KEY:
        # Mock data for demonstration if keys are missing
        return {
            "message": "API keys missing. Returning mock analysis for demonstration.",
            "movie": {
                "title": title,
                "year": year or "2024",
                "verdict": "⭐ Highly Recommended",
                "summary": "This is a mock analysis for demonstration purposes."
            }
        }
    
    aggregator = DataAggregationService(db)
    movie = aggregator.process_movie(title, year)
    
    if movie:
        return {"message": "Analysis complete", "movie": movie}
    return {"message": "Failed to analyze movie. Check logs."}

@app.get("/recommendations/daily")
def get_daily_recommendations(limit: int = 20, db: Session = Depends(get_db)):
    """
    Fetch the highest-rated enriched movies for the dashboard.
    Shows movies that have a poster image, ordered by IMDb/RT score (best first).
    Ratings: IMDb + RT only. Falls back to TMDB vote_average when neither is available.
    """
    try:
        # Show movies that have posters, ordered by best available rating (descending)
        movies = (
            db.query(Movie)
            .outerjoin(Rating, Rating.movie_id == Movie.id)
            .filter(Movie.poster_path != None)
            .order_by(func.coalesce(Rating.imdb_rating, Rating.tmdb_rating, 0.0).desc())
            .limit(limit)
            .all()
        )

        enriched = []
        for m in movies:
            try:
                rec    = db.query(Recommendation).filter(Recommendation.movie_id == m.id).first()
                rating = db.query(Rating).filter(Rating.movie_id == m.id).first()
                enriched.append({
                    "id":             m.id,
                    "title":          m.title,
                    "year":           m.year,
                    "genre":          m.genre,
                    "director":       m.director,
                    "country":        m.country,
                    "poster_path":    m.poster_path,
                    "backdrop_path":  m.backdrop_path,
                    # Ratings — IMDb + RT displayed, TMDB avg as fallback info
                    "rating":         rating.imdb_rating if rating else None,
                    "tmdb_rating":    rating.tmdb_rating if rating else None,
                    "rotten_critics": rating.rotten_critics if rating else None,
                    "rotten_audience": rating.rotten_audience if rating else None,
                    # User community rating
                    "user_rating":    rating.user_rating if rating else None,
                    "user_votes":     rating.user_votes if rating else 0,
                    # Verdict from scoring
                    "verdict":  rec.verdict if rec else None,
                    "summary":  rec.ai_summary if rec else None,
                })
            except Exception as e:
                print(f"Error building recommendation {m.id}: {e}")
                continue
        return enriched
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}



@app.get("/scan/status")
def get_scan_status():
    """Return current background scan progress."""
    with _scan_lock:
        return dict(_scan_state)


@app.get("/recommendations/discover")
def discover_recommendations(
    year: int = None,
    year_start: int = None,
    year_end: int = None,
    region: str = None,
    language: str = None,
    genre_id: int = None,
    db: Session = Depends(get_db)
):
    """
    Fire a full background discovery scan — returns immediately.
    The scan pages through ALL available TMDB results in a background thread.
    Poll /scan/status for progress.
    """
    logger.info(f"Discovery triggered. Region: {region}, Language: {language}, Year: {year}, Range: {year_start}-{year_end}")

    if not settings.GEMINI_API_KEY or not settings.TMDB_API_KEY:
        return {"message": "Mock Discovery (API keys missing)", "count": 0, "movies": []}

    # If already scanning, report status
    with _scan_lock:
        if _scan_state["active"]:
            return {
                "message": "Scan already running",
                "scanned": _scan_state["scanned"],
                "current_page": _scan_state["current_page"],
                "total_pages": _scan_state["total_pages"],
            }

    # Close the FastAPI-injected session before background writes
    db.close()

    # Launch background thread (not FastAPI BackgroundTasks — we want it to outlive the request)
    t = threading.Thread(
        target=_run_full_scan_bg,
        args=(year, region, language, genre_id, year_start, year_end),
        daemon=True
    )
    t.start()

    return {
        "message": "Full scan started in background",
        "region": region,
        "language": language,
        "note": "Poll /scan/status for progress. Explorer auto-refreshes while scan runs."
    }


@app.get("/movies")
def get_movies(
    year: int = None,
    year_start: int = None,
    year_end: int = None,
    genre: str = None,
    region: str = None,
    language: str = None,
    sort_by: str = None, # 'score', 'year', 'title'
    skip: int = 0,
    limit: int = 40,      # Increased default limit for Explorer
    db: Session = Depends(get_db)
):
    """
    Browse the local movie database with filters and pagination.
    """
    try:
        # Optimized joined loading to prevent N+1 queries
        query = db.query(Movie).options(
            joinedload(Movie.ratings),
            joinedload(Movie.recommendations)
        )
        
        # Apply Filters
        if year:
            query = query.filter(Movie.year == year)
        if year_start:
            query = query.filter(Movie.year >= year_start)
        if year_end:
            query = query.filter(Movie.year <= year_end)
        if genre:
            query = query.filter(Movie.genre.contains(genre))
        if region:
            region_name = COUNTRY_MAP.get(region, region)
            query = query.filter(or_(Movie.country == region, Movie.country == region_name))
        if language:
            query = query.filter(Movie.language == language)
        
        # Apply Global Sorting
        if sort_by == 'score' or sort_by == 'score_desc' or sort_by is None:
            # High-performance IMDb-priority sort (as requested)
            query = query.order_by(Movie.imdb_rating.desc())
        elif sort_by == 'score_asc':
            query = query.order_by(Movie.quickflix_score.asc())
        elif sort_by == 'year' or sort_by == 'year_desc':
            query = query.order_by(Movie.year.desc())
        elif sort_by == 'year_asc':
            query = query.order_by(Movie.year.asc())
        elif sort_by == 'title' or sort_by == 'title_asc':
            query = query.order_by(Movie.title.asc())
        elif sort_by == 'title_desc':
            query = query.order_by(Movie.title.desc())
        
        query = query.order_by(Movie.id.desc())
        
        # Optimize count: skip count if it's a deep page to save time, or use approximate
        # For industry standard, we'll keep it but ensure it's indexed
        total = query.count()
        movies = query.offset(skip).limit(limit).all()

        enriched = []
        for m in movies:
            rating = m.ratings
            rec = m.recommendations
            
            enriched.append({
                "id": m.id,
                "title": m.title,
                "year": m.year,
                "genre": m.genre,
                "director": m.director,
                "country": m.country,
                "runtime": m.runtime,
                "poster_path": m.poster_path,
                "backdrop_path": m.backdrop_path,
                "rating": rating.imdb_rating if rating else 0.0,
                "tmdb_rating": rating.tmdb_rating if rating else 0.0,
                "rotten_critics": rating.rotten_critics if rating else 0.0,
                "rotten_audience": rating.rotten_audience if rating else 0.0,
                "quickflix_score": rating.quickflix_score if rating else 0.0,
                "language": m.language,
                "verdict": rec.verdict if rec else "🔍 Analysis Pending",
                "summary": rec.ai_summary if rec else "AI insights coming soon.",
                "watch_links": {
                    "torrent_1337x": f"https://1337x.to/search/{m.title.replace(' ', '+')}+{m.year}/1/",
                    "torrent_yts": f"https://yts.mx/browse-movies/{m.title.replace(' ', '+')}+{m.year}/all/all/0/latest/0/all",
                }
            })
            
        return {"total": total, "movies": enriched}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/recommendations/{movie_id}/social")
def get_social_content(movie_id: int, db: Session = Depends(get_db)):
    """
    Generate social media content for a specific movie.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        return {"error": "Movie not found"}
    
    # Fetch summary from recommendation if available
    rec = db.query(Recommendation).filter(Recommendation.movie_id == movie_id).first()
    summary = rec.ai_summary if rec else "This is a premium film recommended for its quality and impact."
    
    if not settings.GEMINI_API_KEY:
        # Return mock social content if API key missing
        return {
            "reel_hook": f"Stop scrolling! This {movie.year} masterpiece is a must-watch.",
            "reel_script": f"Start with a close-up of the poster of '{movie.title}'. Cut to reaction shots. Explain why it's a {movie.genre} classic. End with a 9/10 rating.",
            "thumbnail_headline": "Hidden Gem Alert!",
            "hashtags": ["#movies", "#cinema", f"#{movie.title.lower().replace(' ', '')}", "#filmintelligence"],
            "story_poll": f"Have you seen '{movie.title}' yet?"
        }
    
    gemini = GeminiService()
    import json
    try:
        raw_json = gemini.generate_social_content({
            "title": movie.title,
            "year": movie.year,
            "genre": movie.genre,
            "summary": summary
        })
        # Clean up possible markdown code blocks
        clean_json = raw_json.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_json)
        return data
    except Exception as e:
        return {"error": f"Failed to generate social content: {e}"}

@app.get("/movies/{movie_id}/details")
def get_movie_details(movie_id: int, db: Session = Depends(get_db)):
    """
    Fetch comprehensive details for a movie. Triggers lazy enrichment if record is 'thin'.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        return {"error": "Movie not found"}
    
    # Check if deep enrichment is needed (no director OR has placeholder summary)
    rec = db.query(Recommendation).filter(Recommendation.movie_id == movie.id).first()
    if not movie.director or (rec and "pending" in rec.ai_summary.lower()):
        aggregator = DataAggregationService(db)
        # Deep Enrichment on demand
        enriched = aggregator.process_movie(movie.title, year=movie.year, tmdb_id=movie.tmdb_id)
        if enriched:
            movie = enriched
            # Re-fetch rec for updated data
            rec = db.query(Recommendation).filter(Recommendation.movie_id == movie.id).first()

    # Fetch ratings and recommendation
    rating = db.query(Rating).filter(Rating.movie_id == movie.id).first()
    rec = db.query(Recommendation).filter(Recommendation.movie_id == movie.id).first()
    
    # Base data from local DB
    result = {
        "id": movie.id,
        "title": movie.title,
        "year": movie.year,
        "genre": movie.genre,
        "director": movie.director,
        "runtime": movie.runtime,
        "ratings": {
            "imdb": rating.imdb_rating if rating else 0,
            "rotten_critics": rating.rotten_critics if rating else 0,
            "rotten_audience": rating.rotten_audience if rating else 0,
            "quickflix": rating.quickflix_score if rating else 0
        },
        "recommendation": {
            "verdict": rec.verdict if rec else "N/A",
            "ai_summary": rec.ai_summary if rec else "No analysis available.",
            "praise": rec.praise if rec else [],
            "criticism": rec.criticism if rec else [],
            "key_strengths": rec.key_strengths if rec else [],
            "key_weaknesses": rec.key_weaknesses if rec else [],
            "availability": rec.availability if rec else "N/A",
            "audience_fit": rec.audience_fit if rec else [],
            "comparisons": rec.comparisons if rec else [],
            "instagram_caption": rec.instagram_caption if rec else ""
        },
        "tmdb_data": None
    }
    
    # Supplemental data from TMDB if tmdb_id exists
    if movie.tmdb_id:
        try:
            tmdb = TMDBService()
            # This fetches credits and release_dates as configured in tmdb_service.py
            tmdb_details = tmdb.get_movie_details(movie.tmdb_id)
            
            # Fetch videos separately as it's not in the default append_to_response in tmdb_service.py
            # Actually, let's update tmdb_service.py's get_movie_details to include videos
            result["tmdb_data"] = {
                "backdrop_path": tmdb_details.get("backdrop_path"),
                "cast": tmdb_details.get("credits", {}).get("cast", [])[:10], # Top 10 cast
                "crew": tmdb_details.get("credits", {}).get("crew", [])[:5],
                "overview": tmdb_details.get("overview"),
                "videos": tmdb_details.get("videos"),
                "watch_providers": tmdb_details.get("watch/providers", {}).get("results", {})
            }
            
            # Generate Torrent and OTT search links
            search_query = f"{movie.title} {movie.year}"
            encoded_query = urllib3.util.parse_url(f"https://example.com/?q={search_query}").query.split('=')[1] if 'urllib3' in globals() else search_query.replace(' ', '+')
            # Use simple plus replacement for safety if urllib3 is complex here
            safe_query = movie.title.replace(' ', '+') + "+" + str(movie.year)
            
            result["watch_links"] = {
                "torrent_1337x": f"https://1337x.to/search/{safe_query}/1/",
                "torrent_yts": f"https://yts.mx/browse-movies/{safe_query}/all/all/0/latest/0/all",
                "google_search": f"https://www.google.com/search?q={safe_query}+watch+online+in+India",
            }
        except Exception as e:
            print(f"Error fetching TMDB data: {e}")
            
    return result

@app.post("/admin/import")
def run_bulk_import(date: str = None, db: Session = Depends(get_db)):
    """
    Administrative endpoint to trigger the bulk ingestion of TMDB IDs.
    Seeding 1M+ titles without hitting TMDB search limits.
    """
    importer = ImportService(db)
    result = importer.fetch_tmdb_daily_ids(date)
    return result

@app.get("/tv")
def get_tv_series(
    year: int = None,
    year_start: int = None,
    year_end: int = None,
    genre: str = None,
    region: str = None,
    language: str = None,
    sort_by: str = "score",
    skip: int = 0,
    limit: int = 40,
    db: Session = Depends(get_db)
):
    """Browse the TV series library."""
    query = db.query(TVSeries).options(
        joinedload(TVSeries.ratings),
        joinedload(TVSeries.recommendations)
    )
    if year: query = query.filter(TVSeries.year == year)
    if year_start: query = query.filter(TVSeries.year >= year_start)
    if year_end: query = query.filter(TVSeries.year <= year_end)
    
    # Exclude non-scripted content by default unless explicitly requested
    if genre:
        query = query.filter(TVSeries.genre.contains(genre))
    else:
        # Default: Strictly follow the "TV Series & Miniseries" scripted-only rule
        # Use TMDB 'type' as primary filter, with genre-based fallbacks for unenriched items
        query = query.filter(or_(
            TVSeries.type.in_(['Scripted', 'Miniseries']),
            and_(
                TVSeries.type == None,
                ~TVSeries.genre.contains('Reality'),
                ~TVSeries.genre.contains('News'),
                ~TVSeries.genre.contains('Talk'),
                ~TVSeries.genre.contains('Documentary')
            )
        ))
    if region:
        region_name = COUNTRY_MAP.get(region, region)
        query = query.filter(or_(TVSeries.country == region, TVSeries.country == region_name))
    if language:
        query = query.filter(TVSeries.language == language)

    # Apply Sorting
    if sort_by == 'score' or sort_by == 'score_desc' or sort_by is None:
        # Sort ONLY by IMDb descending as requested
        query = query.order_by(TVSeries.imdb_rating.desc())
    elif sort_by == 'year':
        query = query.order_by(TVSeries.year.desc())
    
    total = query.count()
    series = query.offset(skip).limit(limit).all()

    enriched = []
    for s in series:
        rating = s.ratings
        rec = s.recommendations
        
        enriched.append({
            "id": s.id,
            "title": s.title,
            "year": s.year,
            "genre": s.genre,
            "creator": s.creator,
            "country": s.country,
            "poster_path": s.poster_path,
            "backdrop_path": s.backdrop_path,
            "rating": rating.imdb_rating if rating else 0.0,
            "tmdb_rating": rating.tmdb_rating if rating else 0.0,
            "rotten_critics": rating.rotten_critics if rating else 0.0,
            "rotten_audience": rating.rotten_audience if rating else 0.0,
            "quickflix_score": s.quickflix_score,
            "user_votes": rating.user_votes if rating else 0,
            "language": s.language,
            "verdict": rec.verdict if rec else "🔍 Analysis Pending",
            "summary": rec.ai_summary if rec else "AI insights coming soon.",
            "content_type": "tv"
        })
    return {"total": total, "tv": enriched}

@app.get("/recommendations/tv/discover")
def discover_tv_recommendations(
    year: int = None,
    year_start: int = None,
    year_end: int = None,
    region: str = None,
    language: str = None,
    genre_id: int = None,
    db: Session = Depends(get_db)
):
    """Trigger background TV discovery scan."""
    with _scan_lock:
        if _scan_state["active"]:
            return {"message": "Scan already running"}

    db.close()
    t = threading.Thread(
        target=_run_tv_scan_bg,
        args=(year, region, language, genre_id, year_start, year_end),
        daemon=True
    )
    t.start()
    return {"message": "TV scan started in background", "type": "tv"}

@app.get("/tv/{tv_id}/details")
def get_tv_details(tv_id: int, db: Session = Depends(get_db)):
    """Fetch comprehensive details for a TV series."""
    tv = db.query(TVSeries).filter(TVSeries.id == tv_id).first()
    if not tv: return {"error": "TV series not found"}
    
    rating = db.query(TVRating).filter(TVRating.tv_id == tv.id).first()
    rec = db.query(TVRecommendation).filter(TVRecommendation.tv_id == tv.id).first()
    
    result = {
        "id": tv.id,
        "title": tv.title,
        "year": tv.year,
        "genre": tv.genre,
        "creator": tv.creator,
        "seasons": tv.seasons,
        "episodes": tv.episodes,
        "status": tv.status,
        "ratings": {
            "imdb": rating.imdb_rating if rating else 0,
            "quickflix": rating.quickflix_score if rating else 0
        },
        "recommendation": {
            "verdict": rec.verdict if rec else "N/A",
            "ai_summary": rec.ai_summary if rec else "No analysis available.",
            "praise": rec.praise if rec else [],
            "criticism": rec.criticism if rec else [],
            "key_strengths": rec.key_strengths if rec else [],
            "key_weaknesses": rec.key_weaknesses if rec else [],
            "availability": rec.availability if rec else "N/A"
        },
        "content_type": "tv"
    }

    if tv.tmdb_id:
        tmdb = TMDBService()
        tmdb_details = tmdb.get_tv_details(tv.tmdb_id)
        result["tmdb_data"] = {
            "cast": tmdb_details.get("credits", {}).get("cast", [])[:10],
            "overview": tmdb_details.get("overview"),
            "videos": tmdb_details.get("videos"),
            "backdrop_path": tmdb_details.get("backdrop_path")
        }
    return result
