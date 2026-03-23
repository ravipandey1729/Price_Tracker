"""
FastAPI Application Initialization

Main application setup with routes, middleware, and static file serving.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import logging

# Import API routers
from web.api import auth, products, scraping, thresholds, health, notifications

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Price Tracker Dashboard",
    description="Web interface for monitoring and managing price tracking",
    version="0.7.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Get paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure directories exist
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Root redirect to dashboard
@app.get("/", response_class=RedirectResponse)
async def root():
    """Redirect root to dashboard"""
    return RedirectResponse(url="/dashboard")


# Dashboard page
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    try:
        # Import here to avoid circular imports
        from database.connection import get_session
        from database.models import Product, Price, ScraperRun
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        with get_session() as session:
            # Get statistics
            total_products = session.query(func.count(Product.id)).scalar()
            total_prices = session.query(func.count(Price.id)).scalar()
            
            # Get latest prices (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_prices = (
                session.query(Price)
                .filter(Price.scraped_at >= yesterday)
                .order_by(Price.scraped_at.desc())
                .limit(10)
                .all()
            )
            
            # Get latest scraper runs
            recent_runs = (
                session.query(ScraperRun)
                .order_by(ScraperRun.start_time.desc())
                .limit(5)
                .all()
            )
            
            # Calculate success rate
            if recent_runs:
                successful = sum(1 for r in recent_runs if r.status.value == 'completed')
                success_rate = (successful / len(recent_runs)) * 100
            else:
                success_rate = 0
            
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context={
                    "request": request,
                    "total_products": total_products,
                    "total_prices": total_prices,
                    "recent_prices": recent_prices,
                    "recent_runs": recent_runs,
                    "success_rate": success_rate
                }
            )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"request": request, "error": str(e)},
            status_code=500
        )


# Products page
@app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    """Products listing page"""
    try:
        from database.connection import get_session
        from database.models import Product
        
        with get_session() as session:
            products = session.query(Product).all()
            
            return templates.TemplateResponse(
                request=request,
                name="products.html",
                context={"request": request, "products": products}
            )
    except Exception as e:
        logger.error(f"Products page error: {e}")
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"request": request, "error": str(e)},
            status_code=500
        )


# Add Product page
@app.get("/products/add", response_class=HTMLResponse)
async def add_product_page(request: Request):
    """Add new product page"""
    return templates.TemplateResponse(
        request=request,
        name="add_product.html",
        context={"request": request}
    )


# Search page
@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Product search and comparison page."""
    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={"request": request}
    )


@app.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request):
    """Login/register page."""
    return templates.TemplateResponse(
        request=request,
        name="auth.html",
        context={"request": request}
    )


# Thresholds page
@app.get("/thresholds", response_class=HTMLResponse)
async def thresholds_page(request: Request):
    """Thresholds management page"""
    try:
        from database.connection import get_session
        from database.models import Threshold, Product
        
        with get_session() as session:
            thresholds = (
                session.query(Threshold)
                .join(Product)
                .order_by(Product.name)
                .all()
            )
            products = session.query(Product).all()
            
            return templates.TemplateResponse(
                request=request,
                name="thresholds.html",
                context={
                    "request": request,
                    "thresholds": thresholds,
                    "products": products
                }
            )
    except Exception as e:
        logger.error(f"Thresholds page error: {e}")
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"request": request, "error": str(e)},
            status_code=500
        )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy", "version": "0.7.0"}


# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(scraping.router, prefix="/api/scraping", tags=["scraping"])
app.include_router(thresholds.router, prefix="/api/thresholds", tags=["thresholds"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(health.router, prefix="/api/system", tags=["system"])


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Price Tracker Web Dashboard starting up...")
    logger.info(f"Static files: {STATIC_DIR}")
    logger.info(f"Templates: {TEMPLATES_DIR}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Price Tracker Web Dashboard shutting down...")
