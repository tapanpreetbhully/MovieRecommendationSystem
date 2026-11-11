from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import os
from dotenv import load_dotenv

from database.db import get_connection
from recommendation.manager import RecommendationManager
from recommendation.mood_engine import MoodRecommendationEngine
from recommendation.taste_dna import TasteDNAEngine
from recommendation.insights_engine import PersonalizedInsightsEngine
from services.tmdb_service import (
    get_movies,
    get_tv_shows,
    get_media_details,
    search_tmdb,
    get_search_suggestions,
    detect_moods,
    get_movies_by_mood,
    LANGUAGES
)

# =========================
# LOAD ENVIRONMENT
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


# =========================
# CREATE FLASK APP
# =========================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")


# =========================
# MOVIE DATASET
# =========================

DATA_PATH = os.path.join(BASE_DIR, "data", "movies.csv")

movies = pd.read_csv(DATA_PATH)


# =========================
# RECOMMENDATION SYSTEM
# =========================

recommendation_manager = RecommendationManager(DATA_PATH)
mood_engine = MoodRecommendationEngine(DATA_PATH)
taste_dna_engine = TasteDNAEngine(DATA_PATH)
insights_engine = PersonalizedInsightsEngine()


# =========================
# HOME
# =========================

@app.route("/")
def home():
    """Build the browse rows shown on the landing page from the CSV dataset."""
    # Work on a copy so presentation-only fields never affect the shared dataset
    # used by search, details, and recommendation routes.
    home_movies = movies.copy().reset_index().rename(columns={"index": "movie_id"})

    if home_movies.empty:
        return render_template(
            "index.html",
            top_rated_movies=[],
            latest_movies=[],
            popular_picks=[],
            genre_rows=[],
            language_rows=[]
        )

    # Invalid or missing values are deliberately sorted to the end.
    home_movies["_rating"] = pd.to_numeric(
        home_movies["rating"] if "rating" in home_movies else None,
        errors="coerce"
    )
    home_movies["_year"] = pd.to_numeric(
        home_movies["release_year"] if "release_year" in home_movies else None,
        errors="coerce"
    )

    def movie_records(frame, limit=12):
        """Return template-friendly records with safe display values."""
        records = []
        for _, movie in frame.head(limit).iterrows():
            def value(column, fallback=""):
                item = movie.get(column, fallback)
                return fallback if pd.isna(item) else item

            year = value("release_year", None)
            rating = value("rating", None)
            poster_url = str(value("poster_url", "")).strip()

            records.append({
                "movie_id": int(movie["movie_id"]),
                "title": str(value("title", "Untitled Movie")).strip() or "Untitled Movie",
                "genre": str(value("genre", "Genre unavailable")).strip() or "Genre unavailable",
                "language": str(value("language", "Language unavailable")).strip() or "Language unavailable",
                "release_year": int(year) if pd.notna(pd.to_numeric(year, errors="coerce")) else None,
                "rating": float(rating) if pd.notna(pd.to_numeric(rating, errors="coerce")) else None,
                "poster_url": poster_url or None
            })
        return records

    rated = home_movies.sort_values(
        ["_rating", "_year"], ascending=[False, False], na_position="last"
    )
    recent = home_movies.sort_values(
        ["_year", "_rating"], ascending=[False, False], na_position="last"
    )

    # The CSV has no popularity field, so Popular Picks combines the strongest
    # ratings with newer releases as a useful, deterministic fallback.
    genre_counts = {}
    for genre_value in home_movies.get("genre", pd.Series(dtype="object")).dropna():
        for genre in str(genre_value).split("|"):
            genre = genre.strip()
            if genre:
                genre_counts[genre] = genre_counts.get(genre, 0) + 1

    genre_rows = []
    for genre, _ in sorted(genre_counts.items(), key=lambda item: (-item[1], item[0]))[:6]:
        genre_matches = home_movies[
            home_movies["genre"].fillna("").astype(str).str.split("|").apply(
                lambda genres: genre in [item.strip() for item in genres]
            )
        ].sort_values(["_rating", "_year"], ascending=[False, False], na_position="last")
        genre_rows.append({"name": genre, "movies": movie_records(genre_matches, 10)})

    language_series = home_movies.get("language", pd.Series(dtype="object")).dropna().astype(str).str.strip()
    language_counts = language_series[language_series.ne("")].value_counts()
    language_rows = []
    for language, _ in language_counts.head(6).items():
        language_matches = home_movies[
            home_movies["language"].fillna("").astype(str).str.strip().str.casefold()
            == language.casefold()
        ].sort_values(["_rating", "_year"], ascending=[False, False], na_position="last")
        language_rows.append({"name": language, "movies": movie_records(language_matches, 10)})

    return render_template(
        "index.html",
        top_rated_movies=movie_records(rated, 10),
        latest_movies=movie_records(recent, 10),
        popular_picks=movie_records(rated, 10),
        genre_rows=genre_rows,
        language_rows=language_rows
    )


