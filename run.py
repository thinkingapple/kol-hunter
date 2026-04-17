#!/usr/bin/env python3
"""KOL Hunter - Entry point"""
import os
import uvicorn
import config
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("SPACE_PORT", config.APP_PORT)))
    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("RAILWAY_ENVIRONMENT") is None,
    )
