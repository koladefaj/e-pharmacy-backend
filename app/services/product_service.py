import logging
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.crud.product import CRUDProduct
from app.schemas.product import BatchCreate
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class ProductService:

    def __init__(self, session: AsyncSession):
        self.product_crud = CRUDProduct(session)
        self.session = session

    async def create_batch(self, product_id: UUID, batch_in: BatchCreate):
        """Pharmacist workflow: Adding a specific batch to a product"""

        # Verify product exists to avoid IntegrityErrors
        product = await self.product_crud.get(id=product_id)
        if not product:
            logger.warning(f"Batch creation failed: Product {product_id} not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Product not found"
            )

        # Create the batch
        try:
            batch = await self.product_crud.create_new_batch(
                product_id=product_id, 
                obj_in=batch_in
            )

            logger.info(
                f"Inventory Added: Product {product_id} | "
                f"Batch {batch_in.batch_number} | "
                f"Qty {batch_in.initial_quantity}"
            )
            return batch
        except Exception as e:
            logger.error(f"Failed to create batch for product {product_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not register new inventory batch."
            )
    
    
    async def get_catalog(self, category: str = None, search: str = None, skip: int = 0, limit: int = 20,):
        """Fetch filtered storefront products."""
        return await self.product_crud.get_storefront(
            category=category, search=search, skip=skip, limit=limit
        )


