import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Category, Response
import requests
import os
from werkzeug.utils import secure_filename
from translate_utils import translate_with_gemma as translate_text
from langdetect import detect
from flask import send_from_directory
import json
from flask import jsonify
from datetime import datetime
from models import db, Log

from flask_cors import CORS
from models import Setting

from werkzeug.middleware.dispatcher import DispatcherMiddleware

class PrefixMiddleware:
    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'].startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
        return self.not_found(environ, start_response)

    def not_found(self, environ, start_response):
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'This URL does not belong to the app.']



app = Flask(__name__)

app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/chatbot')

CORS(app)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 🌍 Langue et chargement de traduction depuis fichier JSON
def load_translations(lang):
    try:
        with open(f'translations/{lang}.json', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

@app.before_request
def set_default_language():
    if 'lang' not in session:
        session['lang'] = 'fr'
    g.translations = load_translations(session['lang'])

@app.context_processor
def inject_translation_function():
    def t(key):
        return g.translations.get(key, key)
    return dict(t=t, get_locale=lambda: session.get('lang', 'fr'))

@app.route('/set_language/<lang_code>')
def set_language(lang_code):
    session['lang'] = lang_code
    return redirect(request.referrer or url_for('dashboard'))

# -------------------- Base de données --------------------
db.init_app(app)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='admin')

