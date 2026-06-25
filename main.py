from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

# import your existing functions here
# from auditor import audit

app = FastAPI()


class AuditRequest(BaseModel):
    url: str
    name: str | None = None


@app.get("/")
def home():
    return {"status": "API running"}


@app.post("/audit")
def run_audit(data: AuditRequest):
    result = audit(data.url, business_name=data.name)

    return {
        "business": result["business_name"],
        "url": result["url"],
        "score": result["score"],
        "rating": result["rating"],
        "rating_desc": result["rating_desc"],
        "issues": result["issues"][:5],
        "positives": result["positives"][:5],
        "load_time_ms": result["load_time_ms"],
        "timestamp": datetime.now().isoformat()
    }