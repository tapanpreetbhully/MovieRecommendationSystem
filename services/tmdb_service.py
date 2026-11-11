import os
import requests
from dotenv import load_dotenv

# Ensure .env is always found regardless of working directory
_dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_dotenv_path)

# TMDb Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip() or "6645088515f762179d2d85bedd868a93"
BASE_URL = "https://api.tmdb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/original"

# Supported language mapping
LANGUAGE_MAP = {
    "hi": "Hindi (Bollywood)",
    "en": "English (Hollywood)",
    "ko": "Korean (K-Drama / Cinema)",
    "es": "Spanish",
    "ja": "Japanese (Anime / Cinema)",
    "fr": "French",
    "te": "Telugu (Tollywood)",
    "ta": "Tamil (Kollywood)",
    "ml": "Malayalam (Mollywood)",
    "kn": "Kannada (Sandalwood)",
    "de": "German",
    "it": "Italian",
    "zh": "Chinese",
    "pa": "Punjabi",
    "bn": "Bengali",
    "mr": "Marathi",
    "tr": "Turkish",
    "ru": "Russian",
    "pt": "Portuguese",
}

LANGUAGES = [
    {"code": code, "name": name} for code, name in LANGUAGE_MAP.items()
]

def get_language_name(code):
    """Convert language code to friendly name."""
    if not code:
        return "Unknown"
    return LANGUAGE_MAP.get(code.lower(), code.upper())

def detect_moods(genres, overview=""):
    """
    Detect emotional / mood categories (Romantic, Sad, Funny, Action, Mind-Blowing, Relaxing)
    based on genres and plot keywords.
    """
    moods = []
    text = (overview or "").lower()
    genre_set = {str(g).lower().strip() for g in genres}

    # 1. Romantic
    romantic_keywords = ["love", "romance", "romantic", "couple", "relationship", "crush", "dating", "passion", "lover", "wedding", "heart"]
    if "romance" in genre_set or any(kw in text for kw in romantic_keywords):
        moods.append({"name": "Romantic", "emoji": "💖", "color": "danger"})

    # 2. Sad / Emotional
    emotional_keywords = ["sad", "death", "die", "grief", "tragedy", "loss", "cancer", "terminal", "mourning", "sacrifice", "heartbreak", "struggle", "depress"]
    if "drama" in genre_set and any(kw in text for kw in emotional_keywords):
        moods.append({"name": "Sad / Emotional", "emoji": "😢", "color": "primary"})
    elif any(kw in text for kw in ["tragedy", "heartbreak", "grief"]):
        moods.append({"name": "Sad / Emotional", "emoji": "😢", "color": "primary"})

    # 3. Funny / Comedy
    comedy_keywords = ["funny", "comedy", "humor", "humour", "laugh", "hilarious", "parody", "satire", "crazy", "silly", "mischief"]
    if "comedy" in genre_set or any(kw in text for kw in comedy_keywords):
        moods.append({"name": "Funny / Comedy", "emoji": "😂", "color": "warning"})

    # 4. Action / Adrenaline
    action_keywords = ["action", "fight", "battle", "war", "explosion", "martial arts", "soldier", "gun", "heist", "chase", "superhero", "revenge"]
    if any(g in genre_set for g in ["action", "adventure", "war"]) or any(kw in text for kw in action_keywords):
        moods.append({"name": "Action & Thrill", "emoji": "💥", "color": "danger"})

    # 5. Mind-Blowing / Psychological
    mind_keywords = ["mystery", "twist", "psychological", "illusion", "dream", "time travel", "multiverse", "alien", "conspiracy", "secrets", "sci-fi"]
    if any(g in genre_set for g in ["science fiction", "mystery", "thriller"]) or any(kw in text for kw in mind_keywords):
        moods.append({"name": "Mind-Blowing", "emoji": "🧠", "color": "info"})

    # 6. Relaxing / Feel-Good
    relaxing_keywords = ["friendship", "journey", "road trip", "peaceful", "nature", "wholesome", "family", "hope", "inspire", "uplifting"]
    if any(g in genre_set for g in ["animation", "family", "music"]) or any(kw in text for kw in relaxing_keywords):
        moods.append({"name": "Feel-Good / Relaxing", "emoji": "🌿", "color": "success"})

    # Default fallback
    if not moods:
        if "drama" in genre_set:
            moods.append({"name": "Emotional Drama", "emoji": "🎭", "color": "secondary"})
        elif "horror" in genre_set:
            moods.append({"name": "Horror & Spooky", "emoji": "👻", "color": "dark"})
        else:
            moods.append({"name": "Engaging Story", "emoji": "🎬", "color": "secondary"})

    return moods

