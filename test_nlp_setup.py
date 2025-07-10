from langdetect import detect
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
import re

# Télécharger les stopwords
nltk.download('stopwords')
from nltk.corpus import stopwords

# Nettoyage simple avec gestion de l’arabe
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)

    arabic_diacritics = re.compile(r'[\u064B-\u0652]')
    text = arabic_diacritics.sub('', text)
    text = text.replace('ى', 'ي').replace('ة', 'ه').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')

    return text.strip()

# Phrases de test
question = "أريد استخراج جواز السفر"
answers = [
    "هذا هو الرابط الخاص بجواز السفر",
    "يجب عليك تقديم نسخة من بطاقة الهوية الوطنية",
    "رخصة السياقة متوفرة عبر الموقع"
]

# Détection de langue
lang = detect(question)
print(f"[LANG DETECTION] Langue détectée : {lang}")

# Nettoyage
stop_words = stopwords.words('arabic')
question_clean = clean_text(question)
answers_clean = [clean_text(ans) for ans in answers]

# Vectorisation TF-IDF
vectorizer = TfidfVectorizer(stop_words=stop_words)
tfidf_matrix = vectorizer.fit_transform(answers_clean + [question_clean])

# Similarité
similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()

# Résultat
for i, score in enumerate(similarities):
    print(f"[SIMILARITY] Score avec réponse {i+1} : {score:.4f}")

best_index = similarities.argmax()
print(f"[RESULT] Meilleure réponse : {answers[best_index]}")
