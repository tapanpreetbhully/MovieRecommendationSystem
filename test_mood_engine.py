
from recommendation.mood_engine import MoodRecommendationEngine


def main():

    # Initialize the mood recommendation engine
    engine = MoodRecommendationEngine("data/movies.csv")

    # Available moods
    moods = [
        "mind_blowing",
        "funny",
        "romantic",
        "action",
        "emotional",
        "relaxing"
    ]

    # Test each mood
    for mood in moods:

        print("\n" + "=" * 50)
        print("MOOD:", mood.upper())
        print("=" * 50)

        try:

            recommendations = engine.recommend_by_mood(
                mood=mood,
                limit=5
            )

            if not recommendations:
                print("No matching movies found.")
                continue

            for movie in recommendations:

                print("\nMovie:", movie["title"])
                print("Genre:", movie["genre"])
                print("Language:", movie["language"])
                print("Movie Rating:", movie["rating"])
                print("Mood Match Score:", movie["match_score"], "%")
                print("Why Recommended:", movie["reason"])

        except Exception as e:
            print("Error while testing mood:", mood)
            print("Details:", e)


if __name__ == "__main__":
    main()
