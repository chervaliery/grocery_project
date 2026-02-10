"""
Simple serialization for API responses. No DRF dependency.
"""

from datetime import date

from django.forms import ValidationError

from lists_app.models import GroceryList, Item, Section

# Max lengths (must match model or be stricter)
MAX_LIST_NAME = 200
MAX_ITEM_NAME = 200
MAX_QUANTITY = 80
MAX_NOTES = 2000


def section_to_dict(section: Section) -> dict:
    return {
        "id": section.id,
        "slug": section.name_slug,
        "label_fr": section.label_fr,
        "position": section.position,
    }


def list_to_dict(grocery_list: GroceryList) -> dict:
    return {
        "id": str(grocery_list.id),
        "name": grocery_list.name,
        "created_at": grocery_list.created_at.isoformat(),
        "archived": grocery_list.archived,
        "position": grocery_list.position,
    }


def item_to_dict(item: Item) -> dict:
    return {
        "id": str(item.id),
        "name": item.name,
        "section_id": item.section_id,
        "section_slug": item.section.name_slug,
        "section_label": item.section.label_fr,
        "quantity": item.quantity or "",
        "notes": item.notes or "",
        "checked": item.checked,
        "position": item.position,
    }


def list_detail_to_dict(grocery_list: GroceryList) -> dict:
    """List with items grouped by section (ordered)."""
    data = list_to_dict(grocery_list)
    sections_order = list(
        Section.objects.order_by("position").values_list("id", "name_slug", "label_fr")
    )
    items_by_section: dict[int, list] = {sid: [] for sid, _, _ in sections_order}
    for item in grocery_list.items.select_related("section").order_by(
        "section", "position"
    ):
        items_by_section.setdefault(item.section_id, []).append(item_to_dict(item))
    data["sections"] = [
        {
            "section_id": sid,
            "section_slug": slug,
            "section_label": label,
            "items": items_by_section.get(sid, []),
        }
        for sid, slug, label in sections_order
    ]
    return data


def default_list_name() -> str:
    return "Liste du " + date.today().strftime("%d/%m/%Y")


def validate_list_name(name) -> str:
    if name is None:
        return default_list_name()
    s = str(name).strip()[:MAX_LIST_NAME]
    return s or default_list_name()


def validate_item_name(name) -> str:
    if not name or not str(name).strip():
        raise ValidationError("Le nom de l'article est requis.")
    s = str(name).strip()[:MAX_ITEM_NAME]
    if not s:
        raise ValidationError("Le nom de l'article est requis.")
    return s


def validate_quantity(value) -> str:
    if value is None:
        return ""
    return str(value).strip()[:MAX_QUANTITY]


def validate_notes(value) -> str:
    if value is None:
        return ""
    return str(value).strip()[:MAX_NOTES]
