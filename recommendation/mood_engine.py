import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class MoodRecommendationEngine:

    # Mood definitions and related keywords
    MOODS = {

        "romantic": {
            "name": "Romantic",
            "emoji": "💖",
            "description": "Love, romance & heartfelt feelings",
            "keywords": (
                "love romance relationships emotional connection "
                "couples friendship feelings heartbreak marriage "
                "dating lovers romantic passionate"
            ),
            "genres": ["Romance", "Drama"]
        },

        "sad": {
            "name": "Sad",
            "emoji": "😢",
            "description": "Heartbreak, tears & touching dramas",
            "keywords": (
                "sad emotional tears heartbreak tragedy grief "
                "drama loss death depression struggle pain "
                "sacrifice terminal mourning cry"
            ),
            "genres": ["Drama", "Romance"]
        },

        "action": {
            "name": "Action",
            "emoji": "💥",
            "description": "Thrilling battles, stunts & adrenaline",
            "keywords": (
                "action fighting battle revenge adventure "
                "superhero criminal danger powerful war "
                "explosion soldier chase mission martial arts"
            ),
            "genres": ["Action", "Adventure", "Thriller", "War"]
        },

        "funny": {
            "name": "Funny",
            "emoji": "😂",
            "description": "Comedy, laughs & feel-good humor",
            "keywords": (
                "funny comedy laughter jokes friends friendship "
                "humour hilarious crazy situations entertaining "
                "parody prank witty amusing"
            ),
            "genres": ["Comedy"]
        },

        "mind_blowing": {
            "name": "Mind-Blowing",
            "emoji": "🧠",
            "description": "Mysteries, sci-fi & plot twists",
            "keywords": (
                "dream reality mystery secrets psychological "
                "thriller science fiction space time travel "
                "unexpected twist illusion discovery matrix multiverse"
            ),
            "genres": ["Sci-Fi", "Thriller", "Mystery"]
        },

        "relaxing": {
            "name": "Relaxing",
            "emoji": "🌿",
            "description": "Peaceful, wholesome & comforting journeys",
            "keywords": (
                "peaceful journey friendship travel adventure "
                "life happiness beautiful experiences relaxing "
                "wholesome family feel good nature calm"
            ),
            "genres": ["Adventure", "Comedy", "Animation", "Family"]
        },

        "emotional": {
            "name": "Emotional",
            "emoji": "🎭",
            "description": "Deep, inspiring life journeys & sacrifices",
            "keywords": (
                "emotional family friendship struggle life "
                "inspiration humanity dreams sacrifice relationships "
                "drama tears deep inspiring"
            ),
            "genres": ["Drama"]
        }
    }

    # Mood aliases for user-friendly routing
    ALIASES = {
        "romantic": "romantic",
        "romance": "romantic",
        "sad": "sad",
        "emotional": "sad",
        "action": "action",
        "funny": "funny",
        "comedy": "funny",
        "mind_blowing": "mind_blowing",
        "mindblowing": "mind_blowing",
        "relaxing": "relaxing",
    }

    def __init__(self, data_path):

        # Load movie dataset
        self.movies = pd.read_csv(data_path)

        # Combine movie information into one text feature
        self.movies["combined_features"] = (
            self.movies["genre"]
            .fillna("")
            .str.replace("|", " ", regex=False)
            + " "
            + self.movies["director"].fillna("")
            + " "
            + self.movies["actors"]
            .fillna("")
            .str.replace("|", " ", regex=False)
            + " "
            + self.movies["description"].fillna("")
        )

        # Convert text into numerical features
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2)
        )

        self.feature_matrix = self.vectorizer.fit_transform(
            self.movies["combined_features"]
        )

    def get_mood_list(self):
        """Return distinct main mood keys for the UI navigation."""
        return ["romantic", "sad", "action", "funny", "mind_blowing", "relaxing"]

    def get_mood_info(self, mood):
        normalized = self.ALIASES.get(mood.lower().strip().replace(" ", "_"), mood)
        return self.MOODS.get(normalized, self.MOODS["romantic"])

    def recommend_by_mood(self, mood, limit=24):

        # Normalize mood input
        raw_key = mood.lower().strip().replace(" ", "_")
        canonical_key = self.ALIASES.get(raw_key, raw_key)

        # Validate mood
        if canonical_key not in self.MOODS:
            raise ValueError(
                f"Invalid mood: {mood}. "
                f"Available moods: {list(self.MOODS.keys())}"
            )

        mood_data = self.MOODS[canonical_key]
        display_name = mood_data["name"]
        emoji = mood_data["emoji"]

        # Convert mood keywords into numerical features
        mood_vector = self.vectorizer.transform(
            [mood_data["keywords"]]
        )

        # Calculate similarity between mood and movies
        similarity_scores = cosine_similarity(
            mood_vector,
            self.feature_matrix
        ).flatten()

        results = []

        for index, score in enumerate(similarity_scores):

            movie = self.movies.iloc[index]

            # Extract movie genres
            movie_genres = [
                genre.strip().lower()
                for genre in str(movie.get("genre", "")).split("|")
            ]

            # Extract preferred genres for selected mood
            preferred_genres = [
                genre.lower()
                for genre in mood_data["genres"]
            ]

            # Find matching genres
            matching_genres = [
                genre for genre in preferred_genres
                if genre in movie_genres
            ]

            # Primary genre match bonus
            genre_bonus = 0.25 * len(matching_genres)

            # Rating quality factor
            try:
                rating_val = float(movie.get("rating", 0.0))
                rating_bonus = (rating_val / 10.0) * 0.1
            except (ValueError, TypeError):
                rating_bonus = 0.0

            # Calculate raw recommendation score
            raw_score = float(score) + genre_bonus + rating_bonus

            # Must have at least some relevance or matching genre
            if raw_score <= 0 or (score < 0.02 and not matching_genres):
                continue

            # Build explanation
            reasons = []
            if matching_genres:
                reasons.append(f"Features {', '.join([g.title() for g in matching_genres])}")
            if score > 0.05:
                reasons.append("storyline strongly aligns with your mood")
            else:
                reasons.append("popular choice for this mood")

            # Clean poster URL safely
            raw_poster = movie.get("poster_url")
            poster_url = "" if pd.isna(raw_poster) or not str(raw_poster).strip() else str(raw_poster).strip()

            results.append({
                "movie_id": int(index),
                "title": str(movie.get("title", "Untitled")),
                "genre": str(movie.get("genre", "")),
                "language": str(movie.get("language", "English")),
                "rating": movie.get("rating", 0.0),
                "description": str(movie.get("description", "")),
                "poster_url": poster_url,
                "raw_score": raw_score,
                "reason": " • ".join(reasons).capitalize() + "."
            })

        # Sort recommendations by highest raw score descending
        results.sort(
            key=lambda item: item["raw_score"],
            reverse=True
        )

        top_results = results[:limit]

        # Calibrate match percentage into smooth descending rank: 99%, 98%, 97%, 96%...
        for rank, item in enumerate(top_results):
            # The top movie starts at 99%, stepping down cleanly: 99, 98, 97, 96...
            assigned_pct = max(60, 99 - rank)
            item["match_percentage"] = assigned_pct
            item["match_score"] = assigned_pct
            item["mood_label"] = f"{assigned_pct}% {display_name}"
            item["mood_name"] = display_name
            item["mood_emoji"] = emoji

        return top_results
