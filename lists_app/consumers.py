import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import GroceryList, Item, Section

class ListConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.list_id = self.scope['url_route']['kwargs']['list_id']
        self.group_name = f"grocery_list_{self.list_id}"
        # Accept the connection
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Send initial data
        items = await sync_to_async(list)(Item.objects.filter(grocery_list_id=self.list_id).order_by('id'))
        items_data = await sync_to_async(list)([item.to_dict() for item in items])
        await self.send_json({"action": "initial", "items": items_data})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        # Expect content: {action: "add"|"update"|"toggle"|"delete", item: {...}}
        action = content.get("action")
        item_data = content.get("item", {})
        print(action, item_data)
        if action == "add":
            name = item_data.get("name", "").strip()
            if not name:
                return
            section = item_data.get("section", None)
            if section:
                section_id = section.get("id", None)
                section = await sync_to_async(Section.objects.filter(id=section_id).first)()
            item = await sync_to_async(Item.objects.create)(grocery_list_id=self.list_id, name=name, section=section)
            data = item.to_dict()
            await self.channel_layer.group_send(self.group_name, {"type": "broadcast", "message": {"action":"added","item":data}})
        elif action == "update":
            item_id = item_data.get("id")
            if not item_id:
                return
            item = await sync_to_async(Item.objects.filter(id=item_id, grocery_list_id=self.list_id).first)()
            if not item:
                return
            item.name = item_data.get("name", item.name)
            section = item_data.get("section", None)
            if section:
                section_id = section.get("id", None)
                section = await sync_to_async(Section.objects.filter(id=section_id).first)()
            item.section = section
            await sync_to_async(item.save)()
            await self.channel_layer.group_send(self.group_name, {"type": "broadcast", "message": {"action":"updated","item": item.to_dict()}})
        elif action == "toggle":
            item_id = item_data.get("id")
            if not item_id:
                return
            item = await sync_to_async(Item.objects.filter(id=item_id, grocery_list_id=self.list_id).first)()
            if not item:
                return
            item.checked = bool(item_data.get("checked", not item.checked))
            await sync_to_async(item.save)()
            await self.channel_layer.group_send(self.group_name, {"type": "broadcast", "message": {"action":"updated","item": item.to_dict()}})
        elif action == "delete":
            item_id = item_data.get("id")
            if not item_id:
                return
            item = await sync_to_async(Item.objects.filter(id=item_id, grocery_list_id=self.list_id).first)()
            if not item:
                return
            await sync_to_async(item.delete)()
            await self.channel_layer.group_send(self.group_name, {"type": "broadcast", "message": {"action":"deleted","item_id": item_id}})
        else:
            # unknown action - ignore or send error
            await self.send_json({"action":"error","message":"unknown action"})

    async def broadcast(self, event):
        message = event["message"]
        await self.send_json(message)
