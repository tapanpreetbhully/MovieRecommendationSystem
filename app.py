from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import os
from dotenv import load_dotenv

from database.db import get_connection
from recommendation.manager import RecommendationManager


# =========================
# LOAD ENVIRONMENT
# =========================

load_dotenv()


# =========================
# CREATE FLASK APP
# =========================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")


# =========================
# MOVIE DATASET
# =========================

DATA_PATH = "data/movies.csv"

movies = pd.read_csv(DATA_PATH)


# =========================
# RECOMMENDATION SYSTEM
# =========================

recommendation_manager = RecommendationManager(DATA_PATH)


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# MOVIE LIST
# =========================

@app.route("/movies")
def movie_list():
    search_query = request.args.get("search", "").strip().lower()
    selected_genre = request.args.get("genre", "").strip()
    selected_language = request.args.get("language", "").strip()

    filtered_movies = movies.copy()

    # Search by movie title
    if search_query:
        filtered_movies = filtered_movies[
            filtered_movies["title"].fillna("").str.lower().str.contains(
                search_query, regex=False
            )
        ]

    # Filter by genre
    if selected_genre:
        filtered_movies = filtered_movies[
            filtered_movies["genre"].fillna("").str.contains(
                selected_genre, case=False, regex=False
            )
        ]

    # Filter by language
    if selected_language:
        filtered_movies = filtered_movies[
            filtered_movies["language"].fillna("").str.lower()
            == selected_language.lower()
        ]

    movie_data = filtered_movies.reset_index().rename(
        columns={"index": "movie_id"}
    ).to_dict(orient="records")
    
    genres = sorted(
        movies["genre"].dropna().str.split(",").explode().str.strip().unique()
    )
    languages = sorted(movies["language"].dropna().unique())

    return render_template(
        "movies.html",
        movies=movie_data,
        genres=genres,
        languages=languages,
        search_query=search_query,
        selected_genre=selected_genre,
        selected_language=selected_language
    )



# =========================
# MOVIE DETAILS
# =========================


@app.route("/movie/<int:movie_id>")
def movie_details(movie_id):

    if movie_id < 0 or movie_id >= len(movies):
        return "Movie not found", 404

    movie = movies.iloc[movie_id].to_dict()

    user_rating = None

    # Get the logged-in user's previous rating
    if session.get("user_id"):
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            mysql_movie_id = movie_id + 1
            user_id = session["user_id"]

            cursor.execute(
                """
                SELECT rating
                FROM user_interactions
                WHERE user_id = %s
                  AND movie_id = %s
                  AND interaction_type = 'rating'
                LIMIT 1
                """,
                (user_id, mysql_movie_id)
            )

            result = cursor.fetchone()

            if result and result["rating"] is not None:
                user_rating = int(float(result["rating"]))

        except Exception as e:
            print("Fetch movie rating error:", e)

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template(
        "movie_details.html",
        movie=movie,
        movie_id=movie_id,
        user_rating=user_rating
    )



# =========================
# RECOMMENDATIONS
# =========================

