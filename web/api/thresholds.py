"""
Thresholds API Router

Endpoints for managing price alert thresholds (CRUD operations).
"""

from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database.connection import get_session
from database.models import Product, Threshold, User
from web.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class ThresholdCreate(BaseModel):
    """Schema for creating a threshold."""

    product_id: int = Field(..., description="Product database ID")
    target_price: Optional[float] = Field(None, description="Target price to alert on")
    percentage_drop: Optional[float] = Field(None, description="Percentage drop to alert on")
    enabled: bool = Field(True, description="Whether threshold is enabled")
    send_email: bool = Field(True, description="Send email alerts")
    send_slack: bool = Field(False, description="Send Slack alerts")


class ThresholdUpdate(BaseModel):
    """Schema for updating a threshold."""

    target_price: Optional[float] = None
    percentage_drop: Optional[float] = None
    enabled: Optional[bool] = None
    send_email: Optional[bool] = None
    send_slack: Optional[bool] = None


@router.get("/")
async def list_thresholds(current_user: User = Depends(get_current_user)):
    """List thresholds for the authenticated user."""
    with get_session() as session:
        query = session.query(Threshold).filter(Threshold.user_id == current_user.id)

        thresholds = query.all()

        return {
            "total": len(thresholds),
            "thresholds": [
                {
                    "id": t.id,
                    "product_id": t.product_id,
                    "product_name": t.product.name,
                    "product_code": t.product.product_id,
                    "target_price": t.target_price,
                    "percentage_drop": t.percentage_drop,
                    "enabled": t.enabled,
                    "send_email": t.send_email,
                    "send_slack": t.send_slack,
                    "created_at": t.created_at.isoformat(),
                }
                for t in thresholds
            ],
        }


@router.post("/")
async def create_threshold(
    threshold: ThresholdCreate,
    current_user: User = Depends(get_current_user),
):
    """Create a new threshold."""
    if threshold.target_price is None and threshold.percentage_drop is None:
        raise HTTPException(
            status_code=400,
            detail="Must specify at least one of target_price or percentage_drop",
        )

    with get_session() as session:
        product_query = session.query(Product).filter_by(
            id=threshold.product_id,
            user_id=current_user.id,
        )

        product = product_query.first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        new_threshold = Threshold(
            user_id=current_user.id,
            product_id=threshold.product_id,
            target_price=threshold.target_price,
            percentage_drop=threshold.percentage_drop,
            enabled=threshold.enabled,
            send_email=threshold.send_email,
            send_slack=threshold.send_slack,
        )

        session.add(new_threshold)
        session.commit()
        session.refresh(new_threshold)

        logger.info("Created threshold for product %s", product.name)

        return {
            "id": new_threshold.id,
            "product_id": new_threshold.product_id,
            "product_name": product.name,
            "target_price": new_threshold.target_price,
            "percentage_drop": new_threshold.percentage_drop,
            "enabled": new_threshold.enabled,
            "send_email": new_threshold.send_email,
            "send_slack": new_threshold.send_slack,
            "created_at": new_threshold.created_at.isoformat(),
        }


@router.get("/{threshold_id}")
async def get_threshold(
    threshold_id: int,
    current_user: User = Depends(get_current_user),
):
    """Get a specific threshold."""
    with get_session() as session:
        query = session.query(Threshold).filter_by(id=threshold_id, user_id=current_user.id)

        threshold = query.first()
        if not threshold:
            raise HTTPException(status_code=404, detail="Threshold not found")

        return {
            "id": threshold.id,
            "product_id": threshold.product_id,
            "product_name": threshold.product.name,
            "product_code": threshold.product.product_id,
            "target_price": threshold.target_price,
            "percentage_drop": threshold.percentage_drop,
            "enabled": threshold.enabled,
            "send_email": threshold.send_email,
            "send_slack": threshold.send_slack,
            "created_at": threshold.created_at.isoformat(),
        }


@router.put("/{threshold_id}")
async def update_threshold(
    threshold_id: int,
    threshold_update: ThresholdUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update a threshold."""
    with get_session() as session:
        query = session.query(Threshold).filter_by(id=threshold_id, user_id=current_user.id)

        threshold = query.first()
        if not threshold:
            raise HTTPException(status_code=404, detail="Threshold not found")

        if threshold_update.target_price is not None:
            threshold.target_price = threshold_update.target_price
        if threshold_update.percentage_drop is not None:
            threshold.percentage_drop = threshold_update.percentage_drop
        if threshold_update.enabled is not None:
            threshold.enabled = threshold_update.enabled
        if threshold_update.send_email is not None:
            threshold.send_email = threshold_update.send_email
        if threshold_update.send_slack is not None:
            threshold.send_slack = threshold_update.send_slack

        session.commit()
        session.refresh(threshold)

        logger.info("Updated threshold %s", threshold_id)

        return {
            "id": threshold.id,
            "product_id": threshold.product_id,
            "product_name": threshold.product.name,
            "target_price": threshold.target_price,
            "percentage_drop": threshold.percentage_drop,
            "enabled": threshold.enabled,
            "send_email": threshold.send_email,
            "send_slack": threshold.send_slack,
            "updated_at": datetime.utcnow().isoformat(),
        }


@router.delete("/{threshold_id}")
async def delete_threshold(
    threshold_id: int,
    current_user: User = Depends(get_current_user),
):
    """Delete a threshold."""
    with get_session() as session:
        query = session.query(Threshold).filter_by(id=threshold_id, user_id=current_user.id)

        threshold = query.first()
        if not threshold:
            raise HTTPException(status_code=404, detail="Threshold not found")

        product_name = threshold.product.name
        session.delete(threshold)
        session.commit()

        logger.info("Deleted threshold %s for product %s", threshold_id, product_name)

        return {
            "status": "deleted",
            "id": threshold_id,
            "message": f"Threshold deleted for {product_name}",
        }


@router.get("/product/{product_id}")
async def get_product_thresholds(
    product_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get all thresholds for a specific product code."""
    with get_session() as session:
        product_query = session.query(Product).filter_by(
            product_id=product_id,
            user_id=current_user.id,
        )

        product = product_query.first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        thresholds_query = session.query(Threshold).filter_by(
            product_id=product.id,
            user_id=current_user.id,
        )

        threshold_items = thresholds_query.all()

        return {
            "product_id": product_id,
            "product_name": product.name,
            "total": len(threshold_items),
            "thresholds": [
                {
                    "id": t.id,
                    "target_price": t.target_price,
                    "percentage_drop": t.percentage_drop,
                    "enabled": t.enabled,
                    "send_email": t.send_email,
                    "send_slack": t.send_slack,
                    "created_at": t.created_at.isoformat(),
                }
                for t in threshold_items
            ],
        }
