import os
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from recommendation.base import RecommendationEngine


class ContentBasedEngine(RecommendationEngine):

    def __init__(self, data_path):
        self.data_path = data_path
        self.movies = pd.read_csv(data_path)

        self.movies["combined_features"] = (
            self.movies["genre"].fillna("") + " " +
            self.movies["director"].fillna("") + " " +
            self.movies["actors"].fillna("") + " " +
            self.movies["description"].fillna("")
        )

        self.vectorizer = TfidfVectorizer(stop_words="english")

        self.feature_matrix = self.vectorizer.fit_transform(
            self.movies["combined_features"]
        )

        self.similarity_matrix = cosine_similarity(self.feature_matrix)

    def recommend(self, movie_id=None, limit=10):

        if movie_id is None:
            return self.movies.head(limit)

        if movie_id < 0 or movie_id >= len(self.movies):
            return pd.DataFrame()

        similarity_scores = list(
            enumerate(self.similarity_matrix[movie_id])
        )

        similarity_scores = sorted(
            similarity_scores,
            key=lambda x: x[1],
            reverse=True
        )

        similar_movies = similarity_scores[1:limit + 1]

        movie_indices = [index for index, score in similar_movies]

        return self.movies.iloc[movie_indices]