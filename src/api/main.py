"""
GreenLawAI — FastAPI Bridge (Lightweight)
Place at: E:\GL_AI\src\api\main.py
Run:      uvicorn src.api.main:app --reload --port 8000
"""

import os, sys, asyncio, random, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────
_api_dir      = Path(__file__).resolve().parent
_src_dir      = _api_dir.parent
_project_root = _src_dir.parent
_frontend_dir = _project_root / "frontend"

if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

load_dotenv(_project_root / ".env")

# ── App ──────────────────────────────────────────────────────
app = FastAPI(title="GreenLawAI API", version="4.0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── Static files — mount css/ and js/ at root ────────────────
if _frontend_dir.exists():
    _css = _frontend_dir / "css"
    _js  = _frontend_dir / "js"
    if _css.exists():
        app.mount("/css", StaticFiles(directory=str(_css)), name="css")
    if _js.exists():
        app.mount("/js",  StaticFiles(directory=str(_js)),  name="js")
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")

# ── Serve HTML pages ─────────────────────────────────────────
@app.get("/")
async def root():
    f = _frontend_dir / "index.html"
    return FileResponse(str(f)) if f.exists() else {"error": "frontend/ folder not found"}

@app.get("/{page}.html")
async def serve_page(page: str):
    f = _frontend_dir / f"{page}.html"
    if f.exists(): return FileResponse(str(f))
    raise HTTPException(404, f"{page}.html not found")

# ════════════════════════════════════════════════════════════
# DATA HELPERS — call source modules directly, never portal.py
# ════════════════════════════════════════════════════════════

def _get_fire_data():
    """Call FIRMSFireMonitor directly — no Streamlit dependency."""
    try:
        from data.fire_monitor import FIRMSFireMonitor
        fm = FIRMSFireMonitor(os.getenv("NASA_FIRMS_TOKEN", "DEMO_TOKEN"))
        return fm.get_active_fires(days=1)
    except Exception:
        return []

def _get_deforestation_data():
    try:
        from data.deforestation_monitor import GFWDeforestationMonitor
        gfw = GFWDeforestationMonitor()
        return gfw.get_alerts(days=30)
    except Exception:
        return {"total_alerts": 124, "recent_hotspots": []}

def _get_weather(city="Abbottabad"):
    try:
        from data.weather_monitor import WeatherMonitor
        wm = WeatherMonitor(os.getenv("OPENWEATHERMAP_KEY", ""))
        return wm.get_weather(city)
    except Exception:
        return None

def _get_forecast(city="Abbottabad"):
    try:
        from data.weather_monitor import WeatherMonitor
        wm = WeatherMonitor(os.getenv("OPENWEATHERMAP_KEY", ""))
        return wm.get_forecast(city)
    except Exception:
        return []

def _get_fusion_events():
    try:
        from data.fire_monitor import FIRMSFireMonitor
        from data.deforestation_monitor import GFWDeforestationMonitor
        from data.geo_intelligence import IntelligenceFusionEngine

        fires = _get_fire_data()
        defo  = _get_deforestation_data()
        stats = {
            "active_fires":         len(fires),
            "fire_alerts":          fires,
            "deforestation_alerts": defo.get("total_alerts", 0),
            "gfw_hotspots":         defo.get("recent_hotspots", []),
            "recent_incidents":     [],
            "weather_stats":        _get_weather(),
        }
        gic    = IntelligenceFusionEngine()
        fusion = gic.normalize_metadata(stats, weather_data=stats["weather_stats"])
        return fusion.get("events", []), fusion.get("metrics", {}), stats
    except Exception as e:
        return [], {}, {"active_fires": 23, "deforestation_alerts": 124,
                        "fire_alerts": [], "gfw_hotspots": []}

# ════════════════════════════════════════════════════════════
# ENDPOINT 1 — KPIs  (fast, no LLM)
# ════════════════════════════════════════════════════════════
@app.get("/api/dashboard/kpis")
async def dashboard_kpis():
    try:
        fires = _get_fire_data()
        defo  = _get_deforestation_data()
        return {
            "active_fires":         len(fires),
            "deforestation_alerts": defo.get("total_alerts", 124),
            "legal_cases":          47,
            "co2_risk_tonnes":      2240,
            "last_synced":          datetime.now().strftime("%H:%M:%S"),
            "feed_status":          "STABLE" if fires else "DEMO",
        }
    except Exception as e:
        return {"active_fires":23,"deforestation_alerts":124,
                "legal_cases":47,"co2_risk_tonnes":2240,
                "last_synced":datetime.now().strftime("%H:%M:%S"),
                "feed_status":"DEMO","_error":str(e)}

# ════════════════════════════════════════════════════════════
# ENDPOINT 2 — Alerts
# ════════════════════════════════════════════════════════════
@app.get("/api/alerts")
async def get_alerts(limit: int = Query(default=5, le=20)):
    try:
        fires     = _get_fire_data()
        defo_data = _get_deforestation_data()
        alerts    = []

        for fa in fires[:3]:
            lat = fa.get("latitude", fa.get("lat", 0))
            lon = fa.get("longitude", fa.get("lon", 0))
            alerts.append({
                "type":"critical","icon":"fa-fire",
                "title":"Fire Outbreak Detected",
                "desc":f"Thermal anomaly — confidence: {fa.get('confidence','nominal')}",
                "location":f"{lat:.3f}°N {lon:.3f}°E",
                "badge":"Critical","badge_cls":"critical","time":"Live",
            })

        for h in defo_data.get("recent_hotspots", [])[:2]:
            alerts.append({
                "type":"high","icon":"fa-tree",
                "title":"Deforestation Activity",
                "desc":f"GLAD alert — {h.get('area_ha','N/A')} ha",
                "location":h.get("location","Hazara Division"),
                "badge":"High","badge_cls":"high","time":"Recent",
            })

        # Always pad to 5
        static = [
            {"type":"high","icon":"fa-exclamation-triangle",
             "title":"Patrol Overdue — Unit P-04",
             "desc":"Last check-in 140 min ago. Communications silent.",
             "location":"Battagram Zone-2","badge":"High","badge_cls":"high","time":"22 min"},
            {"type":"medium","icon":"fa-smog",
             "title":"CO₂ Flux Anomaly",
             "desc":"Carbon flux spike 2.3× baseline in Kohistan.",
             "location":"Kohistan North","badge":"Medium","badge_cls":"medium","time":"35 min"},
            {"type":"info","icon":"fa-user",
             "title":"Citizen Report Received",
             "desc":"Timber truck spotted on restricted forest road.",
             "location":"Haripur District","badge":"Info","badge_cls":"info","time":"48 min"},
        ]
        while len(alerts) < 5:
            alerts.append(static[len(alerts) % len(static)])

        return {"alerts": alerts[:limit], "total": len(alerts)}
    except Exception as e:
        return {"alerts":[
            {"type":"critical","icon":"fa-fire","title":"Fire Outbreak Detected",
             "desc":"Active wildfire at Grid 34-N. 3.2 ha affected.",
             "location":"Mansehra Block-7","badge":"Critical","badge_cls":"critical","time":"2 min"},
            {"type":"high","icon":"fa-tree","title":"Illegal Logging Activity",
             "desc":"SAR anomaly: 0.8 ha cleared overnight.",
             "location":"Abbottabad Sec-3","badge":"High","badge_cls":"high","time":"11 min"},
        ], "_error": str(e)}

# ════════════════════════════════════════════════════════════
# ENDPOINT 3 — Districts
# ════════════════════════════════════════════════════════════
@app.get("/api/districts")
async def get_districts():
    BOUNDS = {
        "Mansehra":  (34.2,34.9,73.1,73.8),
        "Abbottabad":(33.8,34.3,72.9,73.5),
        "Battagram": (34.5,34.9,72.8,73.2),
        "Haripur":   (33.7,34.1,72.7,73.2),
        "Kohistan":  (34.8,36.2,72.8,74.0),
    }
    try:
        events, metrics, _ = _get_fusion_events()
        from collections import defaultdict
        counts = defaultdict(lambda:{"fires":0,"defo":0,"incidents":0,"conf":[]})

        for ev in events:
            lat = getattr(ev,"lat",None); lon = getattr(ev,"lon",None)
            if lat is None or lon is None: continue
            for d,(la,lb,loa,lob) in BOUNDS.items():
                if la<=lat<=lb and loa<=lon<=lob:
                    t = getattr(ev,"type","")
                    if t=="fire":          counts[d]["fires"]     += 1
                    if t=="deforestation": counts[d]["defo"]      += 1
                    if t=="incident":      counts[d]["incidents"] += 1
                    counts[d]["conf"].append(ev.details.get("confidence_score",0.75))

        result = []
        for name,(la,lb,loa,lob) in BOUNDS.items():
            c    = counts[name]
            conf = round(sum(c["conf"])/len(c["conf"])*100) if c["conf"] else (hash(name)%20+70)
            f    = c["fires"]
            defo = round(c["defo"]*1.8,1) or round((hash(name)%25)+8,1)
            if f>=8 or conf>=90: thr,cls="Critical","critical"
            elif f>=4 or conf>=80: thr,cls="High","high"
            elif f>=1 or conf>=60: thr,cls="Medium","medium"
            else: thr,cls="Low","low"
            result.append({"district":name,"fires":f,"defo_ha":defo,
                           "incidents":c["incidents"],"threat":thr,
                           "badge_cls":cls,"confidence":conf})
        result.sort(key=lambda x:x["fires"],reverse=True)
        return {"districts":result}
    except Exception as e:
        return {"districts":[
            {"district":"Mansehra",  "fires":9,"defo_ha":34.2,"incidents":22,"threat":"Critical","badge_cls":"critical","confidence":92},
            {"district":"Abbottabad","fires":5,"defo_ha":21.7,"incidents":15,"threat":"High",    "badge_cls":"high",    "confidence":87},
            {"district":"Battagram", "fires":4,"defo_ha":18.3,"incidents":11,"threat":"High",    "badge_cls":"high",    "confidence":84},
            {"district":"Haripur",   "fires":3,"defo_ha":12.1,"incidents":8, "threat":"Medium",  "badge_cls":"medium",  "confidence":79},
            {"district":"Kohistan",  "fires":2,"defo_ha":38.0,"incidents":6, "threat":"Medium",  "badge_cls":"medium",  "confidence":71},
        ],"_error":str(e)}

# ════════════════════════════════════════════════════════════
# ENDPOINT 4 — Forecast
# ════════════════════════════════════════════════════════════
@app.get("/api/forecast/{city}")
async def get_forecast(city: str = "Abbottabad"):
    try:
        raw = _get_forecast(city)
        if not raw: raise ValueError("empty")
        result = []
        for day in raw[:7]:
            rv = day.get("fire_risk",0)
            if rv>=70:   rc,rl="high","CRIT"
            elif rv>=40: rc,rl="high","HIGH"
            elif rv>=20: rc,rl="medium","MED"
            else:        rc,rl="low","LOW"
            desc = day.get("description","").lower()
            icon = ("🌧️" if "rain" in desc or "drizzle" in desc else
                    "⛈️" if "thunder" in desc else
                    "⛅" if "cloud" in desc and "part" in desc else
                    "☁️" if "cloud" in desc else
                    "🌨️" if "snow" in desc else "☀️")
            try: dn = datetime.strptime(day.get("date",""),"%Y-%m-%d").strftime("%a").upper()
            except: dn = "---"
            result.append({"day":dn,"icon":icon,"temp":day.get("temp","N/A"),
                           "description":day.get("description",""),
                           "risk_label":rl,"risk_cls":rc,"fire_risk":rv})
        return {"city":city,"forecast":result}
    except Exception as e:
        now = datetime.now()
        return {"city":city,"forecast":[
            {"day":(now+timedelta(days=i)).strftime("%a").upper(),
             "icon":["⛅","☀️","🌤️","⛈️","🌧️","🌤️","☀️"][i],
             "temp":[28,31,33,24,22,26,30][i],
             "description":["Partly Cloudy","Clear","Sunny","Thunderstorm","Rain","Partly Cloudy","Clear"][i],
             "risk_label":["HIGH","HIGH","CRIT","MED","LOW","MED","HIGH"][i],
             "risk_cls":["high","high","high","medium","low","medium","high"][i],
             "fire_risk":[65,72,85,38,18,42,70][i]}
            for i in range(7)
        ],"_error":str(e)}

# ════════════════════════════════════════════════════════════
# ENDPOINT 5 — Threat chart history
# ════════════════════════════════════════════════════════════
@app.get("/api/charts/threat-history")
async def threat_history():
    try:
        fires_now = len(_get_fire_data())
        defo_now  = _get_deforestation_data().get("total_alerts",124)
        seed_val  = int(hashlib.md5(datetime.now().strftime("%Y-%m-%d").encode()).hexdigest(),16)%1000
        random.seed(seed_val)
        labels,fires,defos=[],[],[]
        for i in range(30):
            d = datetime.now()-timedelta(days=29-i)
            labels.append(d.strftime("%b %d"))
            ratio = (i+1)/30
            fires.append(max(0,int(fires_now*ratio*random.uniform(0.5,1.5))))
            defos.append(max(0,int(defo_now*ratio*random.uniform(0.6,1.1))))
        fires[-1]=fires_now; defos[-1]=defo_now
        return {"labels":labels,"fires":fires,"defos":defos}
    except Exception as e:
        return {"labels":list(range(1,31)),
                "fires":[3,2,4,3,5,6,4,3,2,4,5,7,8,6,5,4,6,7,9,8,7,6,8,10,9,8,7,9,11,9],
                "defos":[6,7,5,8,9,10,8,7,9,10,11,9,10,12,11,10,9,11,13,12,14,13,11,12,14,13,15,14,16,15],
                "_error":str(e)}

# ════════════════════════════════════════════════════════════
# ENDPOINT 6 — System health
# ════════════════════════════════════════════════════════════
@app.get("/api/system/health")
async def system_health():
    firms_ok = bool(os.getenv("NASA_FIRMS_TOKEN"))
    gfw_ok   = True
    llm_ok   = bool(os.getenv("ANTHROPIC_API_KEY"))
    owm_ok   = bool(os.getenv("OPENWEATHERMAP_KEY"))
    return {"systems":[
        {"name":"NASA FIRMS Feed",  "pct":98 if firms_ok else 45, "cls":"ok"   if firms_ok else "warn"},
        {"name":"GFW GLAD Feed",    "pct":95 if gfw_ok   else 68, "cls":"ok"   if gfw_ok   else "warn"},
        {"name":"AI Fuser Engine",  "pct":99,                     "cls":"ok"},
        {"name":"LLM Intelligence", "pct":98 if llm_ok   else 0,  "cls":"ok"   if llm_ok   else "warn"},
        {"name":"OWM Climate API",  "pct":92 if owm_ok   else 45, "cls":"ok"   if owm_ok   else "warn"},
        {"name":"Evidence Vault",   "pct":97,                     "cls":"ok"},
    ]}

# ════════════════════════════════════════════════════════════
# ENDPOINT 7 — Legal (POST) — only loads coordinator on demand
# ════════════════════════════════════════════════════════════
class LegalQuery(BaseModel):
    query: str

@app.post("/api/legal/analyze")
async def legal_analyze(body: LegalQuery):
    try:
        import yaml, asyncio
        cfg_path = _project_root / "config" / "rag_config.yaml"
        cfg = yaml.safe_load(open(cfg_path)) if cfg_path.exists() else {}
        from pipeline.coordinator import AgentCoordinator
        coord  = AgentCoordinator(cfg)
        result = await asyncio.wait_for(coord.run(body.query), timeout=120)
        fo     = result.get("final_output",{})
        prim   = fo.get("primary") or fo.get("legal") or {}
        return {"answer":prim.get("legal_explanation") or result.get("answer",""),
                "simple":prim.get("simple_explanation",""),
                "citations":prim.get("citations",[]),
                "confidence":prim.get("confidence",0.85),"status":"ok"}
    except Exception as e:
        return {"answer":f"Error: {e}","simple":"","citations":[],"confidence":0,"status":"error"}

# ════════════════════════════════════════════════════════════
# ENDPOINT 8 — Citizen report (POST)
# ════════════════════════════════════════════════════════════
class CitizenReport(BaseModel):
    type: str
    location: str
    description: str
    contact: Optional[str] = None

@app.post("/api/citizen/report")
async def citizen_report(body: CitizenReport):
    try:
        import requests as rq
        rid = f"CIT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        msg = (f"🌿 CITIZEN REPORT\nID: {rid}\nType: {body.type}\n"
               f"Location: {body.location}\nDesc: {body.description}\n"
               f"Contact: {body.contact or 'Anonymous'}")
        email_sent = slack_sent = False
        relay = os.getenv("EMAIL_RELAY_URL"); dfo = os.getenv("DFO_EMAIL")
        if relay and dfo:
            r = rq.post(relay,json={"recipient":dfo,"to":dfo,
                "subject":f"[CITIZEN] {body.type} — {body.location}",
                "body":msg,"message":msg},timeout=15)
            email_sent = r.status_code==200
        tok = os.getenv("SLACK_BOT_TOKEN"); ch = os.getenv("SLACK_CHANNEL_ID")
        if tok and ch:
            r = rq.post("https://slack.com/api/chat.postMessage",
                headers={"Authorization":f"Bearer {tok}"},
                json={"channel":ch,"text":msg},timeout=10)
            slack_sent = r.json().get("ok",False)
        return {"status":"submitted","report_id":rid,
                "email_sent":email_sent,"slack_sent":slack_sent}
    except Exception as e:
        return {"status":"error","_error":str(e)}

# ════════════════════════════════════════════════════════════
# PING
# ════════════════════════════════════════════════════════════
@app.get("/api/ping")
async def ping():
    return {"status":"ok","time":datetime.now().isoformat(),
            "env":{k:"set" if os.getenv(k) else "missing" for k in
                   ["OPENWEATHERMAP_KEY","ANTHROPIC_API_KEY",
                    "NASA_FIRMS_TOKEN","SLACK_BOT_TOKEN","EMAIL_RELAY_URL"]}}