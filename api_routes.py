from flask import Blueprint, jsonify, request, session
from langdetect import detect
from models import db, Category, Response, Setting
from text_api import ask_question, model_intent, intent_embeddings, intent_tags  # ← ajout intelligent
from sentence_transformers import util

api_bp = Blueprint('api', __name__)

# 🔹 Route : Message d’accueil initial
@api_bp.route('/api/init')
def chatbot_init():
    lang = get_chatbot_language()
    messages = get_messages(lang)
    return jsonify({
        "message": messages["welcome_message"],
        "lang": lang,
        "clarification_required": False
    })

# 🔹 Fallback personnalisé
def guess_lang_fallback(text):
    text = text.lower()
    if any(w in text for w in ["bonjour", "salut", "merci", "svp", "aide"]):
        return "fr"
    elif any(w in text for w in ["hello", "please", "help", "thanks"]):
        return "en"
    elif any(c in text for c in ["أ", "إ", "ل", "ب", "ك", "ى", "ة", "؟"]):
        return "ar"
    return None

# 🔹 Route : Démarrage après message utilisateur
@api_bp.route('/api/start', methods=['POST'])
def chatbot_start():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    try:
        detected_lang = detect(user_message)
    except:
        detected_lang = None

    lang = detected_lang if detected_lang in ['fr', 'en', 'ar'] else guess_lang_fallback(user_message)
    if lang is None:
        lang = get_chatbot_language()

    has_started = session.get("chat_started", False)

    # ✅ Remplacement par détection d’intention intelligente
    if not has_started:
        from torch import no_grad
        with no_grad():
            q_embed = model_intent.encode(user_message, convert_to_tensor=True)
            scores = util.cos_sim(q_embed, intent_embeddings)[0]
            best_score = float(scores.max())
            best_idx = int(scores.argmax())
            best_tag = intent_tags[best_idx]

            if best_score > 0.6 and best_tag == "greeting":
                session["chat_started"] = True
                categories = Category.query.filter_by(parent_id=None, visible=True).all()
                cat_list = [
                    {
                        "id": cat.id,
                        "label": cat.get_translated_name(lang),
                        "has_children": len([c for c in cat.subcategories if c.visible]) > 0,
                        "response_count": len([r for r in cat.responses if r.visible])
                    }
                    for cat in categories
                ]
                return jsonify({
                    "message": get_messages(lang)["select_prompt"],
                    "lang": lang,
                    "categories": cat_list,
                    "navigation_options": get_navigation("categories"),
                    "clarification_required": False
                })

    # 🔁 Sinon : redirection vers la recherche textuelle
    return ask_question(user_message)

# 🔸 Messages multilingues
def get_messages(lang):
    messages = {
        'fr': {
            "welcome_message": "Bonjour, je suis là pour vous aider.",
            "select_prompt": "Veuillez choisir un élément dans la liste.",
            "no_responses": "Aucune réponse trouvée pour cette catégorie.",
            "loading": "Chargement..."
        },
        'en': {
            "welcome_message": "Hello, I'm here to help you.",
            "select_prompt": "Please choose from the list.",
            "no_responses": "No responses found for this category.",
            "loading": "Loading..."
        },
        'ar': {
            "welcome_message": "مرحبًا، أنا هنا لمساعدتك.",
            "select_prompt": "اختر من القائمة.",
            "no_responses": "لا توجد ردود على هذه الفئة.",
            "loading": "جارٍ التحميل..."
        }
    }
    return messages.get(lang, messages['fr'])

# 🔸 Navigation dynamique
def get_navigation(stage):
    if stage == "categories":
        return {
            "back_to_previous": False,
            "back_to_main": False,
            "restart": False
        }
    elif stage == "subcategories":
        return {
            "back_to_previous": True,
            "back_to_main": True,
            "restart": False
        }
    elif stage == "responses":
        return {
            "back_to_previous": True,
            "back_to_main": True,
            "restart": True
        }

# 🔹 Fallback langue globale du chatbot
def get_chatbot_language():
    return Setting.get_value("CHATBOT_LANGUAGE", "fr")

# 🔹 Route : Catégories principales
@api_bp.route('/api/categories')
def get_main_categories():
    lang = request.args.get("lang", get_chatbot_language())
    categories = Category.query.filter_by(parent_id=None, visible=True).all()
    cat_list = [
        {
            "id": cat.id,
            "label": cat.get_translated_name(lang),
            "has_children": len([c for c in cat.subcategories if c.visible]) > 0,
            "response_count": len(cat.responses)
        }
        for cat in categories
    ]
    return jsonify({
        "messages": get_messages(lang),
        "navigation_options": get_navigation("categories"),
        "categories": cat_list,
        "clarification_required": False
    })

# 🔹 Route : Sous-catégories
@api_bp.route('/api/categories/<int:category_id>/subcategories')
def get_subcategories(category_id):
    lang = request.args.get("lang", get_chatbot_language())
    subcats = Category.query.filter_by(parent_id=category_id, visible=True).all()
    sub_list = [
        {
            "id": sub.id,
            "label": sub.get_translated_name(lang),
            "has_children": len([c for c in sub.subcategories if c.visible]) > 0,
            "response_count": len(sub.responses)
        }
        for sub in subcats
    ]
    return jsonify({
        "messages": get_messages(lang),
        "navigation_options": get_navigation("subcategories"),
        "subcategories": sub_list,
        "clarification_required": False
    })

# 🔹 Route : Réponses
@api_bp.route('/api/categories/<int:category_id>/responses')
def get_responses(category_id):
    lang = request.args.get("lang", get_chatbot_language())
    category = Category.query.get_or_404(category_id)
    if not category.visible:
        return jsonify({
            "messages": get_messages(lang),
            "navigation_options": get_navigation("responses"),
            "responses": [],
            "clarification_required": False
        })

    responses = Response.query.filter_by(category_id=category_id).all()
    resp_list = [
        {
            "id": r.id,
            "type": r.type,
            "answer": getattr(r, f'answer_{lang}', r.answer_fr),
            "file_url": r.file_url
        }
        for r in responses
    ]
    return jsonify({
        "messages": get_messages(lang),
        "navigation_options": get_navigation("responses"),
        "responses": resp_list,
        "clarification_required": False
    })
