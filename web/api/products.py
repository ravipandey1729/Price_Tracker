"""
Products API Router

Endpoints for managing products and viewing price history.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy import desc
from pydantic import BaseModel
import uuid

from database.connection import get_session
from database.models import Product, Price, Threshold, User
from web.auth import get_current_user
from web.services.product_search import search_products

router = APIRouter()


# Pydantic models for request validation
class ProductURL(BaseModel):
    Amazon: Optional[str] = None
    eBay: Optional[str] = None
    Walmart: Optional[str] = None


class AlertThreshold(BaseModel):
    percentage_drop: Optional[int] = None
    target_price: Optional[float] = None


class ProductCreate(BaseModel):
    name: str
    category: str
    sku: str
    urls: Dict[str, str]
    alert_threshold: Optional[AlertThreshold] = None


class SearchRequest(BaseModel):
    query: str
    sites: Optional[list[str]] = None
    max_results_per_site: int = 5


class TrackFromSearchRequest(BaseModel):
    name: str
    category: Optional[str] = "Search"
    sku: Optional[str] = ""
    urls: Dict[str, str]
    target_price: Optional[float] = None
    percentage_drop: Optional[float] = None


@router.get("/")
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """List all products with optional search"""
    with get_session() as session:
        query = session.query(Product)

        query = query.filter(Product.user_id == current_user.id)
        
        if search:
            query = query.filter(
                (Product.name.ilike(f"%{search}%")) |
                (Product.product_id.ilike(f"%{search}%")) |
                (Product.sku.ilike(f"%{search}%"))
            )
        
        products = query.offset(skip).limit(limit).all()
        
        return {
            "total": query.count(),
            "products": [
                {
                    "id": p.id,
                    "product_id": p.product_id,
                    "name": p.name,
                    "sku": p.sku,
                    "category": p.category,
                    "created_at": p.created_at.isoformat(),
                    "price_count": len(p.prices),
                    "threshold_count": len(p.thresholds),
                    "alert_count": len(p.alerts)
                }
                for p in products
            ]
        }


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get product details with latest price"""
    with get_session() as session:
        query = session.query(Product).filter_by(product_id=product_id)
        query = query.filter(Product.user_id == current_user.id)
        product = query.first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get latest price
        latest_price = (
            session.query(Price)
            .filter_by(product_id=product.id)
            .order_by(desc(Price.scraped_at))
            .first()
        )
        
        return {
            "id": product.id,
            "product_id": product.product_id,
            "name": product.name,
            "sku": product.sku,
            "category": product.category,
            "created_at": product.created_at.isoformat(),
            "latest_price": {
                "price": latest_price.price,
                "currency": latest_price.currency,
                "source_site": latest_price.source_site,
                "scraped_at": latest_price.scraped_at.isoformat()
            } if latest_price else None
        }