# =========================
# MOVIE LIST (REDIRECTS TO MOVIES & SERIES)
# =========================

@app.route("/movies")
def movie_list():
    return redirect(url_for("tmdb_explore", **request.args))



# =========================
# MOVIE DETAILS
# =========================


@app.route("/movie/<int:movie_id>")
def movie_details(movie_id):
    movie = None
    mysql_movie_id = movie_id

    # 1. First check MySQL movies (covers favourites, watchlist, imported movies)
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT * FROM movies
            WHERE movie_id = %s OR movie_id = %s
            LIMIT 1
            """,
            (movie_id, movie_id + 1)
        )
        row = cursor.fetchone()
        if row:
            movie = dict(row)
            mysql_movie_id = row["movie_id"]
    except Exception as e:
        print("Fetch movie from DB error:", e)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


    # 2. Fallback to dataset CSV if not found in MySQL
    if not movie:
        if 0 <= movie_id < len(movies):
            movie = movies.iloc[movie_id].to_dict()
            mysql_movie_id = movie_id + 1
        else:
            return "Movie not found", 404

    user_rating = None

    # Get the logged-in user's previous rating
    if session.get("user_id"):
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()
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

    mood_list = detect_moods(str(movie.get("genre", "")).split("|"), movie.get("description", ""))

    return render_template(
        "movie_details.html",
        movie=movie,
        movie_id=movie_id,
        user_rating=user_rating,
        moods=mood_list
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
# AI MOOD DISCOVERY
# =========================

@app.route("/ai-discovery")
def ai_discovery():

    selected_mood = request.args.get("mood", "").strip().lower()

    recommendations = []
    current_mood_info = None

    if selected_mood:
        try:
            recommendations, current_mood_info = get_movies_by_mood(
                mood=selected_mood,
                limit=24
            )
        except Exception as e:
            print("AI Discovery TMDb Error:", e)
            flash("Could not fetch movies for this mood from TMDb.", "danger")

    return render_template(
        "ai_discovery.html",
        moods=["romantic", "sad", "action", "funny", "mind_blowing", "relaxing"],
        selected_mood=selected_mood,
        recommendations=recommendations,
        current_mood_info=current_mood_info
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


@app.route("/remove-favourite/<int:movie_id>")
def remove_favourite(movie_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM favourites
            WHERE user_id = %s
            AND (movie_id = %s OR movie_id = %s)
            """,
            (session["user_id"], movie_id, movie_id + 1)
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("Movie removed from favourites.", "success")
    except Exception as e:
        print("Remove favourite error:", e)
        flash("Could not remove movie.", "danger")
    return redirect(url_for("favourites"))


# =========================
# AI TASTE DNA
# =========================

