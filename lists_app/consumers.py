"""
WebSocket consumer for real-time list updates.
Connect to /ws/list/<list_id>/; receive actions and broadcast to group.
"""

import json
import logging
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.forms import ValidationError

from lists_app.models import AccessToken, GroceryList, Item
from lists_app.serializers import list_detail_to_dict
from lists_app.services import item_service as item_svc
from lists_app.utils import parse_uuid
from lists_app.views import SESSION_ACCESS_TOKEN_ID_KEY

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_list_exists(list_id: uuid.UUID) -> bool:
    return GroceryList.objects.filter(pk=list_id).exists()


@database_sync_to_async
def get_list_with_items(list_id: uuid.UUID) -> dict | None:
    try:
        gl = GroceryList.objects.get(pk=list_id)
        return list_detail_to_dict(gl)
    except GroceryList.DoesNotExist:
        return None


def _do_add_item(list_id, name, quantity="", notes="", section_slug=None):
    """Returns (item_dict, None) on success, (None, error_message) on validation error, (None, None) if list not found."""
    try:
        gl = GroceryList.objects.get(pk=list_id)
    except GroceryList.DoesNotExist:
        return (None, None)
    try:
        item_dict = item_svc.create_item(
            gl, name, quantity=quantity, notes=notes, section_slug=section_slug
        )
        return (item_dict, None)
    except ValidationError:
        return (None, "Nom invalide.")


@database_sync_to_async
def ws_add_item(list_id, name, quantity="", notes="", section_slug=None):
    return _do_add_item(list_id, name, quantity, notes, section_slug)


def _do_update_item(list_id, item_id, **kwargs):
    try:
        gl = GroceryList.objects.get(pk=list_id)
    except GroceryList.DoesNotExist:
        return None
    return item_svc.update_item(gl, item_id, **kwargs)


@database_sync_to_async
def ws_update_item(list_id, item_id, **kwargs):
    return _do_update_item(list_id, item_id, **kwargs)


@database_sync_to_async
def ws_delete_item(list_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    return Item.objects.filter(pk=item_id, grocery_list_id=list_id).delete()[0] > 0


def _do_reorder(list_id, section_order=None, item_orders=None):
    try:
        gl = GroceryList.objects.get(pk=list_id)
    except GroceryList.DoesNotExist:
        return None
    return item_svc.apply_reorder(
        gl, section_order=section_order, item_orders=item_orders
    )


@database_sync_to_async
def ws_reorder_items(list_id, section_order=None, item_orders=None):
    return _do_reorder(list_id, section_order=section_order, item_orders=item_orders)


def _is_token_valid(token_id):
    """Return True if token_id exists and is not revoked."""
    if not token_id:
        return False
    try:
        t = AccessToken.objects.get(pk=token_id)
        return not t.revoked
    except AccessToken.DoesNotExist:
        return False


@database_sync_to_async
def check_access_token(token_id):
    return _is_token_valid(token_id)


@database_sync_to_async
def get_token_id_from_scope(scope):
    """Read session in sync thread (session backend may do blocking I/O)."""
    session = scope.get("session")
    if session is None:
        return None
    try:
        return session.get(SESSION_ACCESS_TOKEN_ID_KEY)
    except Exception:
        return None


class ListConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_id = None
        self.room_name = None

    async def connect(self):
        from django.conf import settings

        if getattr(settings, "SECRET_URL_AUTH_REQUIRED", True):
            token_id = await get_token_id_from_scope(self.scope)
            if not await check_access_token(token_id):
                logger.warning("ws connect rejected: no valid secret URL token")
                await self.close(code=4401)
                return
        self.list_id = self.scope["url_route"]["kwargs"].get("list_id")
        if not self.list_id:
            logger.warning("ws connect rejected: missing list_id")
            await self.close(code=4000)
            return
        uid = parse_uuid(self.list_id)
        if uid is None:
            logger.warning("ws connect rejected: invalid list_id=%r", self.list_id)
            await self.close(code=4000)
            return
        exists = await get_list_exists(uid)
        if not exists:
            logger.warning(
                "ws connect rejected: list not found list_id=%s", self.list_id
            )
            await self.close(code=4004)
            return
        self.room_name = f"list_{self.list_id}"
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()
        logger.info("ws connected list_id=%s", self.list_id)

    async def disconnect(self, close_code):
        if self.room_name:
            await self.channel_layer.group_discard(self.room_name, self.channel_name)
        logger.debug("ws disconnected list_id=%s code=%s", self.list_id, close_code)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or self.list_id is None:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError as e:
            logger.warning("ws invalid JSON list_id=%s: %s", self.list_id, e)
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
            return
        action = data.get("action")
        if not action:
            logger.warning("ws missing action list_id=%s", self.list_id)
            await self.send(text_data=json.dumps({"error": "Missing action"}))
            return
        logger.debug("ws receive list_id=%s action=%s", self.list_id, action)
        uid = parse_uuid(self.list_id)
        if uid is None:
            return
        payload = None
        if action == "add_item":
            name = (data.get("name") or "").strip()
            if not name:
                await self.send(text_data=json.dumps({"error": "Missing name"}))
                return
            item, add_err = await ws_add_item(
                uid,
                name,
                data.get("quantity", ""),
                data.get("notes", ""),
                section_slug=data.get("section_slug"),
            )
            if add_err:
                await self.send(text_data=json.dumps({"error": add_err}))
                return
            if item:
                payload = {"action": "item_added", "item": item}
        elif action == "update_item":
            item_id = parse_uuid(data.get("item_id"))
            if not item_id:
                await self.send(text_data=json.dumps({"error": "Invalid item_id"}))
                return
            item = await ws_update_item(
                uid,
                item_id,
                name=data.get("name"),
                quantity=data.get("quantity"),
                notes=data.get("notes"),
                checked=data.get("checked"),
                position=data.get("position"),
            )
            if item:
                payload = {"action": "item_updated", "item": item}
        elif action == "delete_item":
            item_id = parse_uuid(data.get("item_id"))
            if not item_id:
                await self.send(text_data=json.dumps({"error": "Invalid item_id"}))
                return
            deleted = await ws_delete_item(uid, item_id)
            if deleted:
                payload = {"action": "item_deleted", "item_id": str(item_id)}
        elif action == "check_item":
            item_id = parse_uuid(data.get("item_id"))
            if not item_id:
                await self.send(text_data=json.dumps({"error": "Invalid item_id"}))
                return
            checked = data.get("checked", True)
            item = await ws_update_item(uid, item_id, checked=checked)
            if item:
                payload = {"action": "item_updated", "item": item}
        elif action == "reorder_items":
            item_orders = data.get("item_orders", [])
            if not isinstance(item_orders, list):
                await self.send(
                    text_data=json.dumps({"error": "item_orders must be list"})
                )
                return
            section_order = data.get("section_order")
            detail = await ws_reorder_items(
                uid, section_order=section_order, item_orders=item_orders
            )
            if detail:
                payload = {"action": "list_updated", "list": detail}
        else:
            logger.warning(
                "ws unknown action list_id=%s action=%r", self.list_id, action
            )
            await self.send(
                text_data=json.dumps({"error": f"Unknown action: {action}"})
            )
            return
        if payload:
            logger.debug("ws broadcast list_id=%s action=%s", self.list_id, action)
            await self.channel_layer.group_send(
                self.room_name,
                {"type": "broadcast_message", "payload": payload},
            )

    async def broadcast_message(self, event):
        """Send payload to this client (from group_send)."""
        await self.send(text_data=json.dumps(event["payload"]))
