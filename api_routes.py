from flask import Blueprint, jsonify
from models import db, Category, Response, Setting

api_bp = Blueprint('api', __name__)

# 🔸 Messages multilingues
def get_messages(lang):
    messages = {
        'fr': {
            "welcome_message": "Bonjour, je suis là pour vous assister.",
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

# 🔹 Langue globale du chatbot (stockée en base)
def get_chatbot_language():
    return Setting.get_value("CHATBOT_LANGUAGE", "fr")

# 🔹 Route : Catégories principales
@api_bp.route('/api/categories')
def get_main_categories():
    lang = get_chatbot_language()
    categories = Category.query.filter_by(parent_id=None, visible=True).all()

    cat_list = [
        {
            "id": cat.id,
            "label": cat.get_translated_name(lang),
            "has_children": len(cat.subcategories) > 0,
            "response_count": len(cat.responses)
        }
        for cat in categories
    ]

    return jsonify({
        "messages": get_messages(lang),
        "navigation_options": get_navigation("categories"),
        "categories": cat_list
    })

# 🔹 Route : Sous-catégories
@api_bp.route('/api/categories/<int:category_id>/subcategories')
def get_subcategories(category_id):
    lang = get_chatbot_language()
    subcats = Category.query.filter_by(parent_id=category_id, visible=True).all()

    sub_list = [
        {
            "id": sub.id,
            "label": sub.get_translated_name(lang),
            "has_children": len(sub.subcategories) > 0,
            "response_count": len(sub.responses)
        }
        for sub in subcats
    ]

    return jsonify({
        "messages": get_messages(lang),
        "navigation_options": get_navigation("subcategories"),
        "subcategories": sub_list
    })

# 🔹 Route : Réponses
@api_bp.route('/api/categories/<int:category_id>/responses')
def get_responses(category_id):
    lang = get_chatbot_language()

    category = Category.query.get_or_404(category_id)
    if not category.visible:
        return jsonify({
            "messages": get_messages(lang),
            "navigation_options": get_navigation("responses"),
            "responses": []
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
        "responses": resp_list
    })