@router.get("/{product_id}/history")
async def get_price_history(
    product_id: str,
    days: int = Query(30, ge=1, le=365),
    site: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get price history for a product"""
    with get_session() as session:
        query = session.query(Product).filter_by(product_id=product_id)
        query = query.filter(Product.user_id == current_user.id)
        product = query.first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Query prices
        query = (
            session.query(Price)
            .filter(
                Price.product_id == product.id,
                Price.scraped_at >= start_date,
                Price.scraped_at <= end_date
            )
        )
        
        if site:
            query = query.filter(Price.source_site == site)
        
        prices = query.order_by(Price.scraped_at).all()
        
        if not prices:
            return {
                "product_id": product_id,
                "product_name": product.name,
                "dates": [],
                "prices": [],
                "currency": "USD",
                "current": 0,
                "avg": 0,
                "min": 0,
                "max": 0
            }
        
        # Extract data for chart
        dates = [p.scraped_at.strftime('%m/%d %H:%M') for p in prices]
        price_values = [p.price for p in prices]
        currency = prices[0].currency
        
        # Calculate statistics
        current_price = prices[-1].price
        avg_price = sum(price_values) / len(price_values)
        min_price = min(price_values)
        max_price = max(price_values)
        
        return {
            "product_id": product_id,
            "product_name": product.name,
            "dates": dates,
            "prices": price_values,
            "currency": currency,
            "current": current_price,
            "avg": avg_price,
            "min": min_price,
            "max": max_price
        }


@router.get("/{product_id}/statistics")
async def get_product_statistics(
    product_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get detailed statistics for a product"""
    with get_session() as session:
        query = session.query(Product).filter_by(product_id=product_id)
        query = query.filter(Product.user_id == current_user.id)
        product = query.first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get all prices
        prices = session.query(Price).filter_by(product_id=product.id).all()
        
        if not prices:
            return {
                "product_id": product_id,
                "total_prices": 0,
                "statistics": {}
            }
        
        # Group by site
        prices_by_site = {}
        for price in prices:
            if price.source_site not in prices_by_site:
                prices_by_site[price.source_site] = []
            prices_by_site[price.source_site].append(price.price)
        
        # Calculate stats per site
        site_stats = {}
        for site, price_list in prices_by_site.items():
            site_stats[site] = {
                "count": len(price_list),
                "current": price_list[-1],
                "average": sum(price_list) / len(price_list),
                "min": min(price_list),
                "max": max(price_list),
                "currency": prices[0].currency
            }
        
        return {
            "product_id": product_id,
            "product_name": product.name,
            "total_prices": len(prices),
            "sites": list(prices_by_site.keys()),
            "statistics": site_stats
        }


@router.post("/add")
async def add_product(
    product_data: ProductCreate,
    current_user: User = Depends(get_current_user),
):
    """Add a new product to track"""
    with get_session() as session:
        # Generate unique product ID
        product_id = f"prod_{uuid.uuid4().hex[:8]}"
        
        # Check if product with similar name already exists
        existing_query = session.query(Product).filter(
            Product.name.ilike(f"%{product_data.name}%")
        )
        existing_query = existing_query.filter(Product.user_id == current_user.id)
        existing = existing_query.first()
        
        if existing:
            return {
                "success": False,
                "message": "A product with similar name already exists",
                "existing_product_id": existing.product_id
            }
        
        # Create new product
        new_product = Product(
            user_id=current_user.id,
            product_id=product_id,
            name=product_data.name,
            category=product_data.category,
            sku=product_data.sku,
            amazon_url=product_data.urls.get("Amazon"),
            ebay_url=product_data.urls.get("eBay"),
            walmart_url=product_data.urls.get("Walmart")
        )
        
        session.add(new_product)
        session.flush()  # Get the ID
        
        # Add thresholds if provided
        if product_data.alert_threshold:
            if product_data.alert_threshold.percentage_drop:
                threshold = Threshold(
                    user_id=current_user.id,
                    product_id=new_product.id,
                    percentage_drop=product_data.alert_threshold.percentage_drop,
                    enabled=True,
                )
                session.add(threshold)
            
            if product_data.alert_threshold.target_price:
                threshold = Threshold(
                    user_id=current_user.id,
                    product_id=new_product.id,
                    target_price=product_data.alert_threshold.target_price,
                    enabled=True,
                )
                session.add(threshold)
        
        session.commit()
        
        return {
            "success": True,
            "message": "Product added successfully",
            "product_id": product_id,
            "product": {
                "id": new_product.id,
                "product_id": product_id,
                "name": new_product.name,
                "category": new_product.category,
                "sku": new_product.sku
            }
        }


@router.post("/search")
async def search_marketplaces(payload: SearchRequest):
    """Search product candidates by keyword across marketplaces."""
    selected_sites = payload.sites or ["Amazon", "eBay"]
    data = search_products(payload.query, selected_sites, payload.max_results_per_site)
    return data


@router.post("/track-from-search")
async def track_from_search(
    payload: TrackFromSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Create tracked product from search result selection."""
    if not payload.urls:
        raise HTTPException(status_code=400, detail="At least one site URL is required")

    with get_session() as session:
        product_id = f"prod_{uuid.uuid4().hex[:8]}"

        new_product = Product(
            user_id=current_user.id,
            product_id=product_id,
            name=payload.name,
            category=payload.category,
            sku=payload.sku or payload.name.replace(" ", "")[:30].upper(),
            amazon_url=payload.urls.get("Amazon"),
            ebay_url=payload.urls.get("eBay"),
            walmart_url=payload.urls.get("Walmart"),
            flipkart_url=payload.urls.get("Flipkart"),
        )

        session.add(new_product)
        session.flush()

        if payload.target_price is not None or payload.percentage_drop is not None:
            threshold = Threshold(
                user_id=current_user.id,
                product_id=new_product.id,
                target_price=payload.target_price,
                percentage_drop=payload.percentage_drop,
                enabled=True,
                send_email=True,
                send_slack=False,
            )
            session.add(threshold)

        session.commit()

        return {
            "status": "created",
            "product_id": new_product.product_id,
            "product_name": new_product.name,
        }
