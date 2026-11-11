
class PersonalizedInsightsEngine:

    def __init__(self):
        self.genre_exploration = {
            "Action": ["Thriller", "Adventure", "Crime"],
            "Sci-Fi": ["Mystery", "Thriller", "Fantasy"],
            "Comedy": ["Romance", "Adventure", "Family"],
            "Drama": ["Mystery", "Romance", "Biography"],
            "Romance": ["Comedy", "Drama", "Musical"],
            "Thriller": ["Mystery", "Crime", "Psychological Thriller"],
            "Adventure": ["Fantasy", "Action", "Sci-Fi"],
            "Crime": ["Thriller", "Mystery", "Drama"],
            "Horror": ["Thriller", "Mystery", "Supernatural"],
            "Sports": ["Drama", "Biography", "Action"]
        }

    def get_names(self, items):
        """Extract names from Taste DNA data."""
        if not items:
            return []

        return [
            str(item[0] if isinstance(item, (tuple, list)) else item)
            for item in items
        ]

    def generate_insights(self, profile):

        genres = self.get_names(profile.get("top_genres", []))
        languages = self.get_names(profile.get("top_languages", []))
        directors = self.get_names(profile.get("top_directors", []))
        actors = self.get_names(profile.get("top_actors", []))

        total_ratings = profile.get("total_ratings", 0)
        total_favourites = profile.get("total_favourites", 0)
        average_rating = profile.get("average_rating", 0)
        personality = profile.get("personality", "New Explorer")

        insights = []

        # 1. Movie taste analysis
        if genres:
            insights.append({
                "title": "Your Movie Taste",
                "icon": "🎭",
                "description": (
                    f"Your activity shows a strong interest in "
                    f"{', '.join(genres[:3])} movies. "
                    f"These genres appear frequently in your movie preferences."
                )
            })
        else:
            insights.append({
                "title": "Your Movie Taste",
                "icon": "🎭",
                "description": (
                    "You are just starting your movie journey. "
                    "Rate and favourite movies to help us understand your taste."
                )
            })

        # 2. Rating behaviour
        if total_ratings > 0:
            if average_rating >= 4:
                rating_message = (
                    "You generally give positive ratings to movies. "
                    "You seem to enjoy the movies you select."
                )
            elif average_rating >= 3:
                rating_message = (
                    "Your ratings are balanced. You appear to be "
                    "selective about which movies impress you."
                )
            else:
                rating_message = (
                    "Your ratings suggest that you have selective movie preferences."
                )
        else:
            rating_message = (
                "You haven't rated movies yet. Start rating movies "
                "to unlock deeper insights."
            )

        insights.append({
            "title": "Your Rating Behaviour",
            "icon": "⭐",
            "description": rating_message
        })

        # 3. Favourite creators
        if directors or actors:
            creator_parts = []

            if directors:
                creator_parts.append(
                    f"directors such as {', '.join(directors[:2])}"
                )

            if actors:
                creator_parts.append(
                    f"actors such as {', '.join(actors[:3])}"
                )

            creator_message = (
                "Your preferences include " +
                " and ".join(creator_parts) +
                ". Explore more of their work to discover similar movies."
            )
        else:
            creator_message = (
                "Rate or favourite more movies to discover "
                "your preferred directors and actors."
            )

        insights.append({
            "title": "Your Favourite Creators",
            "icon": "🎬",
            "description": creator_message
        })

        # 4. Language preferences
        if languages:
            language_message = (
                f"You explore movies in {', '.join(languages[:3])}. "
                "Try discovering highly rated movies in other languages too."
            )
        else:
            language_message = "Your language preferences are not available yet."

        insights.append({
            "title": "Your Language Preferences",
            "icon": "🌍",
            "description": language_message
        })

        # 5. Next genre exploration
        suggested_genres = []

        for genre in genres:
            for suggestion in self.genre_exploration.get(genre, []):
                if suggestion not in genres and suggestion not in suggested_genres:
                    suggested_genres.append(suggestion)

        if suggested_genres:
            exploration_message = (
                "Based on your favourite genres, you may enjoy exploring "
                + ", ".join(suggested_genres[:4]) + " movies."
            )
        else:
            exploration_message = (
                "Explore different movie genres and rate them "
                "to receive more personalized discovery suggestions."
            )

        insights.append({
            "title": "What You Should Explore Next",
            "icon": "🔍",
            "description": exploration_message,
            "suggested_genres": suggested_genres[:4]
        })

        # 6. Overall movie personality
        insights.append({
            "title": "Your Movie Personality",
            "icon": "🧬",
            "description": (
                f"Your current movie personality is {personality}. "
                f"You have rated {total_ratings} movies and added "
                f"{total_favourites} movies to your favourites."
            )
        })

        return {
            "user_id": profile.get("user_id"),
            "personality": personality,
            "insights": insights
        }
