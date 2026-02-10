"""
REST API views for lists and items. JSON only; no DRF.
"""

import logging
import re
import uuid
from collections import defaultdict

from django.db.models import Count, Q
from django.forms import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from lists_app.models import GroceryList, Item
from lists_app.serializers import (
    list_to_dict,
    list_detail_to_dict,
    validate_list_name,
    validate_item_name,
    validate_quantity,
    validate_notes,
)
from lists_app.services.section_assigner import normalize_import_with_llm
from lists_app.services import item_service as item_svc
from lists_app.utils import parse_uuid, get_request_json

logger = logging.getLogger(__name__)


def _json_400(message: str, errors: dict | None = None):
    return JsonResponse({"error": message, "errors": errors or {}}, status=400)


def _json_404(message: str = "Not found"):
    return JsonResponse({"error": message}, status=404)


# ---------- Lists ----------


@require_http_methods(["GET"])
def _get_lists(request):
    """GET /api/lists/ - list all lists (active first, then archived)."""
    lists = GroceryList.objects.annotate(
        items_count=Count("items"),
        items_checked=Count("items", filter=Q(items__checked=True)),
    )
    logger.debug("api list_lists count=%d", len(lists))
    return JsonResponse(
        {
            "lists": [
                {**list_to_dict(g), "items_count": g.items_count, "items_checked": g.items_checked}
                for g in lists
            ]
        }
    )


@require_http_methods(["POST"])
@csrf_exempt
def _create_list(request):
    """POST /api/lists/ - create a new list."""
    body, err = get_request_json(request)
    if err is not None:
        return err
    name = validate_list_name(body.get("name"))
    grocery_list = GroceryList.objects.create(name=name)
    logger.info("api create_list list_id=%s name=%r", grocery_list.id, name)
    return JsonResponse(list_to_dict(grocery_list), status=201)


def _get_list_or_404(list_id) -> GroceryList | JsonResponse:
    uid = parse_uuid(list_id)
    if uid is None:
        logger.debug("api list 404 invalid list_id=%r", list_id)
        return _json_404("Liste introuvable.")
    try:
        return GroceryList.objects.get(pk=uid)
    except GroceryList.DoesNotExist:
        logger.debug("api list 404 list_id=%s", list_id)
        return _json_404("Liste introuvable.")


@require_http_methods(["GET"])
def _get_list(request, list_id):
    """GET /api/lists/<uuid>/ - list detail with items by section."""
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return gl
    logger.debug("api get_list list_id=%s", list_id)
    return JsonResponse(list_detail_to_dict(gl))


@require_http_methods(["PATCH", "PUT"])
@csrf_exempt
def _patch_list(request, list_id):
    """PATCH /api/lists/<uuid>/ - update name and/or archived."""
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return gl
    body, err = get_request_json(request)
    if err is not None:
        return err
    if "name" in body:
        gl.name = validate_list_name(body["name"])
    if "archived" in body:
        gl.archived = bool(body["archived"])
    gl.save()
    logger.info("api patch_list list_id=%s archived=%s", list_id, gl.archived)
    return JsonResponse(list_to_dict(gl))


@require_http_methods(["DELETE"])
@csrf_exempt
def _delete_list(request, list_id):
    """DELETE /api/lists/<uuid>/ - delete list and all items."""
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return gl
    gl.delete()
    logger.info("api delete_list list_id=%s", list_id)
    return JsonResponse({"ok": True}, status=204)


@require_http_methods(["POST"])
@csrf_exempt
def _parse_import(request, list_id):
    """POST /api/lists/<uuid>/parse-import/ - normalize pasted text via LLM. Body: { \"text\": \"...\" }."""
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return gl
    body, err = get_request_json(request)
    if err is not None:
        return err
    text = body.get("text") or ""
    items = normalize_import_with_llm(text)
    if not items:
        return JsonResponse(
            {"error": "llm_unavailable", "message": "LLM indisponible ou échec de l'analyse."},
            status=503,
        )
    return JsonResponse({"items": items})


