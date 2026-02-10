"""
Helpers for item ordering within a section.
"""

from lists_app.models import GroceryList, Section


def reorder_section_by_name(grocery_list: GroceryList, section: Section) -> None:
    """
    Reorder all items in the given section alphabetically by name (case-insensitive).
    Updates each item's position so that the section displays in name order.
    """
    items = list(grocery_list.items.filter(section=section).order_by("position", "id"))
    items.sort(key=lambda i: (i.name or "").lower())
    for pos, item in enumerate(items):
        item.position = pos
        item.save(update_fields=["position"])
