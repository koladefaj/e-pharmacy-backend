import logging
from fastapi import Depends, APIRouter, Request, status
from starlette import status
from app.models.user import User
from typing import List
from app.core.deps import get_current_admin, get_service
from uuid import UUID
from app.services.admin.product_service import AdminProductService
from app.schemas.product import ProductWithBatches, ProductCreate, ProductRead


from app.schemas.product import (
    ProductRead,
    ProductCreate
)


# Initialize logger for security and audit events
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/product", tags=["Admin"])


@router.post("/create", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_new_product(
    body: ProductCreate,
    service: AdminProductService = Depends(get_service(AdminProductService)), # Service handles DB session
    current_admin: User = Depends(get_current_admin)
):
    """Admin only: Add a new drug definition to the Catalog."""
    # Logic is now inside the service
    return await service.create_product(body)

@router.get("/all", response_model=List[ProductWithBatches])
async def list_products_admin(
    skip: int = 0,
    limit: int = 20,
    service: AdminProductService = Depends(get_service(AdminProductService)),
    current_admin: User = Depends(get_current_admin)
):
    """
    Admin only: Get all products (active + inactive) for management.
    """
    # We return the list directly; if you want the {"products": []} wrapper, 
    # adjust your response_model or the return statement here.
    return await service.get_admin_catalog(skip=skip, limit=limit)

# Example of a mixed route (Admin)
@router.patch("/{product_id}/toggle-active")
async def toggle_product_active(
    product_id: UUID,
    service: AdminProductService = Depends(get_service(AdminProductService)),
    current_user: User = Depends(get_current_admin)
):

    return await service.toggle_active_status(product_id)

@router.delete("/inventory/batches/{batch_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_number: str,
    service: AdminProductService = Depends(get_service(AdminProductService)),
    current_admin: User = Depends(get_current_admin)
):
    """Admin only: Permanently remove an inventory batch."""
    await service.remove_inventory_batch(
        batch_number=batch_number, 
        admin_email=current_admin.email
    )

    logger.warning(f"AUDIT: Batch {batch_number} deleted by Admin: {current_admin.email}")
