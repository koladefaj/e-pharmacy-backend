from app.models.product import Product
from app.schemas.product import ProductCreate, BatchCreate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models.inventory import InventoryBatch
from sqlalchemy.orm.attributes import set_committed_value
from datetime import datetime, timezone
from starlette import status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
import re
from uuid import UUID

class CRUDProduct:

    def _generate_slug(self, name: str) -> str:
        # Simple slugifier: Lowercase, replace spaces/special chars with hyphens
        return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

    async def create_new_product(
        self,
        db: AsyncSession,
        *,
        obj_in: ProductCreate
    ):
        """Create a new Product record."""

        data = obj_in.model_dump()
        data["slug"] = self._generate_slug(data["name"])

        db_obj = Product(**data)
        db.add(db_obj)

        try:
            await db.commit()

        except IntegrityError as e:
            await db.rollback()
            # Check if the error is specifically about the slug/unique constraint
            if "ix_products_slug" in str(e.orig) or "unique constraint" in str(e.orig).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A product with the name '{obj_in.name}' (slug: {data['slug']}) already exists."
                )
            raise e # Re-raise if it's a different integrity issue
        
        await db.refresh(db_obj)        
        return db_obj

    async def get_multi_product(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 20, active: bool | None
    ) -> list[Product]:
        """Fetch all active products and their associated inventory batches."""
        stmt = (
            select(Product)
            .options(selectinload(Product.batches)) # 👈 This is the magic line
            .where(Product.is_active == active)
            .offset(skip)
            .limit(limit)
            .order_by(Product.name.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_multi_product_admin(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Product]:
        """Fetch ALL products (active + inactive) with their batches."""
        stmt = (
            select(Product)
            .options(selectinload(Product.batches))
            .order_by(Product.name.asc())
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(stmt)
        return result.scalars().all()
    

        
    async def create_new_batch(
        self,
        db: AsyncSession,
        *,
        product_id: UUID,
        obj_in: BatchCreate
    ) -> InventoryBatch:
        """Create a new batch record with business logic."""
        # Mix the validated data with system-required fields
        existing = await db.execute(
        select(InventoryBatch).where(InventoryBatch.batch_number == obj_in.batch_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
            status_code=400, 
            detail="This batch number is already assigned to a product."
        )

        # Inside create_new_batch...
        product = await db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
                
        if not product.is_active:
            product.is_active = True # Auto-enable because new stock arrived

        
        data = obj_in.model_dump()
        data["product_id"] = product_id
        data["current_quantity"] = obj_in.initial_quantity # Crucial for new batches
            
        db_obj = InventoryBatch(**data)
        db.add(db_obj)

        try:
            await db.commit()
            await db.refresh(db_obj)
            
            return db_obj

        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Batch violates a database constraint"
            )
    
    async def delete_batch_by_number(self, db: AsyncSession, batch_number: str) -> bool:
    
        stmt = select(InventoryBatch).where(InventoryBatch.batch_number == batch_number)
        result = await db.execute(stmt)
        batch = result.scalar_one_or_none()

        if batch:
            await db.delete(batch)
            await db.commit()
            return True
        return False
    
    async def deduct_stock_fefo(
        self, db: AsyncSession, *, product_id: UUID, quantity: int
    ):
        """
        Deduct stock using First-Expired-First-Out (FEFO) logic.
        Ensures we don't sell blocked or expired items.
        """
        # 1. Fetch all available, non-blocked, unexpired batches sorted by expiry
        stmt = (
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.is_blocked == False,
                InventoryBatch.expiry_date > datetime.now(timezone.utc),
                InventoryBatch.current_quantity > 0
            )
            .order_by(InventoryBatch.expiry_date.asc())
        )
        
        result = await db.execute(stmt)
        batches = result.scalars().all()
        
        total_available = sum(b.current_quantity for b in batches)
        if total_available < quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock. Requested: {quantity}, Available: {total_available}"
            )

        remaining_to_deduct = quantity
        
        for batch in batches:
            if remaining_to_deduct <= 0:
                break
                
            if batch.current_quantity >= remaining_to_deduct:
                # This batch can cover the rest of the order
                batch.current_quantity -= remaining_to_deduct
                remaining_to_deduct = 0
            else:
                # Empty this batch and move to the next
                remaining_to_deduct -= batch.current_quantity
                batch.current_quantity = 0
                
        await db.commit()
        return True
    
    # In your CRUD or a Service layer
    async def get_available_products(self, db: AsyncSession):
        stmt = (
            select(Product)
            .join(Product.batches)
            .where(
                Product.is_active == True,
                InventoryBatch.current_quantity > 0,
                InventoryBatch.expiry_date > datetime.now(timezone.utc),
                InventoryBatch.is_blocked == False
            )
            .distinct()
        )

        return stmt
        # This only returns drugs that actually have "Sellable" stock

    async def get_storefront(
        self, 
        db: AsyncSession, 
        *, 
        category: str = None, 
        search: str = None, 
        skip: int = 0, 
        limit: int = 20
    ):
        # 1. Initialize stmt immediately so it's never "unbound"
        stmt = select(Product).options(selectinload(Product.batches))
        
        # 2. Apply filters
        stmt = stmt.where(Product.is_active == True)
        
        if category:
            stmt = stmt.where(Product.category == category)
        
        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search}%"))
            
        # 3. Apply pagination and ordering
        stmt = stmt.offset(skip).limit(limit).order_by(Product.name.asc())
        
        # 4. Execute
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def delete_batch_by_number(self, db: AsyncSession, batch_number: str) -> bool:
        """Removes a batch from the database by its unique batch number."""
        stmt = select(InventoryBatch).where(InventoryBatch.batch_number == batch_number)
        result = await db.execute(stmt)
        batch = result.scalar_one_or_none()

        if batch:
            await db.delete(batch)
            await db.commit()
            return True
        return False

product_crud = CRUDProduct()