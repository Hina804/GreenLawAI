"""
Phase 3 - Pillar 4: API Ecosystem
FastAPI server to expose the GreenLawAI pipeline and predictive analytics
to external systems (mobile apps, dashboard, third-party services).
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn
from loguru import logger
import asyncio
from datetime import datetime
import json

# Import Core Pipeline & Models
from pipeline.coordinator import AgentCoordinator
from pipeline.proactive_scheduler import proactive_scheduler
from analytics.deforestation_predictor import DeforestationPredictor
from analytics.fire_predictor import FireRiskForecaster
import yaml
import os

app = FastAPI(
    title="GreenLawAI API",
    description="Intelligence Layer API for Environmental Law & Analytics",
    version="1.0.0"
)

# Initialize singletons
config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'rag_config.yaml')
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

coordinator = AgentCoordinator(config)
deforestation_predictor = DeforestationPredictor()
fire_predictor = FireRiskForecaster()

class QueryRequest(BaseModel):
    query: str
    audience: str = "dual"  # simple, legal, dual

class PredictionRequest(BaseModel):
    location: str

@app.get("/")
def health_check():
    return {"status": "online", "system": "GreenLawAI Intelligence Layer"}

@app.post("/api/v1/query")
async def process_query(req: QueryRequest):
    """Run the core multi-agent pipeline."""
    try:
        logger.info(f"[API] Processing query: {req.query}")
        result = await coordinator.run(req.query)
        
        # Build API response from ux_state structure
        ux_state = getattr(result, "get", lambda k, d=None: d)("ux_state")
        
        if ux_state == "SUCCESS":
            final_output = result.get("final_output", {})
            return {
                "status": "success",
                "responses": final_output
            }
        else:
            return {"status": "failure", "message": "Failed to generate comprehensive answer."}
            
    except Exception as e:
        logger.error(f"[API] Query Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/predictions/deforestation")
def get_deforestation_risk(location: str = "KPK"):
    """Get deforestation risk score for a location."""
    try:
        data = deforestation_predictor.predict_risk(location)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/predictions/fire")
def get_fire_risk(days: int = 3):
    """Get N-day fire risk forecast."""
    try:
        data = fire_predictor.forecast_risk(days_ahead=min(days, 7))
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/proactive/reports")
def get_proactive_reports():
    """Get the latest proactive agent reports (Patrols, Violations, Bulletins)."""
    try:
        reports = proactive_scheduler.get_latest_reports()
        return {"status": "success", "data": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Starting GreenLawAI API Server on port 8000")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
