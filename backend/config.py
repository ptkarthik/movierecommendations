from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///c:/Users/Karthik/.gemini/antigravity/scratch/global-movie-intelligence/backend/master_aligned.db" # Standardized absolute path
    TMDB_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OMDB_API_KEY: str = "" # Required for authentic IMDb/RT scores
    
    class Config:
        env_file = ".env"

settings = Settings()
