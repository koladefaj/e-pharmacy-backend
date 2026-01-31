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

    def __init__(self, session: AsyncSession):
        self.session = session

    def _generate_slug(self, name: str) -> str:
        # Simple slugifier: Lowercase, replace spaces/special chars with hyphens
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    async def get(self, id: UUID) -> Product | None:
        """Fetch a product by ID."""
        return await self.session.get(Product, id)

    async def create_new_product(self, *, obj_in: ProductCreate):
        """Create a new Product record."""

        data = obj_in.model_dump()
        data["slug"] = self._generate_slug(data["name"])

        db_obj = Product(**data)
        self.session.add(db_obj)

        try:
            await self.session.commit()

        except IntegrityError as e:
            await self.session.rollback()
            # Check if the error is specifically about the slug/unique constraint
            if (
                "ix_products_slug" in str(e.orig)
                or "unique constraint" in str(e.orig).lower()
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A product with the name '{obj_in.name}' (slug: {data['slug']}) already exists.",
                )
            raise e  # Re-raise if it's a different integrity issue

        await self.session.refresh(db_obj)
        return db_obj

    async def get_multi_product(
        self, *, skip: int = 0, limit: int = 20, active: bool | None
    ) -> list[Product]:
        """Fetch all active products and their associated inventory batches."""
        stmt = (
            select(Product)
            .options(selectinload(Product.batches))  # 👈 This is the magic line
            .where(Product.is_active == active)
            .offset(skip)
            .limit(limit)
            .order_by(Product.name.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_multi_product_admin(
        self,
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

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_new_batch(
        self, *, product_id: UUID, obj_in: BatchCreate
    ) -> InventoryBatch:
        """Create a new batch record with business logic."""
        # Mix the validated data with system-required fields
        existing = await self.session.execute(
            select(InventoryBatch).where(
                InventoryBatch.batch_number == obj_in.batch_number
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="This batch number is already assigned to a product.",
            )

        # Inside create_new_batch...
        product = await self.session.get(Product, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        if not product.is_active:
            product.is_active = True  # Auto-enable because new stock arrived

        data = obj_in.model_dump()
        data["product_id"] = product_id
        data["current_quantity"] = obj_in.initial_quantity  # Crucial for new batches

        db_obj = InventoryBatch(**data)
        self.session.add(db_obj)

        try:
            await self.session.commit()
            await self.session.refresh(db_obj)

            return db_obj

        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Batch violates a database constraint",
            )

    async def delete_batch_by_number(self, batch_number: str) -> bool:

        stmt = select(InventoryBatch).where(InventoryBatch.batch_number == batch_number)
        result = await self.session.execute(stmt)
        batch = result.scalar_one_or_none()

        if batch:
            await self.session.delete(batch)
            await self.session.commit()
            return True
        return False

    async def deduct_stock_fefo(self, *, product_id: UUID, quantity: int):
        """
        Deduct stock using First-Expired-First-Out (FEFO) logic.
        Ensures we don't sell blocked or expired items.
        """
        # Fetch all available, non-blocked, unexpired batches sorted by expiry
        stmt = (
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.is_blocked == False,
                InventoryBatch.expiry_date > datetime.now(timezone.utc),
                InventoryBatch.current_quantity > 0,
            )
            .order_by(InventoryBatch.expiry_date.asc())
        )

        result = await self.session.execute(stmt)
        batches = result.scalars().all()

        total_available = sum(b.current_quantity for b in batches)
        if total_available < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Requested: {quantity}, Available: {total_available}",
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

        await self.session.commit()
        return True

    async def restock_product(
        self,
        *,
        product_id: UUID,
        quantity: int,
    ):
        """
        Restock product by adding quantity back to the MOST RECENT batches.
        (LIFO is acceptable for refunds in pharmacies.)
        """

        stmt = (
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.is_blocked == False,
            )
            .order_by(InventoryBatch.expiry_date.desc())
        )

        result = await self.session.execute(stmt)
        batches = result.scalars().all()

        remaining = quantity

        for batch in batches:
            if remaining <= 0:
                break

            batch.current_quantity += remaining
            remaining = 0

        await self.session.commit()

    # In your CRUD or a Service layer
    async def get_available_products(
        self,
    ):
        stmt = (
            select(Product)
            .join(Product.batches)
            .where(
                Product.is_active == True,
                InventoryBatch.current_quantity > 0,
                InventoryBatch.expiry_date > datetime.now(timezone.utc),
                InventoryBatch.is_blocked == False,
            )
            .distinct()
        )

        result = await self.session.execute(stmt)

        return result.scalars().all()
        # This only returns drugs that actually have "Sellable" stock

    async def get_storefront(
        self,
        *,
        category: str = None,
        search: str = None,
        skip: int = 0,
        limit: int = 20,
    ):
        # Initialize stmt immediately so it's never "unbound"
        stmt = select(Product).options(selectinload(Product.batches))

        # Apply filters
        stmt = stmt.where(Product.is_active == True)

        if category:
            stmt = stmt.where(Product.category == category)

        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search}%"))

        # Apply pagination and ordering
        stmt = stmt.offset(skip).limit(limit).order_by(Product.name.asc())

        # Execute
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def delete_batch_by_number(self, batch_number: str) -> bool:
        """Removes a batch from the database by its unique batch number."""
        stmt = select(InventoryBatch).where(InventoryBatch.batch_number == batch_number)
        result = await self.session.execute(stmt)
        batch = result.scalar_one_or_none()

        if batch:
            await self.session.delete(batch)
            await self.session.commit()
            return True
        return False