@app.route("/taste-dna")
def taste_dna():

    if not session.get("user_id"):
        flash("Please log in to view your Taste DNA.", "warning")
        return redirect(url_for("login"))

    connection = None

    try:
        connection = get_connection()

        user_id = session["user_id"]

        profile = taste_dna_engine.analyze_user(
            user_id=user_id,
            connection=connection
        )

        return render_template(
            "taste_dna.html",
            profile=profile
        )

    except Exception as e:
        print("Taste DNA Error:", e)

        flash("Could not load your Taste DNA.", "danger")
        return redirect(url_for("home"))

    finally:
        if connection:
            connection.close()


# =========================
# PERSONALIZED AI INSIGHTS
# =========================

@app.route("/ai-insights")
def ai_insights():

    if not session.get("user_id"):
        flash("Please log in to view your AI Insights.", "warning")
        return redirect(url_for("login"))

    connection = None

    try:
        connection = get_connection()

        user_id = session["user_id"]

        # Analyze the user's movie preferences.
        profile = taste_dna_engine.analyze_user(
            user_id=user_id,
            connection=connection
        )

        # Generate personalized AI insights.
        result = insights_engine.generate_insights(profile)

        return render_template(
            "ai_insights.html",
            result=result
        )

    except Exception as e:
        print("AI Insights Error:", e)

        flash("Could not generate your AI Insights.", "danger")
        return redirect(url_for("home"))

    finally:
        if connection:
            connection.close()

# =========================
# TMDB MOVIES & TV SERIES
# =========================

@app.route("/tmdb")
def tmdb_explore():
    """Browse TMDb Movies & TV Series filtered by language category."""
    media_type = request.args.get("type", "movie")  # 'movie' or 'tv'
    selected_language = request.args.get("language", "").strip()
    search_query = request.args.get("search", "").strip()

    if search_query:
        items = search_tmdb(query=search_query, media_type=media_type)
    else:
        if media_type == "tv":
            items = get_tv_shows(language=selected_language or None)
        else:
            items = get_movies(language=selected_language or None)

    return render_template(
        "tmdb_explore.html",
        items=items,
        media_type=media_type,
        selected_language=selected_language,
        languages=LANGUAGES,
        search_query=search_query
    )


@app.route("/tmdb/<string:media_type>/<int:media_id>")
def tmdb_details(media_type, media_id):
    """View TMDb details, poster, metadata, and embedded trailer."""
    if media_type not in ["movie", "tv"]:
        return "Invalid media type", 400

    item = get_media_details(media_id, media_type=media_type)
    if not item:
        flash("Could not fetch details from TMDb. Please try again.", "warning")
        return redirect(url_for("tmdb_explore"))

    return render_template("tmdb_detail.html", item=item)


