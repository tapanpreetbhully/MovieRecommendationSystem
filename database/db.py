import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "movie_recommendation"),
        cursorclass=pymysql.cursors.DictCursor
    )

    return connection