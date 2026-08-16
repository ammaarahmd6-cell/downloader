"""InsForge PostgREST client for database operations."""

from __future__ import annotations

import httpx
from app.core.config import get_settings

settings = get_settings()

class InsForgeDB:
    def __init__(self):
        self.base_url = f"{settings.INSFORGE_URL}/rest/v1"
        self.headers = {
            "apikey": settings.INSFORGE_API_KEY,
            "Authorization": f"Bearer {settings.INSFORGE_API_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def _get_client(self):
        return httpx.AsyncClient(base_url=self.base_url, headers=self.headers)
        
    async def get_job(self, job_id: str) -> dict | None:
        async with self._get_client() as client:
            res = await client.get(f"/jobs?id=eq.{job_id}")
            res.raise_for_status()
            data = res.json()
            return data[0] if data else None
            
    async def update_job(self, job_id: str, data: dict) -> dict:
        async with self._get_client() as client:
            res = await client.patch(f"/jobs?id=eq.{job_id}", json=data)
            res.raise_for_status()
            return res.json()
            
    async def create_job(self, data: dict) -> dict:
        async with self._get_client() as client:
            res = await client.post("/jobs", json=data)
            res.raise_for_status()
            return res.json()
            
    async def create_history(self, data: dict) -> dict:
        async with self._get_client() as client:
            res = await client.post("/download_history", json=data)
            res.raise_for_status()
            return res.json()

db_client = InsForgeDB()
