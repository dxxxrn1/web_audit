from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

from website_auditor import audit   # IMPORTANT FIX

app = FastAPI()


class AuditRequest(BaseModel):
    url: str
    name: str | None = None


@app.get("/")
def home():
    return {"status": "API running"}


@app.post("/audit")
def run_audit(data: AuditRequest):
    result = audit(data.url, data.name)

    return {
        "business": result.get("business_name"),
        "url": result.get("url"),
        "score": result.get("score"),
        "issues": result.get("issues", [])[:5],
        "load_time_ms": result.get("load_time_ms"),
        "timestamp": datetime.now().isoformat()
    }