from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from uuid import UUID
from fastapi import Depends, HTTPException
from app.db.sessions import get_async_session
from app.crud.product import product_crud
from app.schemas.product import ProductCreate, BatchCreate

class ProductService:
    def __init__(self, db: AsyncSession = Depends(get_async_session)):
        self.db = db

    async def create_batch(self, product_id: UUID, batch_in: BatchCreate):
        """Pharmacist workflow: Adding a specific batch to a product"""
        batch = await product_crud.create_new_batch(
            self.db, 
            product_id=product_id, 
            obj_in=batch_in
        )
        # Note: product_crud handles the commit internally based on your previous code
        return batch
    
    
    async def get_catalog(self, category: str = None, search: str = None, skip: int = 0, limit: int = 20):
        """Fetch filtered storefront products."""
        return await product_crud.get_storefront(
            self.db, category=category, search=search, skip=skip, limit=limit
        )