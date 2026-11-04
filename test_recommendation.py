from recommendation.manager import RecommendationManager


DATA_PATH = "data/movies.csv"


recommendation_manager = RecommendationManager(DATA_PATH)

recommendations = recommendation_manager.recommend(
    movie_id=0,
    limit=5
)

print("\nRecommended Movies:\n")

for _, movie in recommendations.iterrows():
    print(
        f"- {movie['title']} "
        f"({movie['release_year']}) "
        f"| Rating: {movie['rating']}"
    )