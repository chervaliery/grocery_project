"""
Shared item operations for API and WebSocket: create, update, reorder.
"""

from django.db.models import Max

from lists_app.models import Item, Section
from lists_app.serializers import (
    item_to_dict,
    list_detail_to_dict,
    validate_item_name,
    validate_quantity,
    validate_notes,
)
from lists_app.utils import parse_uuid
from lists_app.services.item_order import reorder_section_by_name
from lists_app.services.section_assigner import assign_section


def create_item(grocery_list, name, quantity="", notes="", section_slug=None):
    """
    Create one item for a list. Uses serializers for validation.
    Returns item_to_dict(item). Raises ValidationError if name is invalid.
    """
    name = validate_item_name(name)
    quantity = validate_quantity(quantity)
    notes = validate_notes(notes)
    if section_slug and str(section_slug).strip():
        section = Section.objects.filter(name_slug=str(section_slug).strip()).first()
        if section is None:
            section = assign_section(name)
    else:
        section = assign_section(name)
    if section is None:
        section = Section.objects.get(name_slug="autre")
    max_pos = (
        grocery_list.items.filter(section=section)
        .aggregate(mx=Max("position"))
        .get("mx")
        or 0
    )
    item = Item.objects.create(
        grocery_list=grocery_list,
        name=name,
        section=section,
        quantity=quantity,
        notes=notes,
        position=max_pos + 1,
    )
    reorder_section_by_name(grocery_list, section)
    return item_to_dict(item)


def update_item(grocery_list, item_id, **kwargs):
    """
    Update an item by list and item id. Only provided keys are applied.
    Returns item_to_dict(item) or None if not found.
    Raises ValidationError if name is provided and invalid.
    """
    uid = parse_uuid(item_id)
    if uid is None:
        return None
    try:
        item = Item.objects.get(pk=uid, grocery_list=grocery_list)
    except Item.DoesNotExist:
        return None
    if "name" in kwargs and kwargs["name"] is not None:
        item.name = validate_item_name(kwargs["name"])
    if "quantity" in kwargs:
        item.quantity = validate_quantity(kwargs["quantity"])
    if "notes" in kwargs:
        item.notes = validate_notes(kwargs["notes"])
    if "checked" in kwargs:
        item.checked = bool(kwargs["checked"])
    if "position" in kwargs and kwargs["position"] is not None:
        try:
            item.position = int(kwargs["position"])
        except (TypeError, ValueError):
            pass
    if "section_id" in kwargs and kwargs["section_id"] is not None:
        try:
            sid = int(kwargs["section_id"])
            section = Section.objects.get(pk=sid)
            item.section = section
        except (TypeError, ValueError, Section.DoesNotExist):
            pass
    item.save()
    return item_to_dict(item)


def apply_reorder(grocery_list, section_order=None, item_orders=None):
    """
    Apply section_order (list of section ids) and item_orders
    (list of { item_id, position } or { section_id, item_ids }).
    Returns list_detail_to_dict(grocery_list).
    """
    if section_order and isinstance(section_order, list):
        for pos, sid in enumerate(section_order):
            try:
                Section.objects.filter(pk=sid).update(position=pos)
            except Exception:
                pass
    if item_orders and isinstance(item_orders, list):
        for entry in item_orders:
            if "item_id" in entry and "position" in entry:
                uid = parse_uuid(entry["item_id"])
                if uid:
                    try:
                        Item.objects.filter(pk=uid, grocery_list=grocery_list).update(
                            position=int(entry["position"])
                        )
                    except (ValueError, TypeError):
                        pass
            elif "section_id" in entry and "item_ids" in entry:
                for pos, iid in enumerate(entry["item_ids"]):
                    uid = parse_uuid(iid) if isinstance(iid, str) else iid
                    if uid:
                        try:
                            Item.objects.filter(
                                pk=uid, grocery_list=grocery_list
                            ).update(position=pos)
                        except Exception:
                            pass
    return list_detail_to_dict(grocery_list)
