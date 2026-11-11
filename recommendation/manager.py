
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
        Existing personalized recommendation method.
        Movie IDs are zero-based CSV indexes.
        """

        favourite_movie_ids = favourite_movie_ids or []
        rated_movies = rated_movies or []

        movie_count = len(self.engine.movies)

        favourites = {
            movie_id for movie_id in favourite_movie_ids
            if isinstance(movie_id, int)
            and 0 <= movie_id < movie_count
        }

        ratings = {}

        for movie_id, rating in rated_movies:
            if 0 <= movie_id < movie_count and 1 <= rating <= 5:
                ratings[movie_id] = rating

        excluded_ids = favourites | set(ratings)

        if not favourites and not ratings:
            return self.engine.recommend(limit=limit)

        scores = {}

        for movie_id in favourites:
            similarities = self.engine.similarity_matrix[movie_id]

            for candidate_id, similarity in enumerate(similarities):
                if candidate_id in excluded_ids:
                    continue

                scores[candidate_id] = (
                    scores.get(candidate_id, 0.0)
                    + 1.5 * float(similarity)
                )

        for movie_id, rating in ratings.items():
            similarities = self.engine.similarity_matrix[movie_id]

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

    def recommend_for_user_with_explanations(
        self,
        favourite_movie_ids=None,
        rated_movies=None,
        limit=10
    ):
        """
        Generate personalized recommendations with explanations.

        Returns a list containing:
        - Movie information
        - Recommendation score
        - Reasons for recommending the movie
        """

        favourite_movie_ids = favourite_movie_ids or []
        rated_movies = rated_movies or []

        movie_count = len(self.engine.movies)

        favourites = {
            movie_id for movie_id in favourite_movie_ids
            if isinstance(movie_id, int)
            and 0 <= movie_id < movie_count
        }

        ratings = {}

        for movie_id, rating in rated_movies:
            if 0 <= movie_id < movie_count and 1 <= rating <= 5:
                ratings[movie_id] = rating

        excluded_ids = favourites | set(ratings)

        scores = {}
        reasons = {}

        # Process favourite movies.
        for movie_id in favourites:

            similarities = self.engine.similarity_matrix[movie_id]

            favourite_title = self.engine.movies.iloc[movie_id]["title"]

            for candidate_id, similarity in enumerate(similarities):

                if candidate_id in excluded_ids:
                    continue

                similarity = float(similarity)

                contribution = 1.5 * similarity

                scores[candidate_id] = (
                    scores.get(candidate_id, 0.0)
                    + contribution
                )

                if similarity > 0:
                    reason = (
                        f"Similar to {favourite_title}, "
                        "which you added to your favourites."
                    )

                    reasons.setdefault(candidate_id, []).append(reason)

        # Process user ratings.
        for movie_id, rating in ratings.items():

            similarities = self.engine.similarity_matrix[movie_id]

            rated_title = self.engine.movies.iloc[movie_id]["title"]

            preference_weight = (rating - 3) / 2.0

            for candidate_id, similarity in enumerate(similarities):

                if candidate_id in excluded_ids:
                    continue

                similarity = float(similarity)

                contribution = preference_weight * similarity

                scores[candidate_id] = (
                    scores.get(candidate_id, 0.0)
                    + contribution
                )

                if similarity > 0 and rating >= 4:
                    reason = (
                        f"Similar to {rated_title}, "
                        f"which you rated {rating}/5."
                    )

                    reasons.setdefault(candidate_id, []).append(reason)

        # Rank recommendations by their calculated scores.
        ranked_ids = sorted(
            scores,
            key=lambda candidate_id: scores[candidate_id],
            reverse=True
        )[:limit]

        recommendations = []

        for candidate_id in ranked_ids:

            movie_data = self.engine.movies.iloc[candidate_id].to_dict()

            movie_data["movie_id"] = int(candidate_id)

            movie_reasons = reasons.get(candidate_id, [])

            if not movie_reasons:
                movie_reasons = [
                    "Ranked using similarities to your saved movie preferences."
                ]

            recommendations.append({
                "movie": movie_data,
                "score": round(scores[candidate_id], 4),
                "reasons": movie_reasons[:3]
            })

        return recommendations