SUPER_ADMIN = {
    'username': 'admin',
    'password_hash': 'scrypt:32768:8:1$r5AYriongkSZfODw$81121a2f07f207e7852af238d6498bcf57cb7e9fea242e885ae35204a81bf57c83c0456af5c456524b14384e0dbe0ac196eece0c244b14fcabffa59a76fa74c4'
}

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == SUPER_ADMIN['username'] and check_password_hash(SUPER_ADMIN['password_hash'], password):
            session['username'] = username
            session['role'] = 'superadmin'
            session['admin_id'] = 0  # ✅ Superadmin a un id fictif
            return redirect(url_for('dashboard'))

        user = Admin.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = user.username
            session['role'] = user.role
            session['admin_id'] = user.id  # ✅ Cette ligne manquait
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="invalid_credentials")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    role = session['role']

    # Message selon l'heure
    hour = datetime.now().hour
    if hour < 12:
        greeting_key = "good_morning"
    elif hour < 18:
        greeting_key = "good_afternoon"
    else:
        greeting_key = "good_evening"

    # Statistiques globales
    total_categories = Category.query.count()
    total_responses = Response.query.count()

    type_counts = {
        'text': Response.query.filter_by(type='text').count(),
        'file': Response.query.filter_by(type='file').count(),
        'link': Response.query.filter_by(type='link').count(),
        'contact': Response.query.filter_by(type='contact').count(),
    }

    lang_counts = {
        'fr': Response.query.filter_by(source_lang='fr').count(),
        'en': Response.query.filter_by(source_lang='en').count(),
        'ar': Response.query.filter_by(source_lang='ar').count(),
    }

    logs = []
    if role == 'superadmin':
        logs = Log.query.order_by(Log.timestamp.desc()).limit(5).all()
    current_lang = Setting.get_value('CHATBOT_LANGUAGE', 'fr')

    return render_template(
        'dashboard.html',
        username=username,
        role=role,
        greeting_key=greeting_key,
        total_categories=total_categories,
        total_responses=total_responses,
        type_counts=type_counts,
        lang_counts=lang_counts,
        logs=logs,
        current_lang=current_lang
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/manage_admins')
def manage_admins():
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    admins = Admin.query.all()
    role = session.get('role')

    return render_template('manage_admins.html', admins=admins, username=session['username'] , role=role )

@app.route('/add_admin', methods=['GET', 'POST'])
def add_admin():
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("passwords_dont_match", "danger")
            return redirect(url_for('add_admin'))

        if Admin.query.filter_by(username=username).first():
            flash("username_already_exists", "danger")
            return redirect(url_for('add_admin'))

        new_admin = Admin(
            username=username,
            password_hash=generate_password_hash(password),
            role='admin'  # 🔒 Rôle fixé à 'admin'
        )
        db.session.add(new_admin)
        db.session.commit()
        flash("admin_added_success", "success")
        return redirect(url_for('manage_admins'))

    return render_template('add_admin.html', role=session.get('role'))


@app.route('/edit_admin/<int:id>', methods=['GET', 'POST'])
def edit_admin(id):
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    admin = Admin.query.get_or_404(id)

    if admin.username == 'admin':
        flash("cannot_modify_initial_superadmin", "danger")
        return redirect(url_for('manage_admins'))

    if request.method == 'POST':
        admin.username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password:
            if password != confirm:
                flash("passwords_dont_match", "danger")
                return redirect(url_for('edit_admin', id=id))
            admin.password_hash = generate_password_hash(password)

        # 🔒 Rôle figé en 'admin'
        admin.role = 'admin'

        db.session.commit()
        flash("admin_updated_success", "success")
        return redirect(url_for('manage_admins'))

    return render_template('edit_admin.html', admin=admin, role=session.get('role'))


@app.route('/delete_admin/<int:id>', methods=['POST'])
def delete_admin(id):
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    admin = Admin.query.get_or_404(id)

    if admin.username == 'admin':
        flash("cannot_delete_initial_superadmin", "danger")
        return redirect(url_for('manage_admins'))

    db.session.delete(admin)
    db.session.commit()
    flash("admin_deleted_success", "success")
    return redirect(url_for('manage_admins'))

# -------------------- À partir d'ici tu peux continuer --------------------

# -------------------- Catégories --------------------
def build_category_tree(categories, parent_id=None, level=0):
    lang = session.get('lang', 'fr')
    tree = []

    for cat in categories:
        if cat.parent_id == parent_id:
            name = cat.name_fr
            if lang == 'en':
                name = cat.name_en or cat.name_fr
            elif lang == 'ar':
                name = cat.name_ar or cat.name_fr

            children = build_category_tree(categories, cat.id, level + 1)

            tree.append({
                'id': cat.id,
                'parent_id': cat.parent_id,
                'translated_name': name,
                'level': level,
                'response_count': len(cat.responses),
                'has_children': len(children) > 0,
                'visible': cat.visible,  # ✅ la clé manquante !
                'children': children
            })

    return tree

def flatten_tree(tree):
    result = []

    def _flatten(nodes):
        for node in nodes:
            children = node.pop('children', [])
            result.append(node)
            _flatten(children)

    _flatten(tree)
    return result


@app.route('/manage_categories')
def manage_categories():
    if 'username' not in session:
        return redirect(url_for('login'))
    role = session.get('role')

    categories = Category.query.all()
    category_tree = build_category_tree(categories)
    flat_tree = flatten_tree(category_tree)
    return render_template('manage_categories.html', flat_tree=flat_tree , role=role)

@app.route('/toggle_category_visibility/<int:id>', methods=['POST'])
def toggle_category_visibility(id):
    if 'username' not in session:
        return jsonify({"success": False, "error": "unauthorized"}), 401

    category = Category.query.get_or_404(id)

    # ✅ Lire la valeur envoyée par le formulaire
    visible_value = request.form.get('visible')
    if visible_value is None:
        return jsonify({"success": False, "error": "missing visible"}), 400

    category.visible = visible_value == 'true'
    db.session.commit()

    return jsonify({"success": True, "visible": category.visible})

@app.route('/edit_category/<int:id>', methods=['GET', 'POST'])
def edit_category(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    category = Category.query.get_or_404(id)

    # ⚠️ Correction : on s'assure que source_lang est bien fr/en/ar
    if category.source_lang not in ['fr', 'en', 'ar']:
        category.source_lang = 'fr'
        db.session.commit()
    source_lang = category.source_lang
    source_field = f'name_{source_lang}'
    source_value = getattr(category, source_field, '')

    if request.method == 'POST':
        name_source = request.form.get(source_field, '').strip()
        name_en_manual = request.form.get('name_en', '').strip()
        name_fr_manual = request.form.get('name_fr', '').strip()
        name_ar_manual = request.form.get('name_ar', '').strip()

        old_source_value = getattr(category, source_field, '').strip()

        if name_source != old_source_value:
            setattr(category, source_field, name_source)
            category.source_lang = source_lang  # on garde la même langue
            if source_lang != 'fr':
                category.name_fr = translate_text(name_source, source_lang, 'fr')
            if source_lang != 'en':
                category.name_en = translate_text(name_source, source_lang, 'en')
            if source_lang != 'ar':
                category.name_ar = translate_text(name_source, source_lang, 'ar')
        else:
            category.name_fr = name_fr_manual if source_lang != 'fr' else category.name_fr
            category.name_en = name_en_manual if source_lang != 'en' else category.name_en
            category.name_ar = name_ar_manual if source_lang != 'ar' else category.name_ar

        parent_id = request.form.get('parent_id') or None
        category.parent_id = int(parent_id) if parent_id else None

        # ✅ Met à jour le champ `visible` selon la case cochée
        category.visible = request.form.get('visible') == 'on'

        db.session.commit()
        log_action("log_edit_category", "category", category.id)
        flash("category_updated_success", "success")
        return redirect(url_for('manage_categories'))

    all_categories = Category.query.all()
    tree = build_category_tree([cat for cat in all_categories if cat.id != id])
    label_key = f"category_name_{category.source_lang}"

    return render_template('edit_category.html',
                           category=category,
                           tree=tree,
                           source_field=source_field,
                           source_value=source_value,
                           label_key=label_key,
                           role=session.get('role'))

@app.route('/delete_category/<int:id>', methods=['POST'])
def delete_category(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    category = Category.query.get_or_404(id)

    # 🔒 Vérifie s'il y a des sous-catégories
    if category.subcategories:
        flash("cannot_delete_category_with_children", "danger")
        return redirect(url_for('manage_categories'))

    # 🔒 Vérifie s'il y a des réponses associées
    if hasattr(category, 'responses') and category.responses:
        flash("cannot_delete_category_with_responses", "danger")
        return redirect(url_for('manage_categories'))

    db.session.delete(category)
    db.session.commit()

    # ✅ ENREGISTREMENT DU LOG
    log_action("log_delete_category", "category", category.id)

    flash("category_deleted_success", "success")
    return redirect(url_for('manage_categories'))

@app.route('/add_category', methods=['GET', 'POST'])
def add_category():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        source_name = request.form['name'].strip()

        try:
            detected_lang = detect(source_name)
        except:
            detected_lang = "fr"

        # Initialisation des noms
        name_fr = name_en = name_ar = ""

        if detected_lang == "fr":
            name_fr = source_name
            name_en = translate_text(name_fr, source_lang='fr', target_lang='en')
            name_ar = translate_text(name_fr, source_lang='fr', target_lang='ar')
        elif detected_lang == "en":
            name_en = source_name
            name_fr = translate_text(name_en, source_lang='en', target_lang='fr')
            name_ar = translate_text(name_fr, source_lang='fr', target_lang='ar')
        elif detected_lang == "ar":
            name_ar = source_name
            name_fr = translate_text(name_ar, source_lang='ar', target_lang='fr')
            name_en = translate_text(name_fr, source_lang='fr', target_lang='en')
        else:
            name_fr = source_name
            name_en = translate_text(name_fr, source_lang='fr', target_lang='en')
            name_ar = translate_text(name_fr, source_lang='fr', target_lang='ar')

        parent_id = request.form.get('parent_id') or None
        if parent_id == '':
            parent_id = None

        # ✅ Nouveau champ : afficher/masquer
        visible = request.form.get('visible') == 'on'

        new_cat = Category(
            name_fr=name_fr,
            name_en=name_en,
            name_ar=name_ar,
            parent_id=parent_id,
            source_lang=detected_lang,
            visible=visible
        )
        db.session.add(new_cat)
        db.session.commit()

        log_action("log_add_category", "category", new_cat.id)
        flash("category_added_success", "success")
        return redirect(url_for('manage_categories'))

    parent_id = request.args.get('parent_id')
    selected_parent = Category.query.get(parent_id) if parent_id else None
    role = session.get('role')
    all_categories = Category.query.all()
    category_tree = build_category_tree(all_categories)

    return render_template('add_category.html', tree=category_tree, selected_parent=selected_parent, role=role)


@app.route('/categories/<int:category_id>/responses/add', methods=['GET', 'POST'])
def add_response_for_category(category_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    category = Category.query.get_or_404(category_id)

    if request.method == 'POST':
        response_type = request.form.get('type')

        if response_type in ['form', 'chat']:
            flash("invalid_response_type", "danger")
            return redirect(request.url)

        answer_fr = answer_en = answer_ar = file_url = None
        source_lang = "fr"  # valeur par défaut

        if response_type == 'text':
            content = request.form.get('content')
            try:
                detected_lang = detect(content)
                if detected_lang not in ["fr", "en", "ar"]:
                    detected_lang = "fr"
                source_lang = detected_lang

                if detected_lang == "fr":
                    answer_fr = content
                    answer_en = translate_text(content, "fr", "en")
                    answer_ar = translate_text(content, "fr", "ar")
                elif detected_lang == "en":
                    answer_en = content
                    answer_fr = translate_text(content, "en", "fr")
                    answer_ar = translate_text(answer_fr, "fr", "ar")
                elif detected_lang == "ar":
                    answer_ar = content
                    answer_fr = translate_text(content, "ar", "fr")
                    answer_en = translate_text(answer_fr, "fr", "en")

            except Exception:
                answer_fr = answer_en = answer_ar = "[ERROR] " + content
                source_lang = "fr"

        elif response_type == 'link':
            link = request.form.get('link')
            answer_fr = answer_en = answer_ar = link
            source_lang = "fr"

        elif response_type == 'contact':
            contact = request.form.get('content')
            answer_fr = answer_en = answer_ar = contact
            source_lang = "fr"

        elif response_type == 'file':
            uploaded_file = request.files.get('file')
            if uploaded_file and uploaded_file.filename:
                filename = secure_filename(uploaded_file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                uploaded_file.save(file_path)
                file_url = file_path
            source_lang = None

        new_response = Response(
            type=response_type,
            answer_fr=answer_fr,
            answer_en=answer_en,
            answer_ar=answer_ar,
            file_url=file_url,
            source_lang=source_lang,
            category_id=category.id
        )
        db.session.add(new_response)
        db.session.commit()

        # ✅ ENREGISTREMENT DU LOG
        log_action("log_add_response", "response", new_response.id)

        flash("response_added_success", "success")
        return redirect(url_for('responses_by_category', category_id=category.id))

    return render_template('add_response_for_category.html', category=category, role=session.get('role'))

@app.route('/responses/edit/<int:response_id>', methods=['GET', 'POST'])
def edit_response(response_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    response = Response.query.get_or_404(response_id)

    if request.method == 'POST':
        new_type = request.form.get('type')

        if new_type in ['form', 'chat']:
            flash("invalid_response_type", "danger")
            return redirect(request.url)

        response.type = new_type

        if new_type == 'text':
            new_fr = request.form.get('answer_fr', '').strip()
            new_en = request.form.get('answer_en', '').strip()
            new_ar = request.form.get('answer_ar', '').strip()

            source_lang = response.source_lang or "fr"

            if source_lang == "fr":
                if new_fr != response.answer_fr:
                    response.answer_fr = new_fr
                    response.answer_en = translate_text(new_fr, "fr", "en")
                    response.answer_ar = translate_text(new_fr, "fr", "ar")
                else:
                    response.answer_en = new_en or response.answer_en
                    response.answer_ar = new_ar or response.answer_ar

            elif source_lang == "en":
                if new_en != response.answer_en:
                    response.answer_en = new_en
                    fr = translate_text(new_en, "en", "fr")
                    response.answer_fr = fr
                    response.answer_ar = translate_text(fr, "fr", "ar")
                else:
                    response.answer_fr = new_fr or response.answer_fr
                    response.answer_ar = new_ar or response.answer_ar

            elif source_lang == "ar":
                if new_ar != response.answer_ar:
                    response.answer_ar = new_ar
                    fr = translate_text(new_ar, "ar", "fr")
                    response.answer_fr = fr
                    response.answer_en = translate_text(fr, "fr", "en")
                else:
                    response.answer_fr = new_fr or response.answer_fr
                    response.answer_en = new_en or response.answer_en

        elif new_type == 'link':
            response.answer_fr = request.form.get('link', '').strip()
            response.answer_en = ""
            response.answer_ar = ""

        elif new_type == 'contact':
            response.answer_fr = request.form.get('contact', '').strip()
            response.answer_en = ""
            response.answer_ar = ""

        elif new_type == 'file':
            uploaded_file = request.files.get('file')
            if uploaded_file and uploaded_file.filename:
                filename = secure_filename(uploaded_file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                uploaded_file.save(file_path)
                response.file_url = file_path

        db.session.commit()

        # ✅ ENREGISTREMENT DU LOG
        log_action("log_edit_response", "response", response.id)

        flash("response_edited_success", "success")
        return redirect(url_for('responses_by_category', category_id=response.category_id))

    return render_template('edit_response.html', response=response, role=session.get('role'))

@app.route('/categories/<int:category_id>/responses')
def responses_by_category(category_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    category = Category.query.get_or_404(category_id)
    responses = Response.query.filter_by(category_id=category.id).all()
    role = session.get('role')

    lang_code = session.get("lang", "fr")
    lang_attr = "answer_" + lang_code

    return render_template(
        'responses_by_category.html',
        category=category,
        responses=responses,
        lang_attr=lang_attr,
        role=role
    )


@app.route('/responses/delete/<int:response_id>')
def delete_response(response_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    response = Response.query.get_or_404(response_id)
    category_id = response.category_id  # on sauvegarde avant suppression

    db.session.delete(response)
    db.session.commit()

    # ✅ ENREGISTREMENT DU LOG
    log_action("log_delete_response", "response", response_id)

    flash("Réponse supprimée avec succès.", "success")
    return redirect(url_for('responses_by_category', category_id=category_id))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def log_action(action, target_type, target_id=None):
    if 'admin_id' in session:
        print("✅ LOG enregistré :", action, target_type, target_id)  # 🔍 debug console

        new_log = Log(
            admin_id=session['admin_id'],
            action=action,
            target_type=target_type,
            target_id=target_id
        )
        db.session.add(new_log)
        db.session.commit()

@app.route('/logs')
def show_logs():
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    logs = Log.query.order_by(Log.timestamp.desc()).all()

    return render_template('logs.html', logs=logs, role=session.get('role'))


from api_routes import api_bp
app.register_blueprint(api_bp)

from text_api import text_api_bp
app.register_blueprint(text_api_bp)

from preload_utils import preload_all_languages

with app.app_context():
    preload_all_languages()

@app.route('/settings', methods=['POST'])
def update_settings():
    if 'role' not in session or session['role'] != 'superadmin':
        return redirect(url_for('dashboard'))

    selected_lang = request.form.get('chatbot_lang')
    if selected_lang in ['fr', 'en', 'ar']:
        Setting.set_value('CHATBOT_LANGUAGE', selected_lang)
        flash("chatbot_lang_updated", "success")
    else:
        flash("chatbot_lang_invalid", "danger")

    return redirect(url_for('dashboard'))

@app.route('/test/lang')
def test_lang():
    return f"Langue du chatbot: {Setting.get_value('CHATBOT_LANGUAGE', 'fr')}"



if __name__ == '__main__':
    app.run(debug=True)
