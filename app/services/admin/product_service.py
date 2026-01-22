from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from uuid import UUID
from fastapi import Depends, HTTPException
from app.db.sessions import get_async_session
from app.crud.product import product_crud
from app.schemas.product import ProductCreate

class AdminProductService:
    def __init__(self, db: AsyncSession = Depends(get_async_session)):
        self.db = db

    async def create_product(self, product_in: ProductCreate):
        """Pure product creation (Metadata only)"""
        product = await product_crud.create_new_product(self.db, obj_in=product_in)
        # We don't commit here if we want the caller to decide, 
        # but usually for standalone creation, we do:
        await self.db.commit()
        await self.db.refresh(product)
        return product

    
    async def get_admin_catalog(self, skip: int = 0, limit: int = 20):
        """
        Fetches full product list including inactive items.
        Returns a list of products (The service shouldn't wrap in {"products": ...})
        """
        return await product_crud.get_multi_product_admin(
            self.db, 
            skip=skip, 
            limit=limit
        )
    
    async def toggle_active_status(self, product_id: UUID):
        """Business logic to flip a product's active status."""
        product = await self.db.get(Product, product_id)
        if not product:
            # This will be caught by your global handler in main.py
            raise HTTPException(status_code=404, detail="Product not found")

        product.is_active = not product.is_active
        await self.db.commit()
        await self.db.refresh(product)
        
        status_text = "enabled" if product.is_active else "disabled"
        return {"message": f"Product {product.name} is now {status_text}."}
    
    async def remove_inventory_batch(self, batch_number: str, admin_email: str):
        """Service logic to remove a batch and log the administrator responsible."""
        success = await product_crud.delete_batch_by_number(self.db, batch_number)
        
        if not success:
            raise HTTPException(
                status_code=404, 
                detail=f"Inventory batch '{batch_number}' not found."
            )
        
        return True
