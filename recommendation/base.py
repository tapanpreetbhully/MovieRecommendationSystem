from abc import ABC, abstractmethod


class RecommendationEngine(ABC):

    @abstractmethod
    def recommend(self, movie_id=None, limit=10):
        pass