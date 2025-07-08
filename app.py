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

app = Flask(__name__)
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
            return redirect(url_for('dashboard'))

        user = Admin.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="invalid_credentials")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session.get('role'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add_admin', methods=['GET', 'POST'])
def add_admin():
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        requested_role = request.form['role']

        if requested_role == 'superadmin' and session['username'] != 'admin':
            flash("only_initial_superadmin_can_create", "danger")
            return redirect(url_for('add_admin'))

        if password != confirm_password:
            flash("passwords_dont_match", "danger")
            return redirect(url_for('add_admin'))

        if Admin.query.filter_by(username=username).first():
            flash("username_already_exists", "danger")
            return redirect(url_for('add_admin'))

        new_admin = Admin(
            username=username,
            password_hash=generate_password_hash(password),
            role=requested_role
        )
        db.session.add(new_admin)
        db.session.commit()
        flash("admin_added_success", "success")
        return redirect(url_for('manage_admins'))

    return render_template('add_admin.html')

@app.route('/manage_admins')
def manage_admins():
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    admins = Admin.query.all()
    return render_template('manage_admins.html', admins=admins, username=session['username'])

@app.route('/delete_admin/<int:id>', methods=['POST'])
def delete_admin(id):
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    admin = Admin.query.get_or_404(id)

    if admin.username == 'admin':
        flash("cannot_delete_initial_superadmin", "danger")
        return redirect(url_for('manage_admins'))

    if admin.role == 'superadmin' and admin.username != session['username'] and session['username'] != 'admin':
        flash("cannot_modify_other_superadmin", "danger")
        return redirect(url_for('manage_admins'))

    db.session.delete(admin)
    db.session.commit()
    flash("admin_deleted_success", "success")
    return redirect(url_for('manage_admins'))

@app.route('/edit_admin/<int:id>', methods=['GET', 'POST'])
def edit_admin(id):
    if 'username' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('login'))

    admin = Admin.query.get_or_404(id)

    if admin.username == 'admin':
        flash("cannot_modify_initial_superadmin", "danger")
        return redirect(url_for('manage_admins'))

    if admin.role == 'superadmin' and admin.username != session['username'] and session['username'] != 'admin':
        flash("cannot_modify_other_superadmin", "danger")
        return redirect(url_for('manage_admins'))

    if request.method == 'POST':
        admin.username = request.form['username']
        requested_role = request.form['role']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if requested_role == 'superadmin' and session['username'] != 'admin':
            flash("only_initial_superadmin_can_promote", "danger")
            return redirect(url_for('edit_admin', id=id))

        if password:
            if password != confirm:
                flash("passwords_dont_match", "danger")
                return redirect(url_for('edit_admin', id=id))
            admin.password_hash = generate_password_hash(password)

        admin.role = requested_role
        db.session.commit()
        flash("admin_updated_success", "success")
        return redirect(url_for('manage_admins'))

    return render_template('edit_admin.html', admin=admin)

# -------------------- À partir d'ici tu peux continuer --------------------

# -------------------- Catégories --------------------
def build_category_tree(categories, parent_id=None, level=0):
    lang = session.get('lang', 'fr')  # 🔁 fallback sur 'fr'

    tree = []
    for cat in categories:
        if cat.parent_id == parent_id:
            name = cat.name_fr
            if lang == 'en':
                name = cat.name_en or cat.name_fr
            elif lang == 'ar':
                name = cat.name_ar or cat.name_fr

            tree.append({
                'id': cat.id,
                'translated_name': name,  # ← c'est ce que ton HTML attend
                'level': level,
                'response_count': len(cat.responses),
                'children': build_category_tree(categories, cat.id, level + 1)
            })

    return tree

@app.route('/manage_categories')
def manage_categories():
    if 'username' not in session:
        return redirect(url_for('login'))

    categories = Category.query.all()
    category_tree = build_category_tree(categories)
    return render_template('manage_categories.html', tree=category_tree)