@app.route("/recommendations/<int:movie_id>")
def recommendations(movie_id):

    if movie_id < 0 or movie_id >= len(movies):
        return "Movie not found", 404

    selected_movie = movies.iloc[movie_id].to_dict()

    recommended_movies = recommendation_manager.recommend(
        movie_id=movie_id,
        limit=5
    )

    recommendations_list = []

    for movie_index, movie in recommended_movies.iterrows():
        movie_data = movie.to_dict()
        movie_data["movie_id"] = int(movie_index)
        recommendations_list.append(movie_data)
    

    return render_template(
        "recommendations.html",
        movie=selected_movie,
        recommendations=recommendations_list
    )


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        try:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO users (name, email, password)
                VALUES (%s, %s, %s)
                """,
                (name, email, password_hash)
            )

            connection.commit()

            cursor.close()
            connection.close()

            flash(
                "Account created successfully!",
                "success"
            )

            return redirect(url_for("login"))

        except Exception as e:

            print("Registration error:", e)

            flash(
                "Email may already be registered.",
                "danger"
            )

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        try:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

            cursor.close()
            connection.close()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session["user_id"] = user["user_id"]
                session["user_name"] = user["name"]
                session["user_email"] = user["email"]

                flash(
                    "Login successful!",
                    "success"
                )

                return redirect(url_for("home"))

            else:

                flash(
                    "Invalid email or password.",
                    "danger"
                )

        except Exception as e:

            print("Login error:", e)

            flash(
                "Something went wrong. Please try again.",
                "danger"
            )

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("home"))


# =========================
# ADD TO WATCHLIST
# =========================

@app.route("/add-watchlist/<int:movie_id>")
def add_watchlist(movie_id):

    if not session.get("user_id"):
        return redirect(url_for("login"))

    if movie_id < 0 or movie_id >= len(movies):
        return "Movie not found", 404

    try:

        connection = get_connection()
        cursor = connection.cursor()

        # CSV index starts from 0
        # MySQL movie_id starts from 1
        mysql_movie_id = movie_id + 1

        cursor.execute(
            """
            INSERT INTO watchlist (user_id, movie_id)
            VALUES (%s, %s)
            """,
            (
                session["user_id"],
                mysql_movie_id
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "Movie added to your watchlist!",
            "success"
        )

    except Exception as e:

        print("Watchlist error:", e)

        flash(
            "Movie is already in your watchlist.",
            "warning"
        )

    return redirect(
        url_for(
            "movie_details",
            movie_id=movie_id
        )
    )


# =========================
# MY WATCHLIST
# =========================

@app.route("/watchlist")
def watchlist():

    if not session.get("user_id"):
        return redirect(url_for("login"))

    try:

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT m.*
            FROM movies m
            INNER JOIN watchlist w
                ON m.movie_id = w.movie_id
            WHERE w.user_id = %s
            ORDER BY w.added_at DESC
            """,
            (session["user_id"],)
        )

        watchlist_movies = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template(
            "watchlist.html",
            movies=watchlist_movies
        )

    except Exception as e:

        print("Watchlist page error:", e)

        return "Something went wrong", 500


# =========================
# REMOVE FROM WATCHLIST
# =========================

