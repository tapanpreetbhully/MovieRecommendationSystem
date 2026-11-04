
from recommendation.content_based import ContentBasedEngine


class RecommendationManager:
    def __init__(self, data_path):
        self.engine = ContentBasedEngine(data_path)

    def recommend(self, movie_id=None, limit=10):
        return self.engine.recommend(
            movie_id=movie_id,
            limit=limit
        )

    def recommend_for_user(
        self,
        favourite_movie_ids=None,
        rated_movies=None,
        limit=10
    ):
        """
        Personalize recommendations using favourites and ratings.

        All movie IDs are zero-based CSV indexes.
        rated_movies is a list of (movie_id, rating) pairs.
        """

        favourite_movie_ids = favourite_movie_ids or []
        rated_movies = rated_movies or []

        movie_count = len(self.engine.movies)

        # Collect valid preferences.
        favourites = {
            movie_id for movie_id in favourite_movie_ids
            if isinstance(movie_id, int) and 0 <= movie_id < movie_count
        }

        ratings = {}
        for movie_id, rating in rated_movies:
            if 0 <= movie_id < movie_count and 1 <= rating <= 5:
                ratings[movie_id] = rating

        # Movies already favourited or rated should not be recommended.
        excluded_ids = favourites | set(ratings)

        if not favourites and not ratings:
            return self.engine.recommend(limit=limit)

        scores = {}

        # Favourites provide a positive preference signal.
        for movie_id in favourites:
            similarities = self.engine.similarity_matrix[movie_id]

            for candidate_id, similarity in enumerate(similarities):
                if candidate_id in excluded_ids:
                    continue

                scores[candidate_id] = (
                    scores.get(candidate_id, 0.0)
                    + 1.5 * float(similarity)
                )

        # Ratings influence how strongly similar movies are recommended.
        for movie_id, rating in ratings.items():
            similarities = self.engine.similarity_matrix[movie_id]

            # Positive for 4–5 stars, neutral for 3, negative for 1–2.
            preference_weight = (rating - 3) / 2.0

            for candidate_id, similarity in enumerate(similarities):
                if candidate_id in excluded_ids:
                    continue

                scores[candidate_id] = (
                    scores.get(candidate_id, 0.0)
                    + preference_weight * float(similarity)
                )

        ranked_ids = sorted(
            scores,
            key=lambda candidate_id: scores[candidate_id],
            reverse=True
        )[:limit]

        return self.engine.movies.iloc[ranked_ids]
