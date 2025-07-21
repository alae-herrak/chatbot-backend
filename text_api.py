from flask import Blueprint, request, jsonify
from langdetect import detect
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import nltk
import unicodedata
from pathlib import Path
import json
import random
from models import db, Category, Response
from sentence_transformers import SentenceTransformer, util
from sqlalchemy.orm import joinedload

# === Chargement du modèle SentenceTransformer ===
model_intent = SentenceTransformer("models/all-MiniLM-L12-v2")

# === Chargement du fichier intents.json ===
intent_data = {}
intent_file_path = Path("intents.json")
if intent_file_path.exists():
    with open(intent_file_path, "r", encoding="utf-8") as f:
        intent_data = json.load(f)

intent_phrases, intent_tags, intent_langs, intent_responses = [], [], [], {}
for intent in intent_data.get("intents", []):
    tag = intent["tag"]
    intent_responses[tag] = intent.get("responses", {})
    for pattern in intent.get("patterns", []):
        if pattern.strip():
            try:
                intent_phrases.append(pattern)
                intent_tags.append(tag)
                intent_langs.append(detect(pattern))
            except:
                intent_phrases.append(pattern)
                intent_tags.append(tag)
                intent_langs.append('fr')

intent_embeddings = model_intent.encode(intent_phrases, convert_to_tensor=True)

text_api_bp = Blueprint('text_api_bp', __name__)

from nltk.corpus import stopwords

cache = {
    "text_responses": {},
    "tfidf_matrix": {},
    "vectorizer": {},
    "texts_clean": {},
    "categories": {},
    "cat_matrix": {},
    "cat_vectorizer": {},
    "cat_names_clean": {}
}

def normalize_common(text):
    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_fr(text):
    return re.sub(r'\b(les|des|aux|du|de|la|le|un|une|et|ou|pour|avec|sur|dans|parmi|au|en|vers)\b', '', normalize_common(text))

def clean_en(text):
    return re.sub(r'\b(the|a|an|in|on|at|of|and|or|to|with|for|by|from|about|as)\b', '', normalize_common(text))

def clean_ar(text):
    text = normalize_common(text)
    text = re.sub(r'[\u064B-\u0652]', '', text)
    text = text.replace('ى', 'ي').replace('ة', 'ه').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    return re.sub(r'\b(من|عن|إلى|في|على|مع|ال|و|او|ما|هو|هي|هذا|هذه|ذلك|تلك)\b', '', text)

def clean_text(text, lang='fr'):
    if not text:
        return ""
    if lang == 'ar':
        return clean_ar(text)
    elif lang == 'en':
        return clean_en(text)
    return clean_fr(text)

def get_stopwords_for_lang(lang_code):
    lang_map = {'fr': 'french', 'en': 'english', 'ar': 'arabic'}
    try:
        return stopwords.words(lang_map.get(lang_code, 'english'))
    except:
        return []

def get_answer_field(lang_code):
    return {'fr': 'answer_fr', 'en': 'answer_en', 'ar': 'answer_ar'}.get(lang_code, 'answer_en')

def preload_language_data(lang):
    answer_field = get_answer_field(lang)
    stop_words = get_stopwords_for_lang(lang)

    responses = Response.query.options(joinedload(Response.category)).join(Response.category).filter(Category.visible == True, Response.type == 'text').all()
    texts_clean = [clean_text(getattr(r, answer_field) or "", lang) for r in responses]

    if texts_clean:
        vectorizer = TfidfVectorizer(stop_words=stop_words)
        tfidf_matrix = vectorizer.fit_transform(texts_clean)
        cache["text_responses"][lang] = responses
        cache["tfidf_matrix"][lang] = tfidf_matrix
        cache["vectorizer"][lang] = vectorizer
        cache["texts_clean"][lang] = texts_clean

    categories = Category.query.filter_by(visible=True).all()
    cat_names_clean = [clean_text(c.get_translated_name(lang) or "", lang) for c in categories]

    if cat_names_clean:
        cat_vectorizer = TfidfVectorizer(stop_words=stop_words)
        cat_matrix = cat_vectorizer.fit_transform(cat_names_clean)
        cache["categories"][lang] = categories
        cache["cat_matrix"][lang] = cat_matrix
        cache["cat_vectorizer"][lang] = cat_vectorizer
        cache["cat_names_clean"][lang] = cat_names_clean

