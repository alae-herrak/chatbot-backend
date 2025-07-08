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
    type = db.Column(db.String(20), nullable=False)  # text, link, contact, file, chat
    answer_fr = db.Column(db.Text, nullable=True)
    answer_en = db.Column(db.Text, nullable=True)
    answer_ar = db.Column(db.Text, nullable=True)
    file_url = db.Column(db.String(300), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = db.relationship('Category', backref='responses')

    def __repr__(self):
        return f'<Response {self.type}>'

class FormField(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label_fr = db.Column(db.String(255), nullable=False)
    label_en = db.Column(db.String(255))
    label_ar = db.Column(db.String(255))
    field_type = db.Column(db.String(50), nullable=False)  # 'text', 'textarea', etc.
    response_id = db.Column(db.Integer, db.ForeignKey('response.id'), nullable=False)