@app.route('/edit_category/<int:id>', methods=['GET', 'POST'])
def edit_category(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    category = Category.query.get_or_404(id)

    if request.method == 'POST':
        name_input = request.form.get('name_input', '').strip()
        name_en_manual = request.form.get('name_en', '').strip()
        name_ar_manual = request.form.get('name_ar', '').strip()

        detected_lang = detect(name_input)

        # Traduction selon la langue détectée
        if detected_lang == 'fr':
            category.name_fr = name_input
            category.name_en = name_en_manual if name_en_manual else translate_text(name_input, 'fr', 'en')
            category.name_ar = name_ar_manual if name_ar_manual else translate_text(name_input, 'fr', 'ar')
        elif detected_lang == 'en':
            category.name_en = name_input
            category.name_fr = translate_text(name_input, 'en', 'fr')
            category.name_ar = name_ar_manual if name_ar_manual else translate_text(name_input, 'en', 'ar')
        elif detected_lang == 'ar':
            category.name_ar = name_input
            category.name_fr = translate_text(name_input, 'ar', 'fr')
            category.name_en = name_en_manual if name_en_manual else translate_text(name_input, 'ar', 'en')
        else:
            # fallback
            category.name_fr = name_input
            category.name_en = name_en_manual
            category.name_ar = name_ar_manual

        # Parent
        parent_id = request.form.get('parent_id') or None
        category.parent_id = int(parent_id) if parent_id else None

        db.session.commit()
        flash("category_updated_success", "success")
        return redirect(url_for('manage_categories'))

    all_categories = Category.query.all()
    tree = build_category_tree([cat for cat in all_categories if cat.id != id])
    return render_template('edit_category.html', category=category, tree=tree)

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

        new_cat = Category(
            name_fr=name_fr,
            name_en=name_en,
            name_ar=name_ar,
            parent_id=parent_id
        )
        db.session.add(new_cat)
        db.session.commit()
        flash("category_added_success", "success")
        return redirect(url_for('manage_categories'))

    parent_id = request.args.get('parent_id')
    selected_parent = Category.query.get(parent_id) if parent_id else None

    all_categories = Category.query.all()
    category_tree = build_category_tree(all_categories)

    return render_template('add_category.html', tree=category_tree, selected_parent=selected_parent)

@app.route('/categories/<int:category_id>/responses/add', methods=['GET', 'POST'])
def add_response_for_category(category_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    category = Category.query.get_or_404(category_id)

    if request.method == 'POST':
        response_type = request.form.get('type')
        content = request.form.get('content')
        uploaded_file = request.files.get('file')

        # Détection automatique de la langue
        detected_lang = detect(content)

        try:
            detected_lang = detect(content)
            if detected_lang not in ["fr", "en", "ar"]:
                detected_lang = "en"

            if detected_lang == "fr":
                answer_fr = content
            elif detected_lang == "en":
                answer_fr = translate_text(content, source_lang="en", target_lang="fr")
            elif detected_lang == "ar":
                answer_fr = translate_text(content, source_lang="ar", target_lang="fr")
            else:
                answer_fr = content

            answer_en = translate_text(answer_fr, source_lang="fr", target_lang="en")
            answer_ar = translate_text(answer_fr, source_lang="fr", target_lang="ar")


        except Exception as e:
            answer_fr = "[ERROR] " + content
            answer_en = "[ERROR] " + content
            answer_ar = "[ERROR] " + content

        file_url = None
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            uploaded_file.save(file_path)
            file_url = file_path

        new_response = Response(
            type=response_type,
            answer_fr=answer_fr,
            answer_en=answer_en,
            answer_ar=answer_ar,
            file_url=file_url,
            category_id=category.id
        )
        db.session.add(new_response)
        db.session.commit()
        flash("Réponse ajoutée avec succès.", "success")
        return redirect(url_for('responses_by_category', category_id=category.id))

    return render_template('add_response_for_category.html', category=category)

@app.route('/responses/edit/<int:response_id>', methods=['GET', 'POST'])
def edit_response(response_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    response = Response.query.get_or_404(response_id)
    categories = Category.query.all()

    if request.method == 'POST':
        response.category_id = request.form.get('category_id')
        response.type = request.form.get('type')

        new_fr = request.form.get('answer_fr', '').strip()
        new_en = request.form.get('answer_en', '').strip()
        new_ar = request.form.get('answer_ar', '').strip()

        old_fr = response.answer_fr
        old_en = response.answer_en
        old_ar = response.answer_ar

        # 🧠 Détection langue source à partir du champ principal non vide
        source_text = new_fr or new_en or new_ar
        detected_lang = detect(source_text)

        if detected_lang == "fr":
            response.answer_fr = new_fr
            response.answer_en = translate_text(new_fr, "fr", "en") if new_en == old_en else new_en
            response.answer_ar = translate_text(new_fr, "fr", "ar") if new_ar == old_ar else new_ar

        elif detected_lang == "en":
            translated_fr = translate_text(new_en, "en", "fr")
            response.answer_fr = translated_fr
            response.answer_en = new_en
            response.answer_ar = translate_text(translated_fr, "fr", "ar") if new_ar == old_ar else new_ar

        elif detected_lang == "ar":
            translated_fr = translate_text(new_ar, "ar", "fr")
            response.answer_fr = translated_fr
            response.answer_ar = new_ar
            response.answer_en = translate_text(translated_fr, "fr", "en") if new_en == old_en else new_en

        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            uploaded_file.save(file_path)
            response.file_url = file_path

        db.session.commit()
        flash("Réponse modifiée avec succès.", "success")
        return redirect(url_for('responses_by_category', category_id=response.category_id))

    return render_template('edit_response.html', response=response, categories=categories)

@app.route('/categories/<int:category_id>/responses')
def responses_by_category(category_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    category = Category.query.get_or_404(category_id)
    responses = Response.query.filter_by(category_id=category.id).all()

    # ✅ On utilise la langue stockée dans session['lang'] (défaut = 'fr')
    lang_code = session.get("lang", "fr")
    lang_attr = "answer_" + lang_code

    return render_template(
        'responses_by_category.html',
        category=category,
        responses=responses,
        lang_attr=lang_attr
    )
@app.route('/responses/delete/<int:response_id>')
def delete_response(response_id):
    response = Response.query.get_or_404(response_id)
    db.session.delete(response)
    db.session.commit()
    flash("Réponse supprimée avec succès.", "success")
    return redirect(url_for('responses_by_category', category_id=response.category_id))
# --------------------
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