@text_api_bp.route("/api/ask", methods=["POST"])
def ask_question_route():
    data = request.get_json()
    return ask_question(data.get("question", "").strip())

def ask_question(question_text):
    question = question_text.strip()
    if not question:
        return jsonify({"error": "Aucune question fournie"}), 400

    try:
        lang = detect(question)
    except:
        lang = 'en'

    answer_field = get_answer_field(lang)
    stop_words = get_stopwords_for_lang(lang)
    question_clean = clean_text(question, lang)

    from torch import no_grad
    with no_grad():
        q_embed = model_intent.encode(question, convert_to_tensor=True)
        scores = util.cos_sim(q_embed, intent_embeddings)[0]
        best_score = float(scores.max())
        best_idx = int(scores.argmax())

        if best_score > 0.6:
            tag = intent_tags[best_idx]
            lang_responses = intent_responses.get(tag, {})
            if lang in lang_responses and lang_responses[lang]:
                selected_response = random.choice(lang_responses[lang])
            elif "fr" in lang_responses and lang_responses["fr"]:
                selected_response = random.choice(lang_responses["fr"])
            else:
                all_responses = sum(lang_responses.values(), [])
                selected_response = random.choice(all_responses) if all_responses else "..."
            return jsonify({
                "response": selected_response,
                "type": "intent",
                "category": None,
                "response_id": None,
                "file_url": None
            })

    if lang not in cache["tfidf_matrix"]:
        preload_language_data(lang)

    responses = cache["text_responses"].get(lang, [])
    if responses:
        vectorizer = cache["vectorizer"][lang]
        tfidf_matrix = cache["tfidf_matrix"][lang]
        q_vector = vectorizer.transform([question_clean])
        similarities = cosine_similarity(q_vector, tfidf_matrix).flatten()
        best_index = similarities.argmax()
        best_score = similarities[best_index]

        close_indices = [i for i, score in enumerate(similarities) if score >= 0.3 and abs(score - best_score) <= 0.05]
        if len(close_indices) >= 2:
            options = [{
                "response_id": responses[i].id,
                "category": responses[i].category.get_translated_name(lang),
                "preview": getattr(responses[i], answer_field)[:120] + "..."
            } for i in close_indices]
            return jsonify({
                "clarification_required": True,
                "clarification_options": options
            })

        if best_score >= 0.3:
            r = responses[best_index]
            return jsonify({
                "response": getattr(r, answer_field),
                "type": r.type,
                "category": r.category.get_translated_name(lang),
                "response_id": r.id,
                "file_url": r.file_url
            })

    categories = cache["categories"].get(lang, [])
    if categories:
        cat_vectorizer = cache["cat_vectorizer"][lang]
        cat_matrix = cache["cat_matrix"][lang]
        q_vector = cat_vectorizer.transform([question_clean])
        similarities = cosine_similarity(q_vector, cat_matrix).flatten()
        best_index = similarities.argmax()
        best_score = similarities[best_index]

        if best_score >= 0.3:
            best_cat = categories[best_index]
            fallback_responses = Response.query.options(joinedload(Response.category)).filter(
                Response.category_id == best_cat.id,
                Response.type != 'text'
            ).all()
            if fallback_responses:
                r = fallback_responses[0]
                return jsonify({
                    "response": getattr(r, answer_field) or "",
                    "type": r.type,
                    "category": best_cat.get_translated_name(lang),
                    "response_id": r.id,
                    "file_url": r.file_url
                })

    default_message = {
        "fr": "Désolé, je n’ai pas trouvé de réponse à votre question.",
        "en": "Sorry, I couldn't find an answer to your question.",
        "ar": "عذرًا، لم أتمكن من العثور على إجابة لسؤالك."
    }.get(lang, "Sorry, I couldn't find an answer.")

    return jsonify({
        "response": default_message,
        "type": "none",
        "category": None,
        "response_id": None,
        "file_url": None
    })
