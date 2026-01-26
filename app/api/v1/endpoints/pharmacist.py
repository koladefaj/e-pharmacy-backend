import logging
from fastapi import Depends, APIRouter
from app.models.user import User
from uuid import UUID
from app.services.product_service import ProductService
from app.schemas.product import BatchCreate
from app.core.deps import get_current_active_pharmacist, get_service


logger = logging.getLogger(__name__)

router = APIRouter( prefix="/pharmacist", tags=["Pharmacist"])




@router.post("/{product_id}/batches", status_code=201)
async def add_inventory_batch(
    product_id: UUID,
    body: BatchCreate,
    service: ProductService = Depends(get_service(ProductService)),
    current_user: User = Depends(get_current_active_pharmacist),
):
    """Pharmacist: Add new stock batch to a product."""
    batch = await service.create_batch(product_id=product_id, batch_in=body)
    
    return {
        "status": "success",
        "message": f"Batch {batch.batch_number} added successfully.",
        "data": {
            "batch_id": batch.id, 
            "current_stock": batch.current_quantity
        }
    }

