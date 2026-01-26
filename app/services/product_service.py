from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.crud.product import CRUDProduct
from app.schemas.product import BatchCreate

class ProductService:

    def __init__(self, session: AsyncSession):
        self.product_crud = CRUDProduct(session)

    async def create_batch(self, product_id: UUID, batch_in: BatchCreate):
        """Pharmacist workflow: Adding a specific batch to a product"""
        batch = await self.product_crud.create_new_batch(
            product_id=product_id, 
            obj_in=batch_in
        )
        # Note: product_crud handles the commit internally based on your previous code
        return batch
    
    
    async def get_catalog(self, category: str = None, search: str = None, skip: int = 0, limit: int = 20,):
        """Fetch filtered storefront products."""
        return await self.product_crud.get_storefront(
            category=category, search=search, skip=skip, limit=limit
        )


