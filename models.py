from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Category(db.Model):
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True)
    name_fr = db.Column(db.String(255))
    name_en = db.Column(db.String(255))
    name_ar = db.Column(db.String(255))
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    source_lang = db.Column(db.String(10), default='fr')

    # Catégorie parente
    parent = db.relationship('Category', remote_side=[id], backref='subcategories')

    def get_translated_name(self, lang):
        if lang == 'ar':
            return self.name_ar or self.name_fr
        elif lang == 'en':
            return self.name_en or self.name_fr
        else:
            return self.name_fr

    def __repr__(self):
        return f'<Category {self.name_fr}>'

class Response(db.Model):
    __tablename__ = 'response'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # text, link, contact, file, form
    answer_fr = db.Column(db.Text, nullable=True)
    answer_en = db.Column(db.Text, nullable=True)
    answer_ar = db.Column(db.Text, nullable=True)
    file_url = db.Column(db.String(300), nullable=True)
    source_lang = db.Column(db.String(5), nullable=True, default='fr')  # <- Ajout ici
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    category = db.relationship('Category', backref='responses')

    def __repr__(self):
        return f'<Response {self.type}>'



class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'))
    action = db.Column(db.String(255))
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Relation avec Admin
    admin = db.relationship('Admin', backref='logs')
