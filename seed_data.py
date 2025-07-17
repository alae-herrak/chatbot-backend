from app import db
from models import Category, Response
from datetime import datetime
from app import app

def create_category(name_fr, name_en, name_ar, parent=None, source_lang='fr'):
    existing = Category.query.filter_by(name_fr=name_fr, parent_id=parent.id if parent else None).first()
    if existing:
        return existing
    cat = Category(name_fr=name_fr, name_en=name_en, name_ar=name_ar, parent=parent, source_lang=source_lang)
    db.session.add(cat)
    db.session.commit()
    return cat

def create_response(type_, fr, en, ar, cat, file_url=None, source_lang='fr'):
    existing = Response.query.filter_by(type=type_, category_id=cat.id, answer_fr=fr).first()
    if existing:
        return
    resp = Response(
        type=type_,
        answer_fr=fr,
        answer_en=en,
        answer_ar=ar,
        category=cat,
        file_url=file_url,
        source_lang=source_lang,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(resp)
    db.session.commit()

def seed():
    # 🟫 Domaine : Justice et documents légaux
    justice = create_category("Justice et Légal", "Justice and Legal", "العدل والوثائق القانونية")
    extrait_naissance = create_category("Extrait d'acte de naissance", "Birth certificate", "شهادة الازدياد", justice)
    casier_judiciaire = create_category("Casier judiciaire", "Criminal record", "السجل العدلي", justice)
    autorisation_paternelle = create_category("Autorisation paternelle", "Parental authorization", "إذن الأب", justice)

    create_response("text",
        "Demandez votre extrait à l'état civil avec votre carte d'identité.",
        "Request your birth certificate at the civil registry with your ID.",
        "اطلب شهادة الازدياد من مصلحة الحالة المدنية مصحوبا ببطاقتك الوطنية.",
        extrait_naissance)

    create_response("file", None, None, None, casier_judiciaire, "/files/casier_judiciaire.pdf")
    create_response("contact",
        "Présentez-vous au tribunal de votre région.",
        "Go to your regional court.",
        "توجه إلى المحكمة الابتدائية بمنطقتك.",
        autorisation_paternelle)

    # 🟦 Domaine : Electricité & Eau
    services = create_category("Électricité et Eau", "Electricity and Water", "الماء والكهرباء")
    raccordement_elec = create_category("Demande de raccordement électricité", "Electricity connection", "طلب ربط الكهرباء", services)
    reclamation_facture = create_category("Réclamation facture eau", "Water bill complaint", "شكاية فاتورة الماء", services)

    create_response("link", None, None, None, raccordement_elec, "https://redal.ma/raccordement")
    create_response("text",
        "Vous pouvez contester une facture en ligne ou au guichet.",
        "You can contest a bill online or at the office.",
        "يمكنك الاعتراض على الفاتورة عبر الإنترنت أو في الوكالة.",
        reclamation_facture)

if __name__ == "__main__":
    with app.app_context():
        seed()
    print("✅ Nouveaux domaines ajoutés avec succès.")
