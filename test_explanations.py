
from database.db import get_connection
from recommendation.manager import RecommendationManager

print("\n" + "=" * 60)
print("       MOVIEMATE - AI RECOMMENDATION EXPLANATIONS")
print("=" * 60)

connection = None
cursor = None

try:
    user_id = int(input("\nEnter your MySQL User ID: "))

    connection = get_connection()
    cursor = connection.cursor()

    # Get user's favourite movies.
    cursor.execute("""
        SELECT movie_id
        FROM favourites
        WHERE user_id = %s
    """, (user_id,))

    favourite_rows = cursor.fetchall()

    favourite_movie_ids = [
        int(row["movie_id"]) - 1
        for row in favourite_rows
    ]

    # Get user's movie ratings.
    cursor.execute("""
        SELECT movie_id, rating
        FROM user_interactions
        WHERE user_id = %s
          AND interaction_type = 'rating'
          AND rating IS NOT NULL
    """, (user_id,))

    rating_rows = cursor.fetchall()

    rated_movies = [
        (int(row["movie_id"]) - 1, float(row["rating"]))
        for row in rating_rows
    ]

finally:
    if cursor:
        cursor.close()

    if connection:
        connection.close()

try:
    manager = RecommendationManager("data/movies.csv")

    recommendations = manager.recommend_for_user_with_explanations(
        favourite_movie_ids=favourite_movie_ids,
        rated_movies=rated_movies,
        limit=5
    )

    print("\n" + "=" * 60)
    print("          YOUR PERSONALIZED MOVIE PICKS")
    print("=" * 60)

    if not recommendations:
        print("\nNo recommendations available yet.")
        print("Add favourites or rate some movies first.")

    for index, item in enumerate(recommendations, start=1):

        movie = item["movie"]

        print(f"\n{index}. {movie['title']}")
        print("-" * 50)

        print("Genre:", movie["genre"])
        print("Rating:", movie["rating"])

        print("\nWhy MovieMate recommends this movie:")

        for reason in item["reasons"]:
            print("  ✓", reason)

    print("\n" + "=" * 60)
    print("       AI EXPLANATION TEST COMPLETED!")
    print("=" * 60)

except Exception as error:
    print("\nTEST FAILED!")
    print("Error:", error)
