
from database.db import get_connection
from recommendation.taste_dna import TasteDNAEngine
from recommendation.insights_engine import PersonalizedInsightsEngine

print("\n" + "=" * 55)
print("       MOVIEMATE - PERSONALIZED AI INSIGHTS TEST")
print("=" * 55)

try:
    user_id = int(input("\nEnter your MySQL User ID: "))

    connection = get_connection()

    try:
        taste_engine = TasteDNAEngine("data/movies.csv")
        profile = taste_engine.analyze_user(user_id, connection)
    finally:
        connection.close()

    insights_engine = PersonalizedInsightsEngine()
    result = insights_engine.generate_insights(profile)

    print("\n" + "=" * 55)
    print("           YOUR PERSONALIZED AI INSIGHTS")
    print("=" * 55)

    print("\nMovie Personality:", result["personality"])

    for insight in result["insights"]:
        print("\n" + "-" * 55)
        print(insight["icon"], insight["title"])
        print("-" * 55)
        print(insight["description"])

        if insight.get("suggested_genres"):
            print("\nSuggested Genres:")
            print(", ".join(insight["suggested_genres"]))

    print("\n" + "=" * 55)
    print("       AI INSIGHTS GENERATED SUCCESSFULLY!")
    print("=" * 55)

except Exception as error:
    print("\nTEST FAILED!")
    print("Error:", error)
