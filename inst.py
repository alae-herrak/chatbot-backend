from sentence_transformers import SentenceTransformer

# Télécharger et sauvegarder localement
model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
model.save("models/all-MiniLM-L12-v2")  # 📁 Cela crée un dossier local
print("✅ Modèle téléchargé et enregistré localement.")