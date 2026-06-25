from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from website_auditor import audit

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
        "business": result["business_name"],
        "url": result["url"],
        "score": result["score"],
        "rating": result["rating"],
        "issues": result["issues"][:5],
        "load_time_ms": result.get("load_time_ms", 0),
        "timestamp": datetime.now().isoformat()
    }