def _make_request(endpoint, params=None):
    """Internal helper to call TMDb API with automatic domain fallback."""
    if not TMDB_API_KEY:
        print("Warning: TMDB_API_KEY is not configured.")
        return None

    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    clean_endpoint = endpoint.lstrip('/')
    domains = ["https://api.tmdb.org/3", "https://api.themoviedb.org/3"]

    for base in domains:
        url = f"{base}/{clean_endpoint}"
        try:
            response = requests.get(url, params=params, headers=headers, timeout=6)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [401, 404]:
                return None
        except Exception:
            continue

    return None

def format_item(item, media_type="movie"):
    """Format movie or tv show dictionary for unified template rendering."""
    title = item.get("title") if media_type == "movie" else item.get("name")
    release_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
    year = release_date.split("-")[0] if release_date else "N/A"

    poster_path = item.get("poster_path")
    poster_url = f"{POSTER_BASE_URL}{poster_path}" if poster_path else "https://via.placeholder.com/500x750?text=No+Poster"

    backdrop_path = item.get("backdrop_path")
    backdrop_url = f"{BACKDROP_BASE_URL}{backdrop_path}" if backdrop_path else None

    # Genre names
    genre_names = []
    if "genres" in item:
        genre_names = [g["name"] for g in item.get("genres", [])]
    elif "genre_ids" in item:
        # Genre IDs mapping can be added if needed
        genre_names = []

    overview = item.get("overview", "No synopsis available.")
    lang_code = item.get("original_language", "")
    lang_name = get_language_name(lang_code)

    moods = detect_moods(genre_names, overview)

    return {
        "id": item.get("id"),
        "title": title or "Untitled",
        "overview": overview,
        "release_year": year,
        "release_date": release_date or "N/A",
        "rating": round(float(item.get("vote_average", 0.0)), 1),
        "vote_count": item.get("vote_count", 0),
        "language_code": lang_code.upper(),
        "language": lang_name,
        "genres": genre_names,
        "moods": moods,
        "poster_url": poster_url,
        "backdrop_url": backdrop_url,
        "media_type": media_type
    }

def get_movies(language=None, page=1):
    """Fetch popular/trending movies, optionally filtered by language."""
    params = {
        "sort_by": "popularity.desc",
        "page": page,
        "include_adult": "false"
    }
    if language:
        params["with_original_language"] = language

    data = _make_request("discover/movie", params)
    if not data or "results" not in data:
        return []
    return [format_item(m, media_type="movie") for m in data["results"]]

def get_tv_shows(language=None, page=1):
    """Fetch TV series, optionally filtered by language."""
    params = {
        "sort_by": "popularity.desc",
        "page": page,
        "include_adult": "false"
    }
    if language:
        params["with_original_language"] = language

    data = _make_request("discover/tv", params)
    if not data or "results" not in data:
        return []
    return [format_item(tv, media_type="tv") for tv in data["results"]]

