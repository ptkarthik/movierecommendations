from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Movie(Base):
    __tablename__ = "movies"
    
    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, unique=True, index=True, nullable=True)
    title = Column(String, index=True)
    year = Column(Integer, index=True)
    country = Column(String, index=True)
    language = Column(String, index=True)
    genre = Column(String, index=True)
    director = Column(String)
    runtime = Column(Integer)
    poster_path = Column(String)
    backdrop_path = Column(String)
    quickflix_score = Column(Float, index=True, default=0.0)
    imdb_rating = Column(Float, index=True, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships for optimized querying (joinedload)
    ratings = relationship("Rating", back_populates="movie", uselist=False)
    recommendations = relationship("Recommendation", back_populates="movie", uselist=False)

class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"))
    imdb_rating = Column(Float, index=True)
    tmdb_rating = Column(Float, index=True)
    rotten_critics = Column(Float)
    rotten_audience = Column(Float)
    quickflix_score = Column(Float, index=True)
    vote_count = Column(Integer)
    user_rating = Column(Float, default=0.0, index=True)
    user_votes = Column(Integer, default=0)

    movie = relationship("Movie", back_populates="ratings")

class Recommendation(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"))
    category = Column(String) 
    ai_summary = Column(String)
    praise = Column(JSON)
    criticism = Column(JSON)
    key_strengths = Column(JSON)
    key_weaknesses = Column(JSON)
    verdict = Column(String)
    instagram_caption = Column(String)
    availability = Column(String) 
    audience_fit = Column(JSON)
    comparisons = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    movie = relationship("Movie", back_populates="recommendations")

class TVSeries(Base):
    __tablename__ = "tv_series"
    
    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, unique=True, index=True, nullable=True)
    title = Column(String, index=True)
    year = Column(Integer, index=True)
    country = Column(String, index=True)
    language = Column(String, index=True)
    genre = Column(String, index=True)
    creator = Column(String)
    status = Column(String) 
    seasons = Column(Integer)
    episodes = Column(Integer)
    poster_path = Column(String)
    backdrop_path = Column(String)
    quickflix_score = Column(Float, index=True, default=0.0)
    imdb_rating = Column(Float, index=True, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships for optimized querying
    ratings = relationship("TVRating", back_populates="tv_series", uselist=False)
    recommendations = relationship("TVRecommendation", back_populates="tv_series", uselist=False)

class TVRating(Base):
    __tablename__ = "tv_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    tv_id = Column(Integer, ForeignKey("tv_series.id"))
    imdb_rating = Column(Float, index=True)
    tmdb_rating = Column(Float, index=True)
    rotten_critics = Column(Float)
    rotten_audience = Column(Float)
    quickflix_score = Column(Float, index=True)
    vote_count = Column(Integer)
    user_rating = Column(Float, default=0.0, index=True)
    user_votes = Column(Integer, default=0)

    tv_series = relationship("TVSeries", back_populates="ratings")

class TVRecommendation(Base):
    __tablename__ = "tv_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    tv_id = Column(Integer, ForeignKey("tv_series.id"))
    category = Column(String)
    ai_summary = Column(String)
    praise = Column(JSON)
    criticism = Column(JSON)
    key_strengths = Column(JSON)
    key_weaknesses = Column(JSON)
    verdict = Column(String)
    instagram_caption = Column(String)
    availability = Column(String)
    audience_fit = Column(JSON)
    comparisons = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tv_series = relationship("TVSeries", back_populates="recommendations")
