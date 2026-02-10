# Generated data migration: seed default French sections

from django.db import migrations


def seed_sections(apps, schema_editor):
    Section = apps.get_model("lists_app", "Section")
    sections = [
        (0, "fruits_legumes", "Fruits & Légumes"),
        (1, "viande_volaille", "Viande & Volaille"),
        (2, "poisson_fruits_de_mer", "Poisson & Fruits de mer"),
        (3, "charcuterie", "Charcuterie"),
        (4, "produits_laitiers_oeufs", "Produits laitiers & Œufs"),
        (5, "epicerie", "Épicerie (sucré / salé)"),
        (6, "boulangerie", "Boulangerie"),
        (7, "boissons", "Boissons"),
        (8, "surgeles", "Surgelés"),
        (9, "hygiene_maison", "Hygiène & Maison"),
        (10, "autre", "Autre"),
    ]
    for position, slug, label in sections:
        Section.objects.get_or_create(
            name_slug=slug,
            defaults={"label_fr": label, "position": position},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("lists_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_sections, noop),
    ]
