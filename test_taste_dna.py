
from recommendation.taste_dna import TasteDNAEngine
from database.db import get_connection


def main():

    print("\n" + "=" * 55)
    print("          MOVIEMATE - AI TASTE DNA TEST")
    print("=" * 55)

    # Ask for user ID
    user_id = int(input("\nEnter your MySQL User ID: "))

    # Connect to database
    connection = get_connection()

    if connection is None:
        print("Database connection failed!")
        return

    try:
        # Initialize Taste DNA Engine
        engine = TasteDNAEngine("data/movies.csv")

        print("\nAnalyzing your movie preferences...")
        
        # Generate taste profile
        profile = engine.analyze_user(user_id, connection)

        print("\n" + "=" * 55)
        print("             YOUR AI TASTE DNA")
        print("=" * 55)

        print("\nUser ID:", profile["user_id"])
        print("Personality:", profile["personality"])

        print("\n--- YOUR MOVIE ACTIVITY ---")
        print("Total Ratings:", profile["total_ratings"])
        print("Total Favourites:", profile["total_favourites"])
        print("Total Watchlist Movies:", profile["total_watchlist"])

        print("\n--- YOUR RATING PROFILE ---")
        print("Average Rating:", profile["average_rating"], "/ 5")

        print("\n--- YOUR TOP GENRES ---")
        for genre, count in profile["top_genres"]:
            print(f"{genre}: {count} movies")

        print("\n--- YOUR PREFERRED LANGUAGES ---")
        for language, count in profile["top_languages"]:
            print(f"{language}: {count} movies")

        print("\n--- YOUR FAVOURITE DIRECTORS ---")
        for director, count in profile["top_directors"]:
            print(f"{director}: {count} movies")

        print("\n--- YOUR FAVOURITE ACTORS ---")
        for actor, count in profile["top_actors"]:
            print(f"{actor}: {count} movies")

        print("\n" + "=" * 55)
        print("           TASTE DNA TEST COMPLETED!")
        print("=" * 55)

    except Exception as e:
        print("\nTEST FAILED!")
        print("Error:", e)

    finally:
        connection.close()


if __name__ == "__main__":
    main()
