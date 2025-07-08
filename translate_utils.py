from argostranslate import translate

def translate_with_gemma(text, source_lang, target_lang):
    try:
        # 🔁 Évite les traductions inutiles
        if source_lang == target_lang:
            return text

        # 📦 Récupère les langues installées
        installed_languages = translate.get_installed_languages()
        from_lang = next((lang for lang in installed_languages if lang.code == source_lang), None)
        to_lang = next((lang for lang in installed_languages if lang.code == target_lang), None)

        # ✅ Si le modèle direct existe
        if from_lang and to_lang:
            direct = from_lang.get_translation(to_lang)
            if direct:
                return direct.translate(text)

        # 🔄 Sinon : passer par l’anglais comme pivot
        pivot_code = "en"
        pivot_lang = next((lang for lang in installed_languages if lang.code == pivot_code), None)

        if from_lang and pivot_lang and to_lang:
            to_pivot = from_lang.get_translation(pivot_lang)
            from_pivot = pivot_lang.get_translation(to_lang)

            if to_pivot and from_pivot:
                intermediate = to_pivot.translate(text)
                return from_pivot.translate(intermediate)

        # 🚫 Aucun chemin possible
        return f"[NO MODEL {source_lang}→{target_lang}] {text}"

    except Exception:
        return f"[ERROR] {text}"