def get_or_create_tmdb_in_mysql(item):
    """Ensure a TMDb title exists in MySQL movies table so interactions & Taste DNA work seamlessly."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        title = str(item.get("title", "Untitled")).strip()
        cursor.execute("SELECT movie_id FROM movies WHERE title = %s LIMIT 1", (title,))
        existing = cursor.fetchone()
        if existing:
            return existing["movie_id"]

        genres_str = "|".join(item.get("genres", []))
        year_val = None
        if str(item.get("release_year", "")).isdigit():
            year_val = int(item["release_year"])

        cursor.execute(
            """
            INSERT INTO movies (title, genre, language, release_year, director, actors, description, rating, poster_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                title,
                genres_str or "General",
                item.get("language", "Unknown"),
                year_val,
                item.get("director", "N/A"),
                item.get("actors", "N/A"),
                item.get("overview", ""),
                float(item.get("rating", 0.0)),
                item.get("poster_url", "")
            )
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@app.route("/tmdb/favourite/<int:tmdb_id>")
def tmdb_add_favourite(tmdb_id):
    if not session.get("user_id"):
        flash("Please log in to add movies to favourites.", "warning")
        return redirect(url_for("login"))

    media_type = request.args.get("media_type", "movie")
    item = get_media_details(tmdb_id, media_type=media_type)
    if not item:
        flash("Could not retrieve title from TMDb.", "danger")
        return redirect(url_for("tmdb_explore"))

    try:
        mysql_movie_id = get_or_create_tmdb_in_mysql(item)
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO favourites (user_id, movie_id) VALUES (%s, %s)",
            (session["user_id"], mysql_movie_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash(f"'{item['title']}' added to your favourites! ❤️ (Updated in Taste DNA)", "success")
    except Exception as e:
        print("TMDb Favourite error:", e)
        flash("Movie is already in your favourites.", "warning")

    return redirect(url_for("tmdb_details", media_type=media_type, media_id=tmdb_id))


@app.route("/tmdb/watchlist/<int:tmdb_id>")
def tmdb_add_watchlist(tmdb_id):
    if not session.get("user_id"):
        flash("Please log in to add movies to your watchlist.", "warning")
        return redirect(url_for("login"))

    media_type = request.args.get("media_type", "movie")
    item = get_media_details(tmdb_id, media_type=media_type)
    if not item:
        flash("Could not retrieve title from TMDb.", "danger")
        return redirect(url_for("tmdb_explore"))

    try:
        mysql_movie_id = get_or_create_tmdb_in_mysql(item)
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO watchlist (user_id, movie_id) VALUES (%s, %s)",
            (session["user_id"], mysql_movie_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash(f"'{item['title']}' added to your watchlist! 🔖 (Updated in Taste DNA)", "success")
    except Exception as e:
        print("TMDb Watchlist error:", e)
        flash("Movie is already in your watchlist.", "warning")

    return redirect(url_for("tmdb_details", media_type=media_type, media_id=tmdb_id))


@app.route("/tmdb/rate/<int:tmdb_id>", methods=["POST"])
def tmdb_rate_movie(tmdb_id):
    if not session.get("user_id"):
        flash("Please log in to rate movies.", "warning")
        return redirect(url_for("login"))

    media_type = request.args.get("media_type", "movie")
    item = get_media_details(tmdb_id, media_type=media_type)
    if not item:
        flash("Could not retrieve title from TMDb.", "danger")
        return redirect(url_for("tmdb_explore"))

    try:
        rating = int(request.form.get("rating", ""))
        if rating < 1 or rating > 5:
            flash("Please choose between 1 and 5 stars.", "warning")
            return redirect(url_for("tmdb_details", media_type=media_type, media_id=tmdb_id))
    except (ValueError, TypeError):
        flash("Invalid rating selected.", "warning")
        return redirect(url_for("tmdb_details", media_type=media_type, media_id=tmdb_id))

    try:
        mysql_movie_id = get_or_create_tmdb_in_mysql(item)
        connection = get_connection()
        cursor = connection.cursor()
        user_id = session["user_id"]

        cursor.execute(
            """
            SELECT interaction_id FROM user_interactions
            WHERE user_id = %s AND movie_id = %s AND interaction_type = 'rating'
            LIMIT 1
            """,
            (user_id, mysql_movie_id)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE user_interactions SET rating = %s, created_at = CURRENT_TIMESTAMP WHERE interaction_id = %s",
                (rating, existing["interaction_id"])
            )
        else:
            cursor.execute(
                "INSERT INTO user_interactions (user_id, movie_id, interaction_type, rating) VALUES (%s, %s, 'rating', %s)",
                (user_id, mysql_movie_id, rating)
            )
        connection.commit()
        cursor.close()
        connection.close()
        flash(f"Rated '{item['title']}' {rating} ⭐! Your AI Taste DNA has been updated.", "success")
    except Exception as e:
        print("TMDb Rate error:", e)
        flash("Could not save rating. Please try again.", "danger")

    return redirect(url_for("tmdb_details", media_type=media_type, media_id=tmdb_id))


# =========================
# LIVE SEARCH AUTOCOMPLETE API
# =========================

@app.route("/api/suggestions")
def api_suggestions():
    q = request.args.get("q", "").strip()
    suggestions = get_search_suggestions(q, limit=7)
    return {"suggestions": suggestions}


if __name__ == "__main__":
    app.run(debug=True)
