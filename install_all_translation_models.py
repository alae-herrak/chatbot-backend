import argostranslate.package
import argostranslate.translate

print("🔁 Mise à jour de l'index Argos...")
argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()

# 🎯 Tous les couples à installer
needed_models = [
    ("fr", "en"),
    ("fr", "ar"),
    ("en", "fr"),
    ("en", "ar"),
    ("ar", "fr"),
    ("ar", "en"),
]

for src, tgt in needed_models:
    print(f"🔽 Téléchargement du modèle {src} → {tgt}...")
    match = next((p for p in available if p.from_code == src and p.to_code == tgt), None)
    if match:
        path = match.download()
        argostranslate.package.install_from_path(path)
        print(f"✅ Modèle {src} → {tgt} installé avec succès.")
    else:
        print(f"❌ Modèle {src} → {tgt} non trouvé.")
