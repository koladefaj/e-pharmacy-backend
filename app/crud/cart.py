import json
from uuid import UUID
from typing import List, Dict

from redis.asyncio import Redis
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import CartItem


class CartCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _key(self, user_id: UUID) -> str:
        return f"cart:{user_id}"

    # -----------------------
    # REDIS OPERATIONS
    # -----------------------
    async def get_redis_items(self, redis: Redis, user_id: UUID) -> List[Dict]:
        data = await redis.get(self._key(user_id))
        if not data:
            return []

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            await redis.delete(self._key(user_id))
            return []

    async def set_redis_items(
        self,
        redis: Redis,
        user_id: UUID,
        items: List[Dict],
        ttl: int,
    ):
        await redis.set(self._key(user_id), json.dumps(items), ex=ttl)

    async def delete_redis_cart(self, redis: Redis, user_id: UUID):
        await redis.delete(self._key(user_id))

    # -----------------------
    # DATABASE OPERATIONS
    # -----------------------
    async def get_db_items(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> List[CartItem]:
        result = await session.execute(
            select(CartItem).where(CartItem.user_id == user_id)
        )
        return result.scalars().all()

    async def clear_db_cart(
        self,
        session: AsyncSession,
        user_id: UUID,
    ):
        await session.execute(
            delete(CartItem).where(CartItem.user_id == user_id)
        )
        