def _parse_quantity_with_unit(s: str) -> tuple[float, str] | None:
    """Parse '100 g' or '1.5 l' into (number, unit). Unit lowercase. Returns None if not matched."""
    s = (s or "").strip()
    if not s:
        return None
    # Match number (int or decimal) optionally followed by unit (letters, maybe with spaces)
    m = re.match(r"^([\d.,]+)\s*([a-zA-Z\u00e0-\u024f]+)?\s*$", s)
    if not m:
        return None
    num_str, unit = m.group(1), (m.group(2) or "").strip().lower()
    num_str = num_str.replace(",", ".")
    try:
        val = float(num_str)
    except ValueError:
        return None
    return (val, unit or "")


def _merge_quantities(quantities: list[str]) -> str:
    """Sum when all numeric or all same unit (e.g. 100 g + 100 g -> 200 g); else concatenate with ' + '. Capped at 80 chars."""
    qs = [q.strip() for q in quantities if q and str(q).strip()]
    if not qs:
        return ""
    # Try parse as "number unit" for each
    parsed = [_parse_quantity_with_unit(q) for q in qs]
    if all(p is not None for p in parsed) and parsed:
        units = [p[1] for p in parsed]
        if len(set(units)) == 1:
            total = sum(p[0] for p in parsed)
            unit = units[0]
            if unit:
                result = f"{int(total) if total == int(total) else total} {unit}".strip()
            else:
                result = str(int(total) if total == int(total) else total)
            return result[:80]
    # Fallback: plain numbers only
    numeric_vals = []
    for q in qs:
        try:
            v = int(q)
        except ValueError:
            try:
                v = float(q.replace(",", "."))
            except ValueError:
                return " + ".join(qs)[:80]
        numeric_vals.append(v)
    total = sum(numeric_vals)
    return str(int(total) if total == int(total) else total)[:80]


def _dedup_name_key(name: str) -> str:
    """Normalize name for deduplication: strip, lower, then singularize so 'pomme' and 'pommes' merge."""
    key = (name or "").strip().lower()
    if len(key) >= 3:
        if key.endswith("s") and not key.endswith("ss"):
            key = key[:-1]
        elif key.endswith("x"):
            key = key[:-1]
    return key


def deduplicate_list_items(list_id: uuid.UUID) -> GroceryList:
    """Merge items with same normalized name (strip+lower+singular); sum numeric quantities, concat notes. Returns the list."""
    gl = GroceryList.objects.get(pk=list_id)
    items = list(
        gl.items.select_related("section").order_by("section__position", "position")
    )
    groups = defaultdict(list)
    for it in items:
        key = _dedup_name_key(it.name or "")
        groups[key].append(it)
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        first, rest = group[0], group[1:]
        quantities = [first.quantity or ""] + [it.quantity or "" for it in rest]
        first.quantity = _merge_quantities(quantities)[:80]
        notes_parts = [first.notes or ""] + [it.notes or "" for it in rest]
        first.notes = " ; ".join(p for p in notes_parts if (p or "").strip())[:2000]
        first.checked = any(it.checked for it in group)
        first.save()
        for it in rest:
            it.delete()
    return gl


@require_http_methods(["POST"])
@csrf_exempt
def _deduplicate(request, list_id):
    """POST /api/lists/<uuid>/deduplicate/ - merge duplicate items by name, sum quantities."""
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return gl
    gl = deduplicate_list_items(list_id)
    logger.info("api deduplicate list_id=%s", list_id)
    return JsonResponse(list_detail_to_dict(gl))


# ---------- Items ----------


def _get_item_or_404(
    list_id, item_id
) -> tuple[GroceryList | None, Item | None, JsonResponse | None]:
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return None, None, gl
    uid = parse_uuid(item_id)
    if uid is None:
        logger.debug("api item 404 invalid item_id=%r", item_id)
        return gl, None, _json_404("Article introuvable.")
    try:
        item = Item.objects.get(pk=uid, grocery_list=gl)
        return gl, item, None
    except Item.DoesNotExist:
        logger.debug("api item 404 list_id=%s item_id=%s", list_id, item_id)
        return gl, None, _json_404("Article introuvable.")


@require_http_methods(["POST"])
@csrf_exempt
def _create_item(request, list_id):
    """POST /api/lists/<uuid>/items/ - create item; section from assign_section."""
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return gl
    body, err = get_request_json(request)
    if err is not None:
        return err
    try:
        item_dict = item_svc.create_item(
            gl,
            body.get("name"),
            quantity=body.get("quantity"),
            notes=body.get("notes"),
            section_slug=body.get("section_slug"),
        )
    except ValidationError as e:
        msg = getattr(e, "messages", None) or getattr(e, "message_list", [str(e)])
        logger.warning("api create_item validation error list_id=%s: %s", list_id, msg[0] if msg else "Nom invalide.")
        return _json_400(msg[0] if msg else "Nom invalide.")
    logger.info("api create_item list_id=%s item_id=%s", list_id, item_dict.get("id"))
    return JsonResponse(item_dict, status=201)


