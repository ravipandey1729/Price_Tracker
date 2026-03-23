"""
Web Dashboard Entry Point

Run this file to start the web server:
    python web/main_web.py

Or use uvicorn directly:
    uvicorn web.app:app --reload --port 8000
"""

import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from utils.logging_config import setup_logging

if __name__ == "__main__":
    # Setup logging
    setup_logging()
    
    print("=" * 70)
    print(" Price Tracker Web Dashboard")
    print("=" * 70)
    print()
    print("Starting server...")
    print("Dashboard:  http://localhost:8000/dashboard")
    print("API Docs:   http://localhost:8000/api/docs")
    print("Health:     http://localhost:8000/health")
    print()
    print("Press CTRL+C to stop")
    print()
    
    # Run the server
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