@app.route("/remove-watchlist/<int:movie_id>")
def remove_watchlist(movie_id):

    if not session.get("user_id"):
        return redirect(url_for("login"))

    try:

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM watchlist
            WHERE user_id = %s
            AND movie_id = %s
            """,
            (
                session["user_id"],
                movie_id
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "Movie removed from watchlist.",
            "success"
        )

    except Exception as e:

        print("Remove watchlist error:", e)

        flash(
            "Could not remove movie.",
            "danger"
        )

    return redirect(url_for("watchlist"))


@app.route("/add-favourite/<int:movie_id>")
def add_favourite(movie_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if movie_id < 0 or movie_id >= len(movies):
        return "Movie not found", 404

    try:
        connection = get_connection()
        cursor = connection.cursor()

        mysql_movie_id = movie_id + 1

        cursor.execute(
            """
            INSERT INTO favourites (user_id, movie_id)
            VALUES (%s, %s)
            """,
            (session["user_id"], mysql_movie_id)
        )

        connection.commit()
        cursor.close()
        connection.close()

        flash("Movie added to favourites! ❤️", "success")

    except Exception as e:
        print("Favourite error:", e)
        flash("Movie is already in your favourites.", "warning")

    return redirect(url_for("movie_details", movie_id=movie_id))   

# =========================
# RATE A MOVIE
# =========================

@app.route("/rate-movie/<int:movie_id>", methods=["POST"])
def rate_movie(movie_id):
    if not session.get("user_id"):
        flash("Please log in to rate movies.", "warning")
        return redirect(url_for("login"))

    if movie_id < 0 or movie_id >= len(movies):
        return "Movie not found", 404

    try:
        rating = int(request.form.get("rating", ""))

        if rating < 1 or rating > 5:
            flash("Please select a rating from 1 to 5 stars.", "warning")
            return redirect(url_for("movie_details", movie_id=movie_id))

    except (ValueError, TypeError):
        flash("Please select a valid rating.", "warning")
        return redirect(url_for("movie_details", movie_id=movie_id))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Convert zero-based CSV index to MySQL movie ID.
        mysql_movie_id = movie_id + 1
        user_id = session["user_id"]

        # Check whether this user has already rated this movie.
        cursor.execute(
            """
            SELECT interaction_id
            FROM user_interactions
            WHERE user_id = %s
              AND movie_id = %s
              AND interaction_type = 'rating'
            LIMIT 1
            """,
            (user_id, mysql_movie_id)
        )

        existing_rating = cursor.fetchone()

        if existing_rating:
            cursor.execute(
                """
                UPDATE user_interactions
                SET rating = %s, created_at = CURRENT_TIMESTAMP
                WHERE interaction_id = %s
                """,
                (rating, existing_rating["interaction_id"])
            )
            message = "Your movie rating has been updated! ⭐"

        else:
            cursor.execute(
                """
                INSERT INTO user_interactions
                    (user_id, movie_id, interaction_type, rating)
                VALUES (%s, %s, 'rating', %s)
                """,
                (user_id, mysql_movie_id, rating)
            )
            message = "Your rating has been saved! ⭐"

        connection.commit()
        flash(message, "success")

    except Exception as e:
        if connection:
            connection.rollback()

        print("Movie rating error:", e)
        flash("Could not save your rating. Please try again.", "danger")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for("movie_details", movie_id=movie_id))

# =========================
# RUN APPLICATION
# =========================


@app.route("/personalized-recommendations")
def personalized_recommendations():
    if not session.get("user_id"):
        flash(
            "Please log in to see personalized recommendations.",
            "warning"
        )
        return redirect(url_for("login"))

    connection = None
    cursor = None
    user_id = session["user_id"]

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get favourite movie IDs from MySQL.
        cursor.execute(
            """
            SELECT movie_id
            FROM favourites
            WHERE user_id = %s
            """,
            (user_id,)
        )
        favourite_rows = cursor.fetchall()

        favourite_movie_ids = [
            row["movie_id"] - 1
            for row in favourite_rows
            if 1 <= row["movie_id"] <= len(movies)
        ]

        # Get the user's saved ratings.
        cursor.execute(
            """
            SELECT movie_id, rating
            FROM user_interactions
            WHERE user_id = %s
              AND interaction_type = 'rating'
              AND rating IS NOT NULL
            """,
            (user_id,)
        )
        rating_rows = cursor.fetchall()

        rated_movies = [
            (row["movie_id"] - 1, float(row["rating"]))
            for row in rating_rows
            if (
                row["movie_id"] is not None
                and 1 <= row["movie_id"] <= len(movies)
                and row["rating"] is not None
                and 1 <= float(row["rating"]) <= 5
            )
        ]

    except Exception as e:
        print("Personalized recommendations error:", e)
        flash("Could not load your preferences.", "danger")
        return redirect(url_for("home"))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    recommendations_df = recommendation_manager.recommend_for_user(
        favourite_movie_ids=favourite_movie_ids,
        rated_movies=rated_movies,
        limit=10
    )

    recommendations_list = []

    for movie_index, movie in recommendations_df.iterrows():
        movie_data = movie.to_dict()
        movie_data["movie_id"] = int(movie_index)
        recommendations_list.append(movie_data)

    return render_template(
        "recommendations.html",
        movie={"title": "Your Personalized Picks"},
        recommendations=recommendations_list,
        personalized=True
    )


# =========================
# FOR FAVOURITES
# =========================

@app.route("/favourites")
def favourites():
    if not session.get("user_id"):
        flash("Please log in to view your favourites.", "warning")
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                m.movie_id AS database_movie_id,
                m.title,
                m.genre,
                m.language,
                m.release_year,
                m.director,
                m.actors,
                m.description,
                m.rating,
                m.poster_url
            FROM favourites f
            JOIN movies m ON f.movie_id = m.movie_id
            WHERE f.user_id = %s
            ORDER BY f.created_at DESC
            """,
            (session["user_id"],)
        )

        favourite_movies = cursor.fetchall()

        return render_template(
            "favourites.html",
            favourites=favourite_movies
        )

    except Exception as e:
        print("Favourites error:", e)
        flash("Could not load your favourites.", "danger")
        return redirect(url_for("home"))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    

if __name__ == "__main__":
    app.run(debug=True)
 