import json
from typing import Dict, List
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import CartItem


class CartCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _key(self, user_id: UUID) -> str:
        return f"cart:{user_id}"

    # REDIS OPERATIONS
    async def get_redis_items(self, redis: Redis, user_id: UUID) -> List[Dict]:

        data = await redis.get(self._key(user_id))

        if not data:
            return []

        if isinstance(data, bytes):
            data = data.decode("utf-8")

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            await redis.delete(self._key(user_id))
            return []

        if isinstance(payload, dict):
            items = payload.get("items", [])

        elif isinstance(payload, list):  # backward compatibility
            items = payload

        else:
            await redis.delete(self._key(user_id))
            return []

        if not isinstance(items, list):
            await redis.delete(self._key(user_id))
            return []

        return items

    async def set_redis_items(
        self,
        redis: Redis,
        user_id: UUID,
        items: List[Dict],
        ttl: int,
    ):
        payload = {
            "v": 1,
            "items": items,
        }

        await redis.set(self._key(user_id), json.dumps(payload), ex=ttl)

    async def delete_redis_cart(self, redis: Redis, user_id: UUID):
        await redis.delete(self._key(user_id))

    # DATABASE OPERATIONS
    async def get_db_items(
        self,
        user_id: UUID,
    ) -> List[CartItem]:
        result = await self.session.execute(
            select(CartItem).where(CartItem.user_id == user_id)
        )
        return result.scalars().all()

    async def clear_db_cart(
        self,
        user_id: UUID,
    ):
        await self.session.execute(delete(CartItem).where(CartItem.user_id == user_id))
