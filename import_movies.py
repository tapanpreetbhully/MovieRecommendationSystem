import pandas as pd
from database.db import get_connection


# Read CSV
movies = pd.read_csv("data/movies.csv")


# Convert every missing value to Python None
movies = movies.astype(object).where(pd.notna(movies), None)


# Connect to MySQL
connection = get_connection()
cursor = connection.cursor()


try:

    for _, movie in movies.iterrows():

        title = movie["title"]
        genre = movie["genre"]
        language = movie["language"]
        release_year = movie["release_year"]
        director = movie["director"]
        actors = movie["actors"]
        description = movie["description"]
        rating = movie["rating"]
        poster_url = movie["poster_url"]

        cursor.execute(
            """
            INSERT INTO movies
            (
                title,
                genre,
                language,
                release_year,
                director,
                actors,
                description,
                rating,
                poster_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                title,
                genre,
                language,
                release_year,
                director,
                actors,
                description,
                rating,
                poster_url
            )
        )

    connection.commit()

    print("Movies imported successfully!")
    print(f"Total movies imported: {len(movies)}")

except Exception as e:

    connection.rollback()

    print("Error while importing movies:")
    print(e)

finally:

    cursor.close()
    connection.close()