@require_http_methods(["PATCH", "PUT"])
@csrf_exempt
def _patch_item(request, list_id, item_id):
    """PATCH /api/lists/<uuid>/items/<uuid>/ - update item."""
    gl, item, err = _get_item_or_404(list_id, item_id)
    if err is not None:
        return err
    body, err = get_request_json(request)
    if err is not None:
        return err
    kwargs = {}
    if "name" in body:
        try:
            kwargs["name"] = validate_item_name(body["name"])
        except ValidationError as e:
            msg = getattr(e, "messages", None) or getattr(e, "message_list", [str(e)])
            logger.warning("api patch_item validation error list_id=%s item_id=%s", list_id, item_id)
            return _json_400(msg[0] if msg else "Nom invalide.")
    if "quantity" in body:
        kwargs["quantity"] = validate_quantity(body["quantity"])
    if "notes" in body:
        kwargs["notes"] = validate_notes(body["notes"])
    if "checked" in body:
        kwargs["checked"] = bool(body["checked"])
    if "position" in body:
        try:
            kwargs["position"] = int(body["position"])
        except (TypeError, ValueError):
            pass
    if "section_id" in body:
        kwargs["section_id"] = body["section_id"]
    item_dict = item_svc.update_item(gl, item_id, **kwargs)
    if item_dict is None:
        return _json_404("Article introuvable.")
    logger.info("api patch_item list_id=%s item_id=%s", list_id, item_id)
    return JsonResponse(item_dict)


@require_http_methods(["DELETE"])
@csrf_exempt
def _delete_item(request, list_id, item_id):
    """DELETE /api/lists/<uuid>/items/<uuid>/ - delete item."""
    gl, item, err = _get_item_or_404(list_id, item_id)
    if err is not None:
        return err
    item.delete()
    logger.info("api delete_item list_id=%s item_id=%s", list_id, item_id)
    return JsonResponse({"ok": True}, status=204)


# ---------- Reorder ----------


@require_http_methods(["PATCH", "PUT"])
@csrf_exempt
def _reorder(request, list_id):
    """PATCH /api/lists/<uuid>/reorder/ - reorder sections and/or items."""
    gl = _get_list_or_404(list_id)
    if isinstance(gl, JsonResponse):
        return gl
    body, err = get_request_json(request)
    if err is not None:
        return err
    section_order = body.get("section_order")
    item_orders = body.get("item_orders")
    result = item_svc.apply_reorder(gl, section_order=section_order, item_orders=item_orders)
    logger.info("api reorder list_id=%s", list_id)
    return JsonResponse(result)


# ---------- Dispatchers (same path, different methods) ----------


@csrf_exempt
def api_lists(request):
    """GET or POST /api/lists/."""
    if request.method == "GET":
        return _get_lists(request)
    if request.method == "POST":
        return _create_list(request)
    logger.warning("api_lists method not allowed: %s", request.method)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def api_list_detail(request, list_id):
    """GET, PATCH, or DELETE /api/lists/<id>/."""
    if request.method == "GET":
        return _get_list(request, list_id)
    if request.method in ("PATCH", "PUT"):
        return _patch_list(request, list_id)
    if request.method == "DELETE":
        return _delete_list(request, list_id)
    logger.warning("api_list_detail method not allowed: %s", request.method)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def api_item_detail(request, list_id, item_id):
    """PATCH or DELETE /api/lists/<id>/items/<id>/."""
    if request.method in ("PATCH", "PUT"):
        return _patch_item(request, list_id, item_id)
    if request.method == "DELETE":
        return _delete_item(request, list_id, item_id)
    logger.warning("api_item_detail method not allowed: %s", request.method)
    return JsonResponse({"error": "Method not allowed"}, status=405)


# URL route names (urls.py references these)
api_parse_import = _parse_import
api_deduplicate = _deduplicate
api_create_item = _create_item
api_reorder = _reorder
