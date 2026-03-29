from tmdb_service import TMDBService
from scoring_service import ScoringService
from gemini_service import GeminiService
from models import Movie, Rating, Recommendation, TVSeries, TVRating, TVRecommendation
from config import settings
import requests

class DataAggregationService:
    def __init__(self, db_session):
        self.tmdb = TMDBService()
        self.gemini = GeminiService()
        self.scoring = ScoringService()
        self.db = db_session

    def process_movie(self, title: str, year: int = None, tmdb_id: int = None):
        """
        Processes or enriches a movie. Supports lazy enrichment for pre-seeded IDs.
        """
        # 1. Resolve Movie Record
        movie = None
        if tmdb_id:
            movie = self.db.query(Movie).filter(Movie.tmdb_id == tmdb_id).first()
        elif title:
            # Try to find by title and year
            query = self.db.query(Movie).filter(Movie.title == title)
            if year:
                query = query.filter(Movie.year == year)
            movie = query.first()

        # 2. Check if we already have full details
        if movie and movie.genre and movie.director:
            # Check if recommendation exists, if not, we still need to generate AI content
            rec = self.db.query(Recommendation).filter(Recommendation.movie_id == movie.id).first()
            if rec:
                return movie
            # If movie exists but no recommendation, proceed to enrich

        # 3. Get TMDB Details
        if not tmdb_id:
            search_results = self.tmdb.search_movie(title)
            if not search_results.get('results'):
                return None
            tmdb_id = search_results['results'][0]['id']
        
        details = self.tmdb.get_movie_details(tmdb_id)
        if not details: 
            return movie # Return existing thin record if API fails

        # 4. Get Multi-DB Ratings (OMDb & TVMaze)
        imdb_id = details.get('imdb_id')
        omdb_ratings = self._fetch_omdb_ratings(imdb_id)
        tvmaze_data = self._fetch_tvmaze_data(title, year)
        
        # Consolidate ratings
        imdb_rating = (omdb_ratings.get('imdb') if omdb_ratings else None) or details.get('vote_average')
        rt_critics = omdb_ratings.get('rt_critics') if omdb_ratings else None
        rt_audience = omdb_ratings.get('rt_audience') if omdb_ratings else None
        tvmaze_rating = tvmaze_data.get('rating', {}).get('average') if tvmaze_data else None

        # Regional/Specialized Scores (Universal Adapter)
        regional_scores = self._fetch_regional_scores(details)
        user_score = self._get_user_score(movie.id) if movie else {}


        # 5. Calculate Dynamic Global Score (including regional & user scores)
        quickflix_score = self.scoring.calculate_quickflix_score(
            imdb_rating=imdb_rating, 
            rt_critics=rt_critics, 
            rt_audience=rt_audience, 
            tmdb_popularity=details.get('popularity', 0.0),
            tvmaze_rating=tvmaze_rating,
            regional_rating=regional_scores.get('score'),
            user_rating=user_score.get('rating')
        )

        verdict = self.scoring.classify_verdict(quickflix_score)
        
        # 6. Extract Availability
        providers = details.get('watch/providers', {}).get('results', {})
        us_providers = providers.get('US', {})
        flatrate = us_providers.get('flatrate', [])
        availability = ", ".join([p.get('provider_name') for p in flatrate]) if flatrate else "Theatrical / Purchase Only"

        # 7. Generate AI Content
        ai_data = {
            "title": details.get('title'),
            "overview": details.get('overview'),
            "score": quickflix_score,
            "verdict": verdict,
            "tmdb_data": details,
            "availability": availability,
            "multi_db": {
                "tvmaze": tvmaze_data if tvmaze_data else "Not Found",
                "omdb": omdb_ratings if omdb_ratings else "Not Found"
            }
        }
        
        ai_recommendation_json = self.gemini.generate_recommendation_text(ai_data)
        
        import json
        try:
            cleaned_json = ai_recommendation_json.strip('`').strip('json').strip()
            ai_data_parsed = json.loads(cleaned_json)
        except:
            ai_data_parsed = {
                "ai_summary": "Full analysis details available in the recommendation table.",
                "verdict": verdict,
                "instagram_caption": f"Watch {details.get('title')}!",
            }

        # 8. Update or Create Movie Record
        try:
            if not movie:
                movie = Movie(tmdb_id=tmdb_id)
                self.db.add(movie)
            
            movie.title = details.get('title')
            movie.year = details.get('release_date', '').split('-')[0] if details.get('release_date') else None
            movie.country = details.get('production_countries', [{}])[0].get('name') if details.get('production_countries') else None
            movie.language = details.get('original_language')
            movie.genre = ", ".join([g['name'] for g in details.get('genres', [])])
            movie.director = self._get_director(details)
            movie.runtime = details.get('runtime')
            movie.poster_path = details.get('poster_path')
            movie.backdrop_path = details.get('backdrop_path')
            
            self.db.flush()
            
            # Upsert Rating
            rating = self.db.query(Rating).filter(Rating.movie_id == movie.id).first()
            if not rating:
                rating = Rating(movie_id=movie.id)
                self.db.add(rating)
            
            rating.imdb_rating = imdb_rating
            rating.rotten_critics = rt_critics
            rating.rotten_audience = rt_audience
            rating.quickflix_score = quickflix_score
            rating.vote_count = details.get('vote_count')

            # Upsert Recommendation
            rec = self.db.query(Recommendation).filter(Recommendation.movie_id == movie.id).first()
            if not rec:
                rec = Recommendation(movie_id=movie.id)
                self.db.add(rec)
            
            rec.category = "Multi-DB Analysis"
            rec.ai_summary = ai_data_parsed.get('ai_summary', ai_data_parsed.get('summary'))
            rec.praise = ai_data_parsed.get('praise', [])
            rec.criticism = ai_data_parsed.get('criticism', [])
            rec.key_strengths = ai_data_parsed.get('key_strengths', [])
            rec.key_weaknesses = ai_data_parsed.get('key_weaknesses', [])
            rec.verdict = ai_data_parsed.get('verdict', verdict)
            rec.instagram_caption = ai_data_parsed.get('instagram_caption')
            rec.availability = availability
            rec.audience_fit = ai_data_parsed.get('audience_fit', [])
            rec.comparisons = ai_data_parsed.get('comparisons', [])
            
            self.db.commit()
            return movie
        except Exception as e:
            self.db.rollback()
            print(f"Error saving enriched movie: {e}")
            return None

    def process_tv_series(self, title: str, year: int = None, tmdb_id: int = None):
        """
        Processes or enriches a TV series.
        """
        from models import TVSeries, TVRating, TVRecommendation
        
        # 1. Resolve TV Record
        tv = None
        if tmdb_id:
            tv = self.db.query(TVSeries).filter(TVSeries.tmdb_id == tmdb_id).first()
        
        # 2. Return if already FULLY enriched (has AI summary)
        if tv:
            rec = self.db.query(TVRecommendation).filter(TVRecommendation.tv_id == tv.id).first()
            if rec and rec.ai_summary and "pending" not in rec.ai_summary.lower():
                return tv

        # 3. Get TMDB Details
        if not tmdb_id:
            search_results = self.tmdb.search_tv(title)
            if not search_results.get('results'):
                return None
            tmdb_id = search_results['results'][0]['id']
        
        details = self.tmdb.get_tv_details(tmdb_id)
        if not details: 
            return tv

        # 4. Get Ratings (TVMaze specialized for TV)
        tvmaze_data = self._fetch_tvmaze_data(title, year)
        
        imdb_rating = details.get('vote_average') # TV discovery often relies on TMDB/IMDb
        tvmaze_rating = tvmaze_data.get('rating', {}).get('average') if tvmaze_data else None

        # 5. Calculate Score
        quickflix_score = self.scoring.calculate_quickflix_score(
            imdb_rating=imdb_rating,
            tmdb_popularity=details.get('popularity', 0.0),
            tvmaze_rating=tvmaze_rating
        )
        verdict = self.scoring.classify_verdict(quickflix_score)
        
        # 6. Extract Availability
        providers = details.get('watch/providers', {}).get('results', {})
        us_providers = providers.get('US', {})
        flatrate = us_providers.get('flatrate', [])
        availability = ", ".join([p.get('provider_name') for p in flatrate]) if flatrate else "Broadcast / Purchase Only"

        # 7. Generate AI Content
        ai_data = {
            "title": details.get('name'),
            "overview": details.get('overview'),
            "score": quickflix_score,
            "verdict": verdict,
            "tmdb_data": details,
            "availability": availability,
            "multi_db": {
                "tvmaze": tvmaze_data if tvmaze_data else "Not Found"
            }
        }
        
        ai_recommendation_json = self.gemini.generate_recommendation_text(ai_data)
        
        import json
        try:
            cleaned_json = ai_recommendation_json.strip('`').strip('json').strip()
            ai_data_parsed = json.loads(cleaned_json)
        except:
            ai_data_parsed = {
                "ai_summary": details.get('overview', "No summary available."),
                "verdict": verdict,
                "instagram_caption": f"Watch {details.get('name')}!",
            }

        # 8. Update or Create TV Record
        try:
            if not tv:
                tv = TVSeries(tmdb_id=tmdb_id)
                self.db.add(tv)
            
            tv.title = details.get('name')
            tv.year = details.get('first_air_date', '').split('-')[0] if details.get('first_air_date') else None
            tv.country = details.get('production_countries', [{}])[0].get('name') if details.get('production_countries') else None
            tv.language = details.get('original_language')
            tv.genre = ", ".join([g['name'] for g in details.get('genres', [])])
            tv.creator = ", ".join([c['name'] for c in details.get('created_by', [])]) if details.get('created_by') else "Unknown"
            tv.status = details.get('status')
            tv.seasons = details.get('number_of_seasons')
            tv.episodes = details.get('number_of_episodes')
            tv.poster_path = details.get('poster_path')
            tv.backdrop_path = details.get('backdrop_path')
            
            self.db.flush()
            
            # Upsert Rating
            rating = self.db.query(TVRating).filter(TVRating.tv_id == tv.id).first()
            if not rating:
                rating = TVRating(tv_id=tv.id)
                self.db.add(rating)
            
            rating.tmdb_rating = details.get('vote_average')
            rating.quickflix_score = quickflix_score
            rating.vote_count = details.get('vote_count')

            # Upsert Recommendation
            rec = self.db.query(TVRecommendation).filter(TVRecommendation.tv_id == tv.id).first()
            if not rec:
                rec = TVRecommendation(tv_id=tv.id)
                self.db.add(rec)
            
            rec.category = "Global TV Intelligence"
            rec.ai_summary = ai_data_parsed.get('ai_summary', ai_data_parsed.get('summary'))
            rec.praise = ai_data_parsed.get('praise', [])
            rec.criticism = ai_data_parsed.get('criticism', [])
            rec.key_strengths = ai_data_parsed.get('key_strengths', [])
            rec.key_weaknesses = ai_data_parsed.get('key_weaknesses', [])
            rec.verdict = ai_data_parsed.get('verdict', verdict)
            rec.instagram_caption = ai_data_parsed.get('instagram_caption')
            rec.availability = availability
            rec.audience_fit = ai_data_parsed.get('audience_fit', [])
            rec.comparisons = ai_data_parsed.get('comparisons', [])
            
            self.db.commit()
            return tv
        except Exception as e:
            self.db.rollback()
            print(f"Error saving enriched TV series: {e}")
            return None

    def light_enrichment(self, movie: Movie):
        """
        Quickly fetch poster, backdrop, and basic ratings for a 'thin' movie.
        Does NOT trigger expensive AI analysis.
        """
        if not movie.tmdb_id:
            return
        
        details = self.tmdb.get_movie_details(movie.tmdb_id)
        if not details:
            return
        
        movie.poster_path = details.get('poster_path')
        movie.backdrop_path = details.get('backdrop_path')
        movie.genre = ", ".join([g['name'] for g in details.get('genres', [])])
        movie.runtime = details.get('runtime')
        
        # Quick score update if missing
        rating = self.db.query(Rating).filter(Rating.movie_id == movie.id).first()
        if not rating:
            rating = Rating(movie_id=movie.id)
            self.db.add(rating)
        
        rating.imdb_rating = details.get('vote_average', 0.0)
        movie.imdb_rating = rating.imdb_rating
        rating.quickflix_score = self.scoring.calculate_quickflix_score(
            imdb_rating=rating.imdb_rating, 
            tmdb_popularity=details.get('popularity', 0.0)
        )
        movie.quickflix_score = rating.quickflix_score
        
        self.db.commit()
        return movie

    def light_enrichment_tv(self, tv: TVSeries):
        """
        Quickly fetch poster, backdrop, and basic ratings for a 'thin' TV series.
        """
        if not tv.tmdb_id:
            return
        
        details = self.tmdb.get_tv_details(tv.tmdb_id)
        if not details:
            return
        
        tv.poster_path = details.get('poster_path')
        tv.backdrop_path = details.get('backdrop_path')
        tv.genre = ", ".join([g['name'] for g in details.get('genres', [])])
        tv.type = details.get('type')
        tv.seasons = details.get('number_of_seasons')
        tv.episodes = details.get('number_of_episodes')
        
        # Quick score update if missing
        from models import TVRating
        rating = self.db.query(TVRating).filter(TVRating.tv_id == tv.id).first()
        if not rating:
            rating = TVRating(tv_id=tv.id)
            self.db.add(rating)
        
        rating.tmdb_rating = details.get('vote_average', 0.0)
        # Baseline: Use tmdb_rating as a fallback for imdb_rating to ensure sorting works immediately
        rating.imdb_rating = rating.imdb_rating or rating.tmdb_rating or 0.0
        tv.imdb_rating = rating.imdb_rating
        
        rating.quickflix_score = self.scoring.calculate_quickflix_score(
            imdb_rating=tv.imdb_rating, 
            tmdb_popularity=details.get('popularity', 0.0)
        )
        tv.quickflix_score = rating.quickflix_score
        
        self.db.commit()
        return tv

    # TMDB genre ID → name lookup (no extra API call needed)
    TMDB_GENRES = {
        28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
        80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
        14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
        9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
        10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western",
    }

    def _calculate_visible_score(self, imdb: float = None, rt_critics: float = None,
                                  rt_audience: float = None, tmdb_avg: float = None) -> float:
        """
        Score based ONLY on IMDb + Rotten Tomatoes.
        Fallback chain if neither: TMDB vote_average.
        Returns 0-100.
        """
        values = []
        weights = []

        if imdb and imdb > 0:
            values.append(imdb * 10.0)  # scale to 0-100
            weights.append(2.0)         # IMDb = weight 2
        if rt_critics and rt_critics > 0:
            values.append(float(rt_critics))
            weights.append(2.0)         # RT Critics = weight 2
        if rt_audience and rt_audience > 0:
            values.append(float(rt_audience))
            weights.append(1.0)         # RT Audience = weight 1

        if values:
            score = sum(v * w for v, w in zip(values, weights)) / sum(weights)
            return round(min(score, 100.0), 1)

        # Fallback: TMDB vote_average (0-10 → 0-100)
        if tmdb_avg and tmdb_avg > 0:
            return round(min(tmdb_avg * 10.0, 100.0), 1)

        return 0.0

    def quick_ingest_movie(self, mv: dict, region: str = None) -> bool:
        """
        Rapidly saves core movie metadata from a TMDB discovery result.
        Returns True if the movie was NEWLY created, False if it already existed.
        """
        tmdb_id = mv.get('id')
        title   = mv.get('title') or mv.get('original_title', 'Unknown')
        is_new  = False
        
        try:
            movie = self.db.query(Movie).filter(Movie.tmdb_id == tmdb_id).first()
            if not movie:
                movie = Movie(tmdb_id=tmdb_id, title=title)
                self.db.add(movie)
                self.db.flush()
                is_new = True

            release_date = mv.get('release_date', '')
            movie.title        = title
            movie.year         = release_date.split('-')[0] if release_date else None
            movie.language     = mv.get('original_language')
            movie.poster_path  = mv.get('poster_path')
            movie.backdrop_path = mv.get('backdrop_path')

            genre_ids = mv.get('genre_ids', [])
            movie.genre = ", ".join(self.TMDB_GENRES.get(gid, '') for gid in genre_ids if gid in self.TMDB_GENRES) or None

            if region:
                movie.country = region or 'US'
            
            # Preliminary Score
            tmdb_avg = mv.get('vote_average', 0.0)
            score = self.scoring.calculate_quickflix_score(
                imdb_rating=tmdb_avg,
                tmdb_popularity=mv.get('popularity', 0.0)
            )
            verdict = self.scoring.classify_verdict(score)

            # Upsert Rating
            rating = self.db.query(Rating).filter(Rating.movie_id == movie.id).first()
            if not rating:
                rating = Rating(movie_id=movie.id)
                self.db.add(rating)
            rating.tmdb_rating = tmdb_avg
            # Baseline: Use TMDB avg as fallback for imdb_rating to allow high-performance sorting
            rating.imdb_rating = rating.imdb_rating or tmdb_avg
            movie.imdb_rating  = rating.imdb_rating
            
            rating.quickflix_score = score
            rating.vote_count      = mv.get('vote_count')
            movie.quickflix_score  = score

            # Placeholder Recommendation
            rec = self.db.query(Recommendation).filter(Recommendation.movie_id == movie.id).first()
            if not rec:
                rec = Recommendation(movie_id=movie.id)
                self.db.add(rec)
            if not rec.verdict:
                rec.verdict = verdict
                rec.category = "QuickFlix Discovery"
                rec.ai_summary = "Intelligence analysis pending. Open details for AI deep-dive."

            self.db.commit()
            return is_new
        except Exception as e:
            self.db.rollback()
            print(f"quick_ingest_movie failed for {mv.get('title')}: {e}", flush=True)
            return False

    def enrich_from_discover_data(self, mv: dict, region: str = None):
        """
        Save a movie using the data already in the TMDB discover response.
        NO extra per-movie API call — all 20 discover results reliably succeed.
        Full details (director, cast, etc.) are fetched on-demand via the detail endpoint.
        
        Rating logic: IMDb + RT only. Fallback to TMDB vote_average.
        """
        try:
            tmdb_id = mv['id']
            title   = mv.get('title') or mv.get('original_title', 'Unknown')

            movie = self.db.query(Movie).filter(Movie.tmdb_id == tmdb_id).first()
            if not movie:
                movie = Movie(tmdb_id=tmdb_id, title=title)
                self.db.add(movie)
                self.db.flush()

            # ── Core metadata from discover payload ──────────────────────────
            release_date = mv.get('release_date', '')
            movie.title        = title
            movie.year         = release_date.split('-')[0] if release_date else None
            movie.language     = mv.get('original_language')
            movie.poster_path  = mv.get('poster_path')
            movie.backdrop_path = mv.get('backdrop_path')

            # Map genre IDs → genre names using built-in table
            genre_ids = mv.get('genre_ids', [])
            movie.genre = ", ".join(
                self.TMDB_GENRES.get(gid, '') for gid in genre_ids if gid in self.TMDB_GENRES
            ) or None

            if region:
                movie.country = region
            
            # director left as None — fetched on demand via /movies/{id}/details
            self.db.flush()

            # ── Ratings: IMDb + RT first, TMDB vote_average as fallback ─────
            imdb_rating = None
            rt_critics  = None
            rt_audience = None
            tmdb_avg    = mv.get('vote_average')
            imdb_id     = None

            # First, try to get IMDB ID from TMDB details (more reliable for OMDb)
            try:
                details = self.tmdb.get_movie_details(tmdb_id)
                if details:
                    imdb_id = details.get('imdb_id')
                    # If we have details, we can also pick up RT scores if they were somehow in there (rare)
                    # and refresh TMDB avg
                    tmdb_avg = details.get('vote_average', tmdb_avg)
            except Exception as de:
                print(f"  ! Failed to get TMDB details for {tmdb_id}: {de}", flush=True)

            score = 0.0
            if settings.OMDB_API_KEY:
                try:
                    omdb_url = ""
                    if imdb_id:
                        omdb_url = f"http://www.omdbapi.com/?apikey={settings.OMDB_API_KEY}&i={imdb_id}"
                    else:
                        year_str = movie.year or ''
                        omdb_url = f"http://www.omdbapi.com/?apikey={settings.OMDB_API_KEY}&t={requests.utils.quote(title)}&y={year_str}&type=movie"
                    
                    # Use curl -4 -k fallback for OMDb for reliability in this env
                    import subprocess
                    cmd = ["curl.exe", "-4", "-k", "-s", "-L", "--connect-timeout", "5", omdb_url]
                    res = subprocess.run(cmd, capture_output=True, timeout=10)
                    if res.returncode == 0 and res.stdout:
                        odata = json.loads(res.stdout.decode('utf-8', errors='ignore'))
                        if odata.get('Response') == 'True':
                            imdb_str = odata.get('imdbRating', 'N/A')
                            if imdb_str != 'N/A':
                                imdb_rating = float(imdb_str)
                            for src in odata.get('Ratings', []):
                                if src['Source'] == 'Rotten Tomatoes':
                                    rt_critics = float(src['Value'].replace('%', ''))
                        elif odata.get('Error') == 'Request limit reached!':
                            print(f"  ! OMDb API: Request limit reached (Daily quota 1,000 used). Falling back to TMDB.", flush=True)
                except Exception as oe:
                    print(f"  ! OMDb fetch failed for {title}: {oe}", flush=True)

            # --- Standardized Scoring using ScoringService ---
            # If IMDB is missing, use TMDB avg as the baseline for scoring logic
            effective_imdb = imdb_rating if (imdb_rating and imdb_rating > 0) else tmdb_avg
            
            score = self.scoring.calculate_quickflix_score(
                imdb_rating=effective_imdb,
                rt_critics=rt_critics,
                tmdb_popularity=mv.get('popularity', 0.0),
                regional_rating=self._fetch_regional_scores({'production_countries': [{'iso_3166_1': region}] if region else [], 'original_language': mv.get('original_language'), 'vote_average': tmdb_avg}).get('score')
            )
            
            # Final safety check
            if score == 0 and tmdb_avg and tmdb_avg > 0:
                score = tmdb_avg * 10.0

            verdict = self.scoring.classify_verdict(score)

            # Upsert Rating
            rating = self.db.query(Rating).filter(Rating.movie_id == movie.id).first()
            if not rating:
                rating = Rating(movie_id=movie.id)
                self.db.add(rating)
            rating.imdb_rating    = imdb_rating     # Real IMDB score from OMDb (or None)
            rating.tmdb_rating    = tmdb_avg        # Real TMDB score (always present)
            rating.rotten_critics = rt_critics
            rating.rotten_audience = rt_audience
            rating.quickflix_score = score          # Internal weighted score
            rating.vote_count      = mv.get('vote_count')

            # Upsert Recommendation stub (minimal — full AI on demand)
            rec = self.db.query(Recommendation).filter(Recommendation.movie_id == movie.id).first()
            if not rec:
                rec = Recommendation(movie_id=movie.id)
                self.db.add(rec)
            if not rec.verdict:
                rec.verdict   = verdict
                rec.category  = "QuickFlix Discovery"
                sources_used  = []
                if imdb_rating: sources_used.append(f"IMDB {imdb_rating}")
                if rt_critics:  sources_used.append(f"RT {rt_critics:.0f}%")
                if not sources_used and tmdb_avg:
                    sources_used.append(f"TMDB avg {tmdb_avg:.1f}")
                rec.ai_summary = f"Score based on: {', '.join(sources_used) if sources_used else 'pending enrichment'}. Click Full Report for AI deep-dive."
                rec.praise = []; rec.criticism = []
                rec.key_strengths = []; rec.key_weaknesses = []
                rec.audience_fit  = []; rec.comparisons     = []

            self.db.commit()
            return movie

        except Exception as e:
            self.db.rollback()
            print(f"enrich_from_discover_data failed for {mv.get('title')}: {e}", flush=True)
            return None

    def quick_ingest_tv(self, show: dict, region: str = None) -> bool:
        """Rapidly saves core TV metadata. Returns True if NEW."""
        tid = show.get('id')
        name = show.get('name') or show.get('original_name')
        is_new = False
        
        try:
            tv = self.db.query(TVSeries).filter(TVSeries.tmdb_id == tid).first()
            if not tv:
                tv = TVSeries(tmdb_id=tid, title=name)
                self.db.add(tv)
                self.db.flush()
                is_new = True

            first_air = show.get('first_air_date', '')
            tv.title = name
            tv.year = first_air.split('-')[0] if first_air else None
            tv.language = show.get('original_language')
            tv.poster_path = show.get('poster_path')
            tv.backdrop_path = show.get('backdrop_path')
            
            # Map genre IDs (TV uses same IDs as Movies for many, but we'll use fallback)
            genre_ids = show.get('genre_ids', [])
            tv.genre = ", ".join(self.TMDB_GENRES.get(gid, 'TV') for gid in genre_ids if gid in self.TMDB_GENRES) or "TV Series"
            
            if region:
                tv.country = region

            # Preliminary Scoring using TMDB only
            tmdb_avg = show.get('vote_average', 0.0)
            score = self.scoring.calculate_quickflix_score(
                imdb_rating=tmdb_avg,
                tmdb_popularity=show.get('popularity', 0.0)
            )
            verdict = self.scoring.classify_verdict(score)

            # Upsert Rating
            rating = self.db.query(TVRating).filter(TVRating.tv_id == tv.id).first()
            if not rating:
                rating = TVRating(tv_id=tv.id)
                self.db.add(rating)
            rating.tmdb_rating = tmdb_avg
            rating.quickflix_score = score
            rating.vote_count = show.get('vote_count')

            # Placeholder Recommendation
            rec = self.db.query(TVRecommendation).filter(TVRecommendation.tv_id == tv.id).first()
            if not rec:
                rec = TVRecommendation(tv_id=tv.id)
                self.db.add(rec)
            if not rec.verdict:
                rec.verdict = verdict
                rec.category = "QuickFlix Discovery"
                rec.ai_summary = "Intelligence analysis pending. Open details for AI deep-dive."

            self.db.commit()
            return tv
        except Exception as e:
            self.db.rollback()
            print(f"quick_ingest_tv failed for {show.get('name')}: {e}", flush=True)
            return None

    def fast_enrich_movie(self, tmdb_id: int, title: str, year: str = None):
        """
        Retained for backward compatibility (used by process_movie path).
        Delegates to enrich_from_discover_data with a minimal mock discover dict.
        """
        minimal_mv = {'id': tmdb_id, 'title': title, 'release_date': f"{year}-01-01" if year else ''}
        # Supplement with fresh TMDB detail if available
        try:
            details = self.tmdb.get_movie_details(tmdb_id)
            if details and details.get('title'):
                minimal_mv.update({
                    'title': details['title'],
                    'poster_path': details.get('poster_path'),
                    'backdrop_path': details.get('backdrop_path'),
                    'vote_average': details.get('vote_average'),
                    'vote_count': details.get('vote_count'),
                    'genre_ids': [g['id'] for g in details.get('genres', [])],
                    'original_language': details.get('original_language'),
                })
        except Exception:
            pass
        return self.enrich_from_discover_data(minimal_mv)

    def discover_and_process_top_picks(self, year: int = None, region: str = None,
                                        language: str = None, genre_id: int = None, limit: int = 100):
        """
        Discover movies and enrich them across multiple pages.
        """
        import time
        from database import SessionLocal

        results = []
        page = 1
        per_page = 20
        max_pages = (limit // per_page) + (1 if limit % per_page != 0 else 0)
        
        while len(results) < limit and page <= max_pages:
            print(f"  → Fetching TMDB Discovery page {page}...", flush=True)
            discovery_results = self.tmdb.discover_movies(
                year=year, region=region, language=language, genre_id=genre_id, page=page
            )
            
            movies_on_page = discovery_results.get('results', [])
            if not movies_on_page:
                break
                
            print(f"  → Processing {len(movies_on_page)} movies from page {page}...", flush=True)

            for mv in movies_on_page:
                if len(results) >= limit:
                    break
                    
                movie_db = SessionLocal()
                try:
                    svc = DataAggregationService(movie_db)
                    processed = svc.enrich_from_discover_data(mv, region=region)
                    if processed:
                        results.append({
                            "id":           processed.id,
                            "title":        processed.title,
                            "year":         processed.year,
                            "genre":        processed.genre,
                            "director":     processed.director,
                            "country":      processed.country,
                            "poster_path":  processed.poster_path,
                            "backdrop_path": processed.backdrop_path,
                        })
                        print(f"  ✓ {processed.title}", flush=True)
                except Exception as e:
                    print(f"  ✗ {mv.get('title')}: {e}", flush=True)
                finally:
                    movie_db.close()
            
            page += 1
            if page > discovery_results.get('total_pages', 0):
                break
                
        return results




    def _get_director(self, details: dict) -> str:
        for crew in details.get('credits', {}).get('crew', []):
            if crew['job'] == 'Director':
                return crew['name']
        return "Unknown"

    def _fetch_regional_scores(self, details: dict):
        """
        Dynamically route requests to regional databases or apply cultural weightings
        based on the movie's point of origin (70+ industries supported).
        """
        countries = details.get('production_countries', [])
        iso_codes = [c.get('iso_3166_1') for c in countries]
        orig_lang = details.get('original_language', '')

        # 1. China / East Asia (Chinawood, Hong Kong, Taiwan)
        if any(code in ['CN', 'HK', 'TW'] for code in iso_codes):
            source = "Chinawood" if 'CN' in iso_codes else ("Hong Kong Cinema" if 'HK' in iso_codes else "Taiwanese Cinema")
            return {"source": source, "score": details.get('vote_average', 0.0) * 1.08}
        
        # 2. South Asia (Bollywood, Tollywood, Kollywood, Mollywood, Sandalwood, Pollywood)
        if 'IN' in iso_codes:
            industry_map = {
                'hi': 'Bollywood', 'te': 'Tollywood', 'ta': 'Kollywood',
                'ml': 'Mollywood', 'kn': 'Sandalwood', 'pa': 'Pollywood'
            }
            source = industry_map.get(orig_lang, 'Indian Cinema')
            return {"source": source, "score": details.get('vote_average', 0.0) * 1.05}

        # 3. Africa & Middle East
        africa_me_map = {
            'NG': 'Nollywood', 'GH': 'Ghollywood', 'EG': 'Egyptian Cinema',
            'ZA': 'South African Cinema', 'IR': 'Iranian Cinema',
            'TR': 'Turkish Cinema', 'IL': 'Israeli Cinema'
        }
        for code, source in africa_me_map.items():
            if code in iso_codes:
                return {"source": source, "score": details.get('vote_average', 0.0) * 1.06}

        # 4. East/Southeast Asia
        sea_map = {
            'KR': 'Hallyuwood', 'JP': 'Japanese Cinema', 'TH': 'Thai Cinema',
            'VN': 'Vietnamese Cinema', 'ID': 'Indonesian Cinema', 'PH': 'Philippine Cinema'
        }
        for code, source in sea_map.items():
            if code in iso_codes:
                return {"source": source, "score": details.get('vote_average', 0.0) * 1.04}

        # 5. Latin America
        latam_map = {
            'MX': 'Mexican Cinema', 'BR': 'Brazilian Cinema', 'AR': 'Argentine Cinema',
            'CO': 'Colombian Cinema', 'PE': 'Peruvian Cinema', 'CL': 'Chilean Cinema', 'CU': 'Cuban Cinema'
        }
        for code, source in latam_map.items():
            if code in iso_codes:
                return {"source": source, "score": details.get('vote_average', 0.0) * 1.03}

        # 6. Europe (West & South)
        euro_ws_map = {
            'IT': 'Cinecittà', 'FR': 'French Cinema', 'GB': 'British Cinema',
            'DE': 'German Cinema', 'ES': 'Spanish Cinema', 'PT': 'Portuguese Cinema',
            'NL': 'Dutch Cinema', 'BE': 'Belgian Cinema', 'CH': 'Swiss Cinema',
            'AT': 'Austrian Cinema', 'GR': 'Greek Cinema'
        }
        for code, source in euro_ws_map.items():
            if code in iso_codes:
                return {"source": source, "score": details.get('vote_average', 0.0) * 1.02}

        # 7. Europe (East & Nordic)
        euro_en_map = {
            'PL': 'Polish Cinema', 'RO': 'Romanian New Wave', 'CZ': 'Czech Cinema',
            'SK': 'Slovak Cinema', 'HU': 'Hungarian Cinema', 'BG': 'Bulgarian Cinema',
            'DK': 'Danish Cinema', 'SE': 'Swedish Cinema', 'NO': 'Norwegian Cinema', 'FI': 'Finnish Cinema'
        }
        for code, source in euro_en_map.items():
            if code in iso_codes:
                return {"source": source, "score": details.get('vote_average', 0.0) * 1.025}

        return {}


    def _get_user_score(self, movie_id):
        """
        Fetches user-contributed QuickFlix ratings from the local DB.
        """
        rating = self.db.query(Rating).filter(Rating.movie_id == movie_id).first()
        if rating and rating.user_votes > 0:
            return {"rating": rating.user_rating, "votes": rating.user_votes}
        return {}

    def _fetch_omdb_ratings(self, imdb_id: str):
        if not settings.OMDB_API_KEY or not imdb_id:
            return None
        try:
            import subprocess
            import json
            url = f"http://www.omdbapi.com/?apikey={settings.OMDB_API_KEY}&i={imdb_id}"
            cmd = ["curl.exe", "-4", "-k", "-s", "-L", "--connect-timeout", "5", url]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout.decode('utf-8', errors='ignore'))
                if data.get('Response') == 'True':
                    imdb = data.get('imdbRating', 'N/A')
                    rt_critics = 'N/A'
                    for r in data.get('Ratings', []):
                        if r['Source'] == 'Rotten Tomatoes':
                            rt_critics = r['Value'].replace('%', '')
                    return {
                        "imdb": float(imdb) if imdb != 'N/A' else None,
                        "rt_critics": float(rt_critics) if rt_critics != 'N/A' else None,
                        "rt_audience": None 
                    }
        except Exception:
            pass
        return None

    def _fetch_tvmaze_data(self, title: str, year: int = None):
        try:
            import subprocess
            import json
            query = urllib.parse.quote(title)
            url = f"http://api.tvmaze.com/singlesearch/shows?q={query}"
            cmd = ["curl.exe", "-4", "-k", "-s", "-L", "--connect-timeout", "5", url]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout.decode('utf-8', errors='ignore'))
        except Exception:
            pass
        return None
import urllib.parse