def get_trailer_key(media_id, media_type="movie"):
    """Fetch YouTube trailer video key for a movie or TV show."""
    endpoint = f"{media_type}/{media_id}/videos"
    data = _make_request(endpoint)
    if not data or "results" not in data:
        return None

    # Priority 1: Official Trailer on YouTube
    for video in data["results"]:
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            return video.get("key")

    # Priority 2: Teaser or any YouTube video
    for video in data["results"]:
        if video.get("site") == "YouTube":
            return video.get("key")

    return None

def get_media_details(media_id, media_type="movie"):
    """Fetch full details (cast, director, runtime, genres, moods, trailer) for a movie or TV series."""
    endpoint = f"{media_type}/{media_id}"
    params = {"append_to_response": "credits,videos"}
    data = _make_request(endpoint, params=params)
    if not data:
        return None

    formatted = format_item(data, media_type=media_type)

    # Runtime formatted
    runtime_mins = data.get("runtime") or (data.get("episode_run_time", [0])[0] if data.get("episode_run_time") else 0)
    if runtime_mins:
        hours = runtime_mins // 60
        mins = runtime_mins % 60
        formatted["runtime"] = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    else:
        formatted["runtime"] = "N/A"

    # Director and Cast from credits
    credits = data.get("credits", {})
    crew = credits.get("crew", [])
    directors = [c["name"] for c in crew if c.get("job") == "Director"]
    formatted["director"] = ", ".join(directors) if directors else "N/A"

    cast = credits.get("cast", [])
    actors = [c["name"] for c in cast[:6]]
    formatted["actors"] = ", ".join(actors) if actors else "N/A"

    # Tagline & Status
    formatted["tagline"] = data.get("tagline", "")
    formatted["status"] = data.get("status", "Released")

    # Trailer key
    videos = data.get("videos", {}).get("results", [])
    trailer_key = None
    for video in videos:
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            trailer_key = video.get("key")
            break
    if not trailer_key:
        for video in videos:
            if video.get("site") == "YouTube":
                trailer_key = video.get("key")
                break
    formatted["trailer_key"] = trailer_key

    # TV specific details
    if media_type == "tv":
        formatted["seasons_count"] = data.get("number_of_seasons", 1)
        formatted["episodes_count"] = data.get("number_of_episodes", 0)

    # Re-detect moods with full genre objects
    genres = [g["name"] for g in data.get("genres", [])]
    formatted["genres"] = genres
    formatted["moods"] = detect_moods(genres, formatted["overview"])

    return formatted

def search_tmdb(query, media_type="movie", page=1):
    """Search movies or TV shows by title."""
    endpoint = f"search/{media_type}"
    params = {"query": query, "page": page, "include_adult": "false"}
    data = _make_request(endpoint, params)
    if not data or "results" not in data:
        return []
    return [format_item(item, media_type=media_type) for item in data["results"]]

def get_search_suggestions(query, limit=7):
    """
    Fast autocomplete suggestions for live search as user types.
    Returns title, year, media_type, rating, and poster thumbnail.
    """
    if not query or len(query.strip()) < 2:
        return []

    params = {
        "query": query.strip(),
        "include_adult": "false",
        "page": 1
    }
    data = _make_request("search/multi", params)
    if not data or "results" not in data:
        return []

    suggestions = []
    for item in data.get("results", []):
        media_type = item.get("media_type")
        if media_type not in ["movie", "tv"]:
            continue

        title = item.get("title") if media_type == "movie" else item.get("name")
        if not title:
            continue

        release_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
        year = release_date.split("-")[0] if release_date else ""

        poster_path = item.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w92{poster_path}" if poster_path else "https://via.placeholder.com/92x138?text=No+Poster"

        suggestions.append({
            "id": item.get("id"),
            "title": title,
            "year": year,
            "media_type": "Movie" if media_type == "movie" else "TV Series",
            "type_key": media_type,
            "rating": round(float(item.get("vote_average", 0.0)), 1),
            "poster_url": poster_url,
            "url": f"/tmdb/{media_type}/{item.get('id')}"
        })

        if len(suggestions) >= limit:
            break

    return suggestions
