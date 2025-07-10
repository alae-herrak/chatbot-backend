# intent_detector.py
from sentence_transformers import SentenceTransformer, util
from langdetect import detect
import json
import os
import random

# === Chargement du modèle léger ===
model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")

# === Chargement du fichier JSON des intentions ===
with open("intents.json", "r", encoding="utf-8") as f:
    intent_data = json.load(f)

# === Préparer les embeddings pour les patterns ===
templates = []
intents = []
responses = {}

for intent in intent_data["intents"]:
    tag = intent["tag"]
    patterns = intent["patterns"]
    responses[tag] = intent["responses"]
    templates.extend(patterns)
    intents.extend([tag] * len(patterns))

# === Embedding de tous les patterns
intent_embeddings = model.encode(templates, convert_to_tensor=True)

def detect_intent(user_input):
    try:
        # Détection automatique de la langue de l'utilisateur
        lang = detect(user_input)
    except:
        lang = "fr"  # Par défaut si erreur

    query_embedding = model.encode(user_input, convert_to_tensor=True)
    cosine_scores = util.cos_sim(query_embedding, intent_embeddings)[0]
    best_score = float(cosine_scores.max())
    best_idx = int(cosine_scores.argmax())

    if best_score > 0.6:
        intent_name = intents[best_idx]
        response_list = responses[intent_name]

        # Choisir la bonne langue si elle existe, sinon fallback "fr", puis n’importe quoi
        if lang in response_list:
            response = random.choice(response_list[lang])
        elif "fr" in response_list:
            response = random.choice(response_list["fr"])
        else:
            # prendre n’importe quelle langue dispo
            all_responses = sum(response_list.values(), [])
            response = random.choice(all_responses)

        return {
            "intent": intent_name,
            "confidence": best_score,
            "response": response
        }
    else:
        return None
