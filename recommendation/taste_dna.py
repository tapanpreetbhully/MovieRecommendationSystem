from collections import Counter
import pandas as pd


class TasteDNAEngine:

    def __init__(self, data_path):
        self.movies = pd.read_csv(data_path)

    def get_value(self, row, column, index):
        """Support both dictionary and tuple database rows."""
        if isinstance(row, dict):
            return row.get(column)
        return row[index]

    def analyze_user(self, user_id, connection):

        cursor = connection.cursor()

        try:
            # 1. Get user ratings
            cursor.execute("""
                SELECT movie_id, rating
                FROM user_interactions
                WHERE user_id = %s
                AND interaction_type = 'rating'
                AND rating IS NOT NULL
            """, (user_id,))

            ratings = cursor.fetchall()

            # 2. Get favourite movies
            cursor.execute("""
                SELECT movie_id
                FROM favourites
                WHERE user_id = %s
            """, (user_id,))

            favourites = cursor.fetchall()

            # 3. Get watchlist movies
            cursor.execute("""
                SELECT movie_id
                FROM watchlist
                WHERE user_id = %s
            """, (user_id,))

            watchlist = cursor.fetchall()

        finally:
            cursor.close()

        # Extract movie IDs safely
        rated_ids = [
            int(self.get_value(row, "movie_id", 0))
            for row in ratings
        ]

        favourite_ids = [
            int(self.get_value(row, "movie_id", 0))
            for row in favourites
        ]

        watchlist_ids = [
            int(self.get_value(row, "movie_id", 0))
            for row in watchlist
        ]

        all_ids = set(rated_ids + favourite_ids + watchlist_ids)

        profile = {
            "user_id": user_id,
            "total_ratings": len(ratings),
            "total_favourites": len(favourite_ids),
            "total_watchlist": len(watchlist_ids),
            "average_rating": 0,
            "top_genres": [],
            "top_languages": [],
            "top_directors": [],
            "top_actors": [],
            "mood_breakdown": [],
            "top_mood": "Versatile",
            "personality": "New Explorer"
        }

        if not all_ids:
            return profile

        placeholders = ",".join(["%s"] * len(all_ids))

        movie_cursor = connection.cursor()

        try:
            movie_cursor.execute(
                f"""
                SELECT title, genre, language, director, actors, description
                FROM movies
                WHERE movie_id IN ({placeholders})
                """,
                tuple(all_ids)
            )

            movie_data = movie_cursor.fetchall()

        finally:
            movie_cursor.close()

        genres = Counter()
        languages = Counter()
        directors = Counter()
        actors = Counter()
        mood_counter = Counter()

        for row in movie_data:

            genre = self.get_value(row, "genre", 1) or ""
            language = self.get_value(row, "language", 2) or ""
            director = self.get_value(row, "director", 3) or ""
            actor_list = self.get_value(row, "actors", 4) or ""
            description = (self.get_value(row, "description", 5) or "").lower()

            # Count genres
            if genre:
                genre_items = [item.strip() for item in genre.replace(",", "|").split("|") if item.strip()]
                genres.update(genre_items)
            else:
                genre_items = []

            # Count languages
            if language:
                languages.update([language.strip()])

            # Count directors
            if director:
                directors.update(
                    item.strip() for item in director.replace(",", "|").split("|")
                    if item.strip()
                )

            # Count actors
            if actor_list:
                actors.update(
                    item.strip() for item in actor_list.replace(",", "|").split("|")
                    if item.strip()
                )

            # Analyze Category & Mood (Romantic, Sad, Funny, Action, Mind-Blowing, Relaxing)
            genre_lower = [g.lower() for g in genre_items]

            # 1. Romantic
            if "romance" in genre_lower or any(kw in description for kw in ["love", "romance", "romantic", "couple", "heart"]):
                mood_counter["Romantic"] += 1

            # 2. Sad / Emotional
            if ("drama" in genre_lower and any(kw in description for kw in ["sad", "death", "tragedy", "loss", "grief", "heartbreak"])) or "tragedy" in description:
                mood_counter["Sad / Emotional"] += 1
            elif "drama" in genre_lower:
                mood_counter["Deep Drama"] += 1

            # 3. Funny / Comedy
            if "comedy" in genre_lower or any(kw in description for kw in ["funny", "comedy", "laugh", "hilarious"]):
                mood_counter["Funny / Comedy"] += 1

            # 4. Action & Thrill
            if any(g in genre_lower for g in ["action", "adventure", "war"]) or any(kw in description for kw in ["action", "fight", "battle", "heist"]):
                mood_counter["Action & Thrill"] += 1

            # 5. Mind-Blowing
            if any(g in genre_lower for g in ["thriller", "mystery", "sci-fi", "science fiction"]) or any(kw in description for kw in ["twist", "psychological", "dream", "mystery"]):
                mood_counter["Mind-Blowing"] += 1

            # 6. Relaxing / Feel-Good
            if any(g in genre_lower for g in ["animation", "family", "music"]) or any(kw in description for kw in ["friendship", "wholesome", "peaceful"]):
                mood_counter["Feel-Good"] += 1

        # Calculate average user rating
        if ratings:
            rating_values = [
                float(self.get_value(row, "rating", 1))
                for row in ratings
            ]

            profile["average_rating"] = round(
                sum(rating_values) / len(rating_values), 2
            )

        profile["top_genres"] = genres.most_common(5)
        profile["top_languages"] = languages.most_common(5)
        profile["top_directors"] = directors.most_common(3)
        profile["top_actors"] = actors.most_common(5)

        # Build Mood Breakdown with percentages
        total_mood_hits = sum(mood_counter.values()) or 1
        mood_meta = {
            "Romantic": {"emoji": "💖", "color": "danger"},
            "Sad / Emotional": {"emoji": "😢", "color": "primary"},
            "Deep Drama": {"emoji": "🎭", "color": "secondary"},
            "Funny / Comedy": {"emoji": "😂", "color": "warning"},
            "Action & Thrill": {"emoji": "💥", "color": "danger"},
            "Mind-Blowing": {"emoji": "🧠", "color": "info"},
            "Feel-Good": {"emoji": "🌿", "color": "success"},
        }

        mood_breakdown = []
        for mood_name, count in mood_counter.most_common(6):
            pct = round((count / total_mood_hits) * 100)
            meta = mood_meta.get(mood_name, {"emoji": "🎬", "color": "secondary"})
            mood_breakdown.append({
                "name": mood_name,
                "count": count,
                "percentage": pct,
                "emoji": meta["emoji"],
                "color": meta["color"]
            })

        profile["mood_breakdown"] = mood_breakdown

        # Determine user personality based on their top emotional category & ratings
        if profile["total_ratings"] == 0 and profile["total_favourites"] == 0 and profile["total_watchlist"] == 0:
            profile["personality"] = "New Explorer 🚀"
        elif mood_breakdown:
            top_mood = mood_breakdown[0]["name"]
            profile["top_mood"] = top_mood

            if top_mood == "Romantic":
                profile["personality"] = "Hopeless Romantic 💕"
            elif top_mood == "Sad / Emotional":
                profile["personality"] = "Soulful Drama Seeker 😢"
            elif top_mood == "Funny / Comedy":
                profile["personality"] = "Feel-Good Comedy Fan 😂"
            elif top_mood == "Action & Thrill":
                profile["personality"] = "Adrenaline Junkie 💥"
            elif top_mood == "Mind-Blowing":
                profile["personality"] = "Mind-Bender & Sci-Fi Thinker 🧠"
            elif top_mood == "Feel-Good":
                profile["personality"] = "Wholesome Heart Lover 🌿"
            else:
                profile["personality"] = "Passionate Cinephile 🎬"
        elif profile["average_rating"] >= 4:
            profile["personality"] = "Movie Enthusiast ⭐"
        elif profile["average_rating"] >= 3:
            profile["personality"] = "Balanced Viewer 🍿"
        else:
            profile["personality"] = "Selective Viewer 🎯"

        return profile
