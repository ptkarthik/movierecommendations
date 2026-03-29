import json
import subprocess
import os
import sys
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append('c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend')

from aggregation_service import DataAggregationService
from models import Movie, Rating
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_mock_omdb_limit():
    # Setup mock DB
    engine = create_engine('sqlite:///:memory:')
    Session = sessionmaker(bind=engine)
    db = Session()
    from models import Base
    Base.metadata.create_all(bind=engine)
    
    # Create test movie
    movie = Movie(tmdb_id=12345, title="Mock Movie", year="2024")
    db.add(movie)
    db.commit()
    
    aggregator = DataAggregationService(db)
    
    # Mock TMDB detail call
    aggregator.tmdb.get_movie_details = MagicMock(return_value={
        'id': 12345,
        'title': 'Mock Movie',
        'vote_average': 7.5,
        'vote_count': 100,
        'popularity': 50.0,
        'imdb_id': 'tt1234567'
    })
    
    # Mock Gemini to avoid ModuleNotFoundError
    aggregator.gemini = MagicMock()
    aggregator.gemini.generate_recommendation_text = MagicMock(return_value='{"ai_summary": "Test"}')
    
    # Mock subprocess.run for curl (OMDb limit)
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps({"Response":"False","Error":"Request limit reached!"}).encode('utf-8')
    
    with patch('subprocess.run', return_value=mock_res):
        print("Testing OMDb limit handling...")
        # Simulate discovery data
        mv = {
            'id': 12345,
            'title': 'Mock Movie',
            'vote_average': 7.5,
            'vote_count': 100,
            'popularity': 50.0
        }
        processed = aggregator.enrich_from_discover_data(mv)
        
        rating = db.query(Rating).filter(Rating.movie_id == processed.id).first()
        print(f"Results for '{processed.title}':")
        print(f"  IMDb Rating: {rating.imdb_rating} (Expected: None)")
        print(f"  TMDB Rating: {rating.tmdb_rating} (Expected: 7.5)")
        print(f"  QuickFlix Score: {rating.quickflix_score} (Expected: > 0)")
        
        if rating.tmdb_rating == 7.5 and rating.quickflix_score > 0:
            print("SUCCESS: System fell back to TMDB correctly.")
        else:
            print("FAILURE: System did not handle limit correctly.")

if __name__ == "__main__":
    test_mock_omdb_limit()
