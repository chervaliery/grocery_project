# Data migration: seed SectionKeyword from the original static keyword list.

from django.db import migrations


# Copy of KEYWORDS_TO_SLUG from section_assigner (keyword -> section slug).
KEYWORDS_TO_SLUG = {
    "pomme": "fruits_legumes",
    "poire": "fruits_legumes",
    "banane": "fruits_legumes",
    "orange": "fruits_legumes",
    "citron": "fruits_legumes",
    "tomate": "fruits_legumes",
    "salade": "fruits_legumes",
    "carotte": "fruits_legumes",
    "oignon": "fruits_legumes",
    "ail": "fruits_legumes",
    "pomme de terre": "fruits_legumes",
    "patate": "fruits_legumes",
    "courgette": "fruits_legumes",
    "aubergine": "fruits_legumes",
    "poivron": "fruits_legumes",
    "concombre": "fruits_legumes",
    "haricot": "fruits_legumes",
    "petit pois": "fruits_legumes",
    "épinard": "fruits_legumes",
    "brocoli": "fruits_legumes",
    "chou": "fruits_legumes",
    "fruits": "fruits_legumes",
    "légumes": "fruits_legumes",
    "legumes": "fruits_legumes",
    "viande": "viande_volaille",
    "poulet": "viande_volaille",
    "boeuf": "viande_volaille",
    "bœuf": "viande_volaille",
    "steak": "viande_volaille",
    "porc": "viande_volaille",
    "agneau": "viande_volaille",
    "volaille": "viande_volaille",
    "dinde": "viande_volaille",
    "poisson": "poisson_fruits_de_mer",
    "saumon": "poisson_fruits_de_mer",
    "truite": "poisson_fruits_de_mer",
    "cabillaud": "poisson_fruits_de_mer",
    "crevette": "poisson_fruits_de_mer",
    "moule": "poisson_fruits_de_mer",
    "thon": "poisson_fruits_de_mer",
    "fruits de mer": "poisson_fruits_de_mer",
    "charcuterie": "charcuterie",
    "jambon": "charcuterie",
    "saucisson": "charcuterie",
    "bacon": "charcuterie",
    "pâté": "charcuterie",
    "pate": "charcuterie",
    "lait": "produits_laitiers_oeufs",
    "yaourt": "produits_laitiers_oeufs",
    "yogourt": "produits_laitiers_oeufs",
    "fromage": "produits_laitiers_oeufs",
    "crème": "produits_laitiers_oeufs",
    "creme": "produits_laitiers_oeufs",
    "beurre": "produits_laitiers_oeufs",
    "œuf": "produits_laitiers_oeufs",
    "oeuf": "produits_laitiers_oeufs",
    "oeufs": "produits_laitiers_oeufs",
    "œufs": "produits_laitiers_oeufs",
    "riz": "epicerie",
    "pâtes": "epicerie",
    "pates": "epicerie",
    "huile": "epicerie",
    "vinaigre": "epicerie",
    "sucre": "epicerie",
    "farine": "epicerie",
    "sel": "epicerie",
    "épice": "epicerie",
    "epice": "epicerie",
    "sauce": "epicerie",
    "conserve": "epicerie",
    "céréale": "epicerie",
    "cereale": "epicerie",
    "biscuit": "epicerie",
    "chocolat": "epicerie",
    "confiture": "epicerie",
    "miel": "epicerie",
    "café": "epicerie",
    "cafe": "epicerie",
    "thé": "epicerie",
    "the": "epicerie",
    "pain": "boulangerie",
    "baguette": "boulangerie",
    "croissant": "boulangerie",
    "brioche": "boulangerie",
    "boulangerie": "boulangerie",
    "eau": "boissons",
    "jus": "boissons",
    "soda": "boissons",
    "vin": "boissons",
    "bière": "boissons",
    "biere": "boissons",
    "boisson": "boissons",
    "coca": "boissons",
    "surgelé": "surgeles",
    "surgelés": "surgeles",
    "surgeles": "surgeles",
    "glace": "surgeles",
    "frites": "surgeles",
    "savon": "hygiene_maison",
    "shampoing": "hygiene_maison",
    "dentifrice": "hygiene_maison",
    "papier toilette": "hygiene_maison",
    "lessive": "hygiene_maison",
    "éponge": "hygiene_maison",
    "eponge": "hygiene_maison",
}


def seed_keywords(apps, schema_editor):
    Section = apps.get_model("lists_app", "Section")
    SectionKeyword = apps.get_model("lists_app", "SectionKeyword")
    for keyword, slug in KEYWORDS_TO_SLUG.items():
        try:
            section = Section.objects.get(name_slug=slug)
            SectionKeyword.objects.get_or_create(
                keyword=keyword, defaults={"section": section}
            )
        except Section.DoesNotExist:
            pass


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("lists_app", "0003_add_section_keyword"),
    ]

    operations = [
        migrations.RunPython(seed_keywords, noop),
    ]
