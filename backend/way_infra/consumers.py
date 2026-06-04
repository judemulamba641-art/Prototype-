"""WAY WebSocket Consumers"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncWebsocketConsumer):
    """Real-time notifications for users."""
    async def connect(self):
        self.user_id = self.scope.get("user_id")
        if not self.user_id:
            await self.close()
            return
        self.group_name = f"user_{self.user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.send(text_data=json.dumps({"echo": data}))

    async def notification(self, event):
        await self.send(text_data=json.dumps({
            "type": event["notification_type"],
            "payload": event["payload"],
            "timestamp": event.get("timestamp"),
        }))


class WalletUpdateConsumer(AsyncWebsocketConsumer):
    """Real-time wallet balance updates."""
    async def connect(self):
        self.user_id = self.scope.get("user_id")
        if not self.user_id:
            await self.close()
            return
        self.group_name = f"wallet_{self.user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def wallet_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "wallet_update",
            "balance": event["balance"],
            "available": event["available"],
            "timestamp": event.get("timestamp"),
        }))
