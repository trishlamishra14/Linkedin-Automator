"""Run the FastAPI server. Usage: `python run.py`."""

from __future__ import annotations

import uvicorn

from src.config import settings


if __name__ == "__main__":
    uvicorn.run("src.api:app", host=settings.host, port=settings.port, reload=False)
