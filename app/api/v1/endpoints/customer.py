import logging
from fastapi import Depends, HTTPException, APIRouter
from typing import List, Optional
from app.schemas.product import ProductWithBatches
from app.services.product_service import ProductService
from app.models.user import User
from starlette import status
from app.services.user_service import UserService
from app.core.deps import get_current_customer, get_service


logger = logging.getLogger(__name__)

router = APIRouter( prefix="/customer", tags=["Customers"])


@router.get("/store", response_model=List[ProductWithBatches])
async def storefront_list(
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    service: ProductService = Depends(get_service(ProductService)),
):
    """Public Storefront: Shows only active products with stock."""
    # Validation stays in the router (it's an HTTP concern)
    valid_categories = ["otc", "supplement", "prescription", "medical_device"]
    if category and category not in valid_categories:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )

    # All DB logic and potential 500 errors handled by Service/Global Handler
    return await service.get_catalog(
            category=category, search=search, skip=skip, limit=limit
    )

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: User = Depends(get_current_customer), # Dependency that gets the logged-in user
    service: UserService = Depends(get_service(UserService))
):
    """
    Deactivates the currently authenticated user's account.
    """
    await service.delete_user_account(current_user.id)
    return "Account Successfully Deleted"

