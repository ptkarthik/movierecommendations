from google import genai
from config import settings

class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = 'gemini-2.0-flash'

    def generate_recommendation_text(self, movie_data: dict):
        prompt = f"""
        ACT AS A PROFESSIONAL GLOBAL FILM RESEARCH AND RECOMMENDATION ENGINE.
        
        Analyze this movie based on verified ratings, critical reception, and cultural impact:
        {movie_data}
        
        YOUR TASK: Provide a structured, unbiased, and data-driven analysis.
        
        OUTPUT FORMAT (STRICT JSON):
        {{
            "ai_summary": "2-sentence professional summary.",
            "praise": ["List of 3 key reasons it is praised"],
            "criticism": ["List of 3 key reasons it is criticized"],
            "key_strengths": ["List of 2 technical or narrative strengths"],
            "key_weaknesses": ["List of 2 technical or narrative weaknesses"],
            "verdict": "CHOOSE ONE: ⭐ Highly Recommended | ✅ Recommended (With Notes) | ⚠️ Not Recommended",
            "instagram_caption": "3-4 line punchy caption with emojis.",
            "audience_fit": ["List of 3 audience types, e.g., 'Thriller lovers', 'Slow cinema fans'"],
            "comparisons": ["List of 2 similar culturally impactful films"]
        }}
        """
        try:
            response = self.client.models.generate_content(model=self.model_id, contents=prompt)
            return response.text
        except Exception as e:
            print(f"Gemini Analysis Error: {e}")
            return "{}"

    def generate_social_content(self, movie_data: dict):
        prompt = f"""
        Act as a professional social media manager for a premium film intelligence brand.
        Generate a viral social media package for this movie:
        {movie_data}
        
        Provide a JSON response with:
        - "reel_hook": A scroll-stopping opening line for a Reel.
        - "reel_script": A 20-30 second high-energy script for a content creator.
        - "thumbnail_headline": 3-5 words bold text for a thumbnail.
        - "hashtags": A list of 10 trending and niche hashtags.
        - "story_poll": A creative poll question for Instagram stories related to this movie.
        """
        try:
            response = self.client.models.generate_content(model=self.model_id, contents=prompt)
            return response.text
        except Exception as e:
            print(f"Gemini Social Error: {e}")
            return "{}"
