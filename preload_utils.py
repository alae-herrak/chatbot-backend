from models import db, Response, Category
from text_api import preload_language_data, cache

def preload_all_languages():
    for lang in ['fr', 'en', 'ar']:
        if lang not in cache["tfidf_matrix"]:
            preload_language_data(lang)
