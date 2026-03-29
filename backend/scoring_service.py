class ScoringService:
    @staticmethod
    def calculate_quickflix_score(
        imdb_rating: float = None, 
        rt_critics: float = None, 
        rt_audience: float = None, 
        tmdb_popularity: float = None,
        tvmaze_rating: float = None,
        regional_rating: float = None,
        user_rating: float = None
    ) -> float:
        """
        Calculates a dynamic weighted average (0-100) based ONLY on available databases.
        Weights:
        - IMDb (0-10): 4.0
        - RT Critics (0-100): 3.0
        - RT Audience (0-100): 2.0
        - TMDB Popularity: 1.0 (normalized)
        - TVMaze (0-10): 2.0
        - Regional Rating (Douban/NollyData) (0-100): 4.0 (High priority for Global First)
        - User Contributed Rating (0-10): 3.0
        """
        weighted_sum = 0.0
        total_weight = 0.0

        # IMDb (Scale 0-10 -> 0-100)
        if imdb_rating and imdb_rating > 0:
            weighted_sum += (imdb_rating * 10.0) * 4.0
            total_weight += 4.0

        # RT Critics (Scale 0-100)
        if rt_critics and rt_critics > 0:
            weighted_sum += rt_critics * 3.0
            total_weight += 3.0

        # RT Audience (Scale 0-100)
        if rt_audience and rt_audience > 0:
            weighted_sum += rt_audience * 2.0
            total_weight += 2.0

        # TMDB Popularity (Normalized approx 0-100)
        # We use a logarithmic-ish scale so lower popularities don't crush the score
        if tmdb_popularity and tmdb_popularity > 0:
            import math
            # log10(pop+1) * 20 gives a decent 0-100 range for most pops
            norm_pop = min(math.log10(tmdb_popularity + 1) * 35.0, 100.0)
            weighted_sum += norm_pop * 0.5 # Reduced weight for volume-based metric
            total_weight += 0.5

        # TVMaze (Scale 0-10 -> 0-100)
        if tvmaze_rating and tvmaze_rating > 0:
            weighted_sum += (tvmaze_rating * 10.0) * 2.0
            total_weight += 2.0

        # Regional Rating (Scale 0-100)
        if regional_rating and regional_rating > 0:
            weighted_sum += regional_rating * 4.0
            total_weight += 4.0
            
        # User Rating (Scale 0-10 -> 0-100)
        if user_rating and user_rating > 0:
            weighted_sum += (user_rating * 10.0) * 3.0
            total_weight += 3.0

        if total_weight == 0:
            return 0.0
            
        quickflix_score = weighted_sum / total_weight
        return round(min(quickflix_score, 100), 1)

    @staticmethod
    def classify_verdict(score: float) -> str:
        # Score is now 0-100
        if score >= 85:
            return "💎 Platinum Pick"
        elif score >= 75:
            return "🔥 Must Watch"
        elif score >= 60:
            return "✅ Recommended"
        elif score >= 40:
            return "🍿 Casual Watch"
        else:
            return "❌ Skip It"

    @staticmethod
    def calculate_final_score(imdb_rating: float, rt_critics: float, rt_audience: float, awards_count: int = 0) -> float:
        # Keeping for backward compatibility if needed
        return ScoringService.calculate_quickflix_score(imdb_rating, rt_critics, rt_audience) / 10.0
