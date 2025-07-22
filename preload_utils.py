from models import db, Response, Category
from text_api import preload_language_data, cache

def preload_all_languages():
    if "text_embeddings" not in cache:
        cache["text_embeddings"] = {}

    for lang in ['fr', 'en', 'ar']:
        if lang not in cache["text_embeddings"]:
            preload_language_data(lang)
