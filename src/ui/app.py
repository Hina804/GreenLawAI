#E:\GL_AI\src\ui\app.py
import streamlit as st
from pathlib import Path
import asyncio
import yaml
import sys
import folium
from datetime import datetime
from streamlit_folium import st_folium
from loguru import logger
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

# --- Path Setup (Crucial for module discovery) ---
_this_file = Path(__file__).resolve()
_project_root = _this_file.parent.parent.parent  # E:\GL_AI
_src_dir = _project_root / "src"

if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.pdf_generator import generate_report
from pipeline.coordinator import AgentCoordinator
from pipeline.proactive_scheduler import proactive_scheduler

# --- Page config ---
st.set_page_config(page_title="🌲 GreenLawAI", layout="wide")

# --- Custom CSS for better readability ---
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .legal-answer {
        font-size: 1.1rem;
        line-height: 1.6;
        color: #1e1e1e;
        background-color: #f9f9f9;
        padding: 2rem;
        border-radius: 10px;
        border-left: 4px solid #2e7d32;
        margin: 1rem 0;
        white-space: pre-wrap;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    }
    .citation {
        font-size: 0.9rem;
        color: #666;
        border-top: 1px solid #ddd;
        margin-top: 1rem;
        padding-top: 1rem;
    }
    .trust-badge {
        display: inline-block;
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-weight: 500;
        margin-right: 1rem;
    }
    .stTextInput > div > div > input {
        font-size: 1.1rem;
        padding: 0.75rem;
    }
    .stButton > button {
        background-color: #2e7d32;
        color: white;
        font-size: 1.1rem;
        padding: 0.5rem 2rem;
        border-radius: 5px;
        border: none;
    }
    .stButton > button:hover {
        background-color: #1b5e20;
    }
</style>
""", unsafe_allow_html=True)

# --- UI Header ---
st.title("🌲 GreenLawAI")
st.markdown("AI-powered Forestry & Environmental Law System")

# --- Input ---
query = st.text_input("Enter your question:", placeholder="e.g., What is meant by timber? What is the penalty for cutting deodar?")

# --- Load Config ---
@st.cache_resource
def load_coordinator():
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "rag_config.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = {"default": {}}
    return AgentCoordinator(config)

coordinator = load_coordinator()

# --- Performance Pre-warming (Audit Fix) ---
from data.cache_manager import optimizer
import threading

if "prewarmed" not in st.session_state:
    try:
        # Fire-and-forget pre-warming in a background thread to avoid "no running loop" error
        def run_prewarm():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(optimizer.prewarm_cache(coordinator))
            loop.close()

        thread = threading.Thread(target=run_prewarm, daemon=True)
        thread.start()
        st.session_state.prewarmed = True
        logger.info("[UI] Background pre-warming thread started successfully.")
    except Exception as e:
        logger.error(f"[UI] Pre-warming trigger failed: {e}")
        st.session_state.prewarmed = False # Allow retry

def clean_content(content: str) -> str:
    """PRODUCTION-GRADE: Removes duplicate headers and ensures complete sentences."""
    if not isinstance(content, str): return str(content)
    
    header_patterns = [
        '⚖️ Legal Position', '🌍 Climate Impact', '🚨 Situational Awareness',
        '⚖️ Legal & Summary', '👥 Public Awareness', '🚨 Offence & Penalty',
        '### ⚖ OFFENCE & PENALTY'
    ]
    for h in header_patterns:
        content = content.replace(h, '')
    
    content = content.strip()
    # Sentence completion logic
    if content and not content.endswith(('.', '!', '?', ':')):
        last_period = content.rfind('.')
        if last_period > len(content) * 0.7:
            content = content[:last_period + 1]
    return content

class UIFormatter:
    """
    PRODUCTION-GRADE UI Formatter (Audit Fix)
    """
    def render_tab_content(self, tab_name, content):
        """
        Clean tab rendering without duplication (Day 17-18 implementation)
        """
        return clean_content(content)

class ProductionFeatures:
    """
    PRODUCTION-GRADE professional features (Phase 3 Adaptive Learning)
    """
    def track_usage(self, query, agent_used, response_time):
        logger.info(f"[Analytics] Query='{query}' Agent='{agent_used}' Time={response_time}s")

    def collect_feedback(self, query, response, rating, comment=""):
        from data.feedback_store import feedback_store
        from analytics.active_learner import ActiveLearner
        
        feedback_store.record_feedback(query, response, rating, comment)
        
        # In a real system, we'd schedule this async, but for MVP:
        if rating < 3:
            learner = ActiveLearner()
            learner.generate_knowledge_gap_report()

    def generate_share_link(self, query, response):
        return f"https://greenlaw.ai/share/{hash(query)}"

ui_formatter = UIFormatter()
prod_features = ProductionFeatures()

# --- Event Loop Management (Audit Fix) ---
import nest_asyncio
nest_asyncio.apply()

# --- Execution ---
if st.button("Submit", type="primary", width="stretch") and query:
    with st.spinner("Researching forest laws and analyzing climate data..."):
        # Run the coordinator
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            st.session_state.last_result = loop.run_until_complete(coordinator.run(query))
            loop.close()
            st.session_state.last_query = query
        except Exception as e:
            logger.error(f"[App] Execution failed: {e}")
            st.error("Engine execution failure. Check logs.")

if st.session_state.get("last_result") is not None:
    result = st.session_state.last_result
    # Use the query that generated this result
    current_query = st.session_state.get("last_query", query)
    
    st.subheader("System Response")
        
    # Extract multi-agent data
    legal_text = None
    climate_data = None
    monitoring_data = None
    simple_text = None
    citations = []
    confidence = 0.85
    
    if isinstance(result, dict):
        # Check for multi-agent structure
        final_output = result.get("final_output", {})
        
        if isinstance(final_output, dict):
            # Extract primary/legal response
            primary = final_output.get("primary") or final_output.get("legal")
            if primary:
                if isinstance(primary, dict):
                    legal_text = primary.get("legal_explanation") or primary.get("text")
                    simple_text = primary.get("simple_explanation", "")
                    citations = primary.get("citations", [])
                    confidence = primary.get("confidence", 0.85)
            
            # Extract climate agent data
            climate = final_output.get("climate")
            if climate:
                climate_data = climate.get("simple_explanation") or climate.get("text") or climate.get("insights")
            
            # Extract monitoring agent data
            monitoring = final_output.get("monitoring")
            if monitoring:
                monitoring_data = monitoring.get("linear_explanation") or monitoring.get("simple_explanation") or monitoring.get("incidents") or monitoring.get("text")
                monitoring_meta = monitoring.get("graph_metadata", {})
            else:
                monitoring_meta = {}

            # V7 Extract Awareness data
            awareness = final_output.get("awareness")
            if awareness:
                awareness_data = awareness.get("simple_explanation") or awareness.get("text")
            else:
                awareness_data = None

            # V7 Extract Incident data
            incident = final_output.get("incident")
            if incident:
                incident_data = incident.get("legal_explanation") or incident.get("text")
            else:
                incident_data = None

            # V7 Extract Summary data
            summary = final_output.get("summary")
            if summary:
                summary_data = summary.get("legal_explanation") or summary.get("text")
            else:
                summary_data = None
                
            # Phase 3 Extract Prediction data
            prediction_layer = final_output.get("prediction")
            if prediction_layer:
                if isinstance(prediction_layer, dict):
                    prediction_data = prediction_layer.get("legal_explanation") or prediction_layer.get("text")
                    prediction_meta = prediction_layer.get("graph_metadata", {}).get("predictions", {})
                else:
                    prediction_data = getattr(prediction_layer, "legal_explanation", "") or getattr(prediction_layer, "text", "")
                    prediction_meta = getattr(prediction_layer, "graph_metadata", {}).get("predictions", {})
            else:
                prediction_data = None
                prediction_meta = {}
            
            # Real-Time Data Extraction
            climate_meta = climate.get("graph_metadata", {}) if climate else {}
        
        # Fallback to primary_response if no multi-agent structure
        if not legal_text:
            primary_response = result.get("primary_response")
            if primary_response:
                if hasattr(primary_response, "legal_explanation"):
                    legal_text = primary_response.legal_explanation
                    simple_text = getattr(primary_response, "simple_explanation", "")
                    citations = getattr(primary_response, "citations", [])
                    confidence = getattr(primary_response, "confidence", 0.85)
    
    # Display the answer with multi-agent sections
    if legal_text:
        # Prepare data for PDF Report
        report_data = {
            "legal_text": legal_text,
            "climate_text": climate_data or "Not available.",
            "monitoring_text": monitoring_data or "Not available.",
            "citations": citations,
            "fire_stats": climate_meta.get("fire_stats", {}),
            "weather_stats": climate_meta.get("weather", {})
        }
        
        # Generate PDF in memory
        try:
            pdf_bytes = generate_report(current_query, report_data)
            st.download_button(
                label="📥 Download Professional Report (PDF)",
                data=pdf_bytes,
                file_name=f"GreenLawAI_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                key="pdf_download"
            )
        except Exception as e:
            logger.error(f"PDF Generation Error: {e}")

        # Trust indicator
        trust_color = "#2e7d32" if confidence > 0.7 else "#ed6c02" if confidence > 0.4 else "#d32f2f"
        st.markdown(f"""
        <div style="margin-bottom: 1rem; display: flex; align-items: center;">
            <span class="trust-badge">✓ VERIFIED_RESPONSE</span>
            <span style="color: {trust_color}; font-weight: 500;">Confidence: {confidence:.0%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Simple explanation (if available) - Professional prefix
        if simple_text:
            st.markdown(f"**{simple_text}**")
        
        # Create tabs ONLY if specialized Phase 2 agents have data
        if climate_data or monitoring_data or awareness_data or incident_data or summary_data or prediction_data:
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["⚖️ Legal & Summary", "👥 Public Awareness", "🌍 Climate Impact", "🚨 Situational Awareness", "📊 Predictions", "🤖 Proactive Ops"])
            
            with tab1:
                # IRAC / Primary Legal Text
                cleaned_legal = ui_formatter.render_tab_content("legal", legal_text)
                st.markdown(f'<div class="legal-answer">{cleaned_legal}</div>', unsafe_allow_html=True)
                
                # Executive Summary (Optional)
                if summary_data:
                    st.info("📝 **Executive Summary**")
                    st.markdown(ui_formatter.render_tab_content("summary", summary_data))
                
                # Citations
                if citations:
                    with st.expander("📚 Legal Sources", expanded=False):
                        for c in citations:
                            if hasattr(c, "document"):
                                doc = c.document
                                section = getattr(c, "section", "")
                            elif isinstance(c, dict):
                                doc = c.get("document", "Forest Act")
                                section = c.get("section", "")
                            else:
                                doc = str(c)
                                section = ""
                            
                            if section:
                                st.markdown(f"- **{doc}**, Section {section}")
                            else:
                                st.markdown(f"- **{doc}**")
            
            with tab2:
                if awareness_data:
                    st.success("👥 **Citizen Awareness Guide (Simplified)**")
                    st.markdown(ui_formatter.render_tab_content("awareness", awareness_data))
                else:
                    st.info("No simplified guide available for this query.")

            with tab3:
                if climate_data:
                    st.info("🌿 **Climate Impact Analysis**")
                    st.markdown(ui_formatter.render_tab_content("climate", climate_data))
                    
                    # Phase 3: Real-Time Visualization
                    if climate_meta.get("fire_stats"):
                        fstats = climate_meta["fire_stats"]
                        st.divider()
                        st.write("🛰️ **NASA FIRMS Real-Time Fire Report**")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Active Fires (24h)", fstats['total_fires'])
                        c2.metric("High Confidence", fstats['high_confidence'])
                        c22 = f"{round(fstats['avg_brightness'], 1)} K" if fstats['total_fires'] > 0 else "0 K"
                        c3.metric("Avg Intensity", c22)
                    
                    if climate_meta.get("weather"):
                        w = climate_meta["weather"]
                        st.divider()
                        st.write(f"🌤️ **Local Weather & Fire Risk ({w.get('city', 'Regional')})**")
                        wc1, wc2, wc3, wc4 = st.columns(4)
                        wc1.metric("Temperature", f"{w['temp']}°C")
                        wc2.metric("Humidity", f"{w['humidity']}%")
                        wc3.metric("Wind Speed", f"{w['wind_speed']} m/s")
                        
                        risk = w.get('risk_index', 0)
                        risk_color = "green" if risk < 30 else "orange" if risk < 60 else "red"
                        wc4.markdown(f"**Fire Risk Index**\n<h2 style='color:{risk_color}; margin:0;'>{risk}/100</h2>", unsafe_allow_html=True)

                    if climate_meta.get("metrics"):
                        m = climate_meta["metrics"]
                        st.write("📊 **Estimated Carbon Deficit**")
                        st.metric("Annual CO2 Sequestration Loss", f"{m.get('co2', 0)} kg", "Environmental Loss")
                        st.metric("Oxygen Production Loss", f"{m.get('oxygen', 0)} kg")
                else:
                    st.info("No climate data available for this query.")
            
            with tab4:
                # Incident Analyzer Report
                if incident_data:
                    st.error("📊 **Incident Violation Analysis**")
                    st.markdown(ui_formatter.render_tab_content("incident", incident_data))
                    st.divider()

                if monitoring_data:
                    st.warning("⚠️ **Situational Report & Alerts**")
                    st.markdown(monitoring_data if isinstance(monitoring_data, str) else str(monitoring_data))
                    st.divider()

                    # Phase 3: Interactive GIS Map
                    st.write("🗺️ **Live Environmental Monitoring Map**")
                    
                    # Set default center as Pakistan (Islamabad area)
                    m = folium.Map(location=[33.6844, 73.0479], zoom_start=6, tiles="OpenStreetMap")
                    
                    # Add NASA Fire Markers
                    if climate_meta.get("fire_stats", {}).get("recent_alerts"):
                        for fire in climate_meta["fire_stats"]["recent_alerts"]:
                            lat = fire.get('latitude')
                            lon = fire.get('longitude')
                            brightness = fire.get('bright_ti4')
                            if lat and lon:
                                folium.CircleMarker(
                                    location=[lat, lon],
                                    radius=8,
                                    popup=f"🔥 NASA FIRE\nBrightness: {brightness}K",
                                    color="red",
                                    fill=True,
                                    fill_color="orange"
                                ).add_to(m)

                    # Add GFW Hotspot Markers
                    if monitoring_meta.get("gfw_alerts", {}).get("recent_hotspots"):
                        for spot in monitoring_meta["gfw_alerts"]["recent_hotspots"]:
                            lat = spot.get('lat')
                            lon = spot.get('lon')
                            if lat and lon:
                                folium.Marker(
                                    location=[lat, lon],
                                    popup=f"🌳 DEFORESTATION ALERT\nDate: {spot.get('date')}",
                                    icon=folium.Icon(color="green", icon="leaf")
                                ).add_to(m)

                    # Render the map
                    st_folium(m, width=1100, height=500)
                    st.divider()

                    # Phase 3: Real-Time GFW & GDACS
                    if monitoring_meta.get("gfw_alerts"):
                        gfw = monitoring_meta["gfw_alerts"]
                        st.write("🌳 **Global Forest Watch (Deforestation Alerts)**")
                        gc1, gc2, gc3 = st.columns(3)
                        gc1.metric("GLAD Alerts (30d)", gfw['total_alerts'])
                        gc2.metric("High Confidence", gfw['high_confidence_alerts'])
                        gc3.metric("Est. Loss (ha)", gfw['estimated_loss_ha'])

                    if monitoring_meta.get("gdacs_alerts"):
                        st.write("📢 **Live GDACS Disaster Alerts**")
                        for alert in monitoring_meta["gdacs_alerts"]:
                            with st.expander(f"🔴 {alert['title']}", expanded=True):
                                st.write(alert['description'])
                                st.caption(f"Source: GDACS | Date: {alert['pubDate']}")
                    else:
                        st.success("✅ **No large-scale natural disasters detected in Pakistan today.**")
                else:
                    st.info("No active monitoring alerts.")
                    
            with tab5:
                if prediction_data:
                    st.success("🔮 **Predictive Analytics (Phase 3)**")
                    st.markdown(ui_formatter.render_tab_content("prediction", prediction_data))
                    
                    # Phase 3 Visualizations
                    heatmap_data = prediction_meta.get("heatmap", {})
                    if heatmap_data and heatmap_data.get("heatmap_points"):
                        st.divider()
                        st.write("🗺️ **Deforestation Risk Heatmap**")
                        
                        # Center on KPK
                        pm = folium.Map(location=[34.5, 72.5], zoom_start=7, tiles="CartoDB dark_matter")
                        
                        # Add heatmap layer
                        from folium.plugins import HeatMap
                        HeatMap(heatmap_data["heatmap_points"], radius=25, blur=15).add_to(pm)
                        
                        # Add markers for divisions
                        for div in heatmap_data.get("divisions", []):
                            risk_color = "red" if div['risk_level'] == 'CRITICAL' else "orange" if div['risk_level'] == 'HIGH' else "green"
                            folium.CircleMarker(
                                location=[div['lat'], div['lon']],
                                radius=8,
                                popup=f"<b>{div['name']}</b><br>Risk: {div['risk_score']}<br>Level: {div['risk_level']}",
                                color=risk_color,
                                fill=True,
                                fill_opacity=0.7
                            ).add_to(pm)
                            
                        st_folium(pm, width=1100, height=400, key="heatmap_map")
                else:
                    st.info("No predictive analytics available for this query.")
                    
            with tab6:
                st.success("🤖 **Proactive Operations Hub (Phase 3)**")
                reports = proactive_scheduler.get_latest_reports()
                
                # 1. Seasonal Awareness
                if reports.get("awareness", {}).get("status") != "error":
                    aw = reports["awareness"]
                    st.info(f"📅 **Public Awareness Bulletin: {aw.get('season')}**")
                    b = aw.get("bulletin", {})
                    urgency_color = "red" if b.get('urgency') == 'HIGH' else "orange"
                    st.markdown(f"### <span style='color:{urgency_color}'>{b.get('title')}</span>", unsafe_allow_html=True)
                    st.write(b.get("message"))
                    st.write("**Action Items:**")
                    for item in b.get("action_items", []):
                        st.write(f"- ✅ {item}")
                    st.divider()
                    
                # 2. Patrol Recommender
                if reports.get("patrol", {}).get("status") != "error":
                    pr = reports["patrol"]
                    st.warning("👮 **Daily Patrol Deployment Schedule**")
                    st.write(f"Total Critical Zones: {pr.get('total_critical_zones', 0)} | High Risk Zones: {pr.get('total_high_zones', 0)}")
                    
                    for rec in pr.get("recommendations", []):
                        priority = rec.get('priority', '')
                        color = "red" if "CRITICAL" in priority or "EXTREME" in priority else "orange"
                        st.markdown(f"**<span style='color:{color}'>{priority}</span> | Zone: {rec.get('division')}**", unsafe_allow_html=True)
                        st.write(f"👉 **Action:** {rec.get('action')}")
                        st.caption(f"Reason: {rec.get('reason')}")
                    st.divider()
                    
                # 3. Violation Detector
                if reports.get("violation", {}).get("status") != "error":
                    vd = reports["violation"]
                    st.error("🚨 **Systemic Violation Detection**")
                    
                    if vd.get("status") == "clear":
                        st.success("✅ No systemic violation patterns detected in the last 30 days.")
                    else:
                        st.write(f"Recent Incidents (30d): {vd.get('recent_incidents')}")
                        st.write(f"Night Operation Ratio: {vd.get('night_ratio', 0)*100:.0f}%")
                        
                        if vd.get("hotspots"):
                            st.write("**Detection Hotspots:**")
                            for h in vd["hotspots"]:
                                st.write(f"- 📍 {h['location']} ({h['count']} incidents)")
                                
                        if vd.get("systemic_alerts"):
                            st.write("**Automated Alerts:**")
                            for a in vd["systemic_alerts"]:
                                st.markdown(f"<p style='color:red;'>⚠️ {a}</p>", unsafe_allow_html=True)
                    
                st.caption(f"Last updated: {reports.get('last_updated', 'Never')}")
        else:
            # Single agent view (backward compatibility)
            st.markdown(f'<div class="legal-answer">{legal_text}</div>', unsafe_allow_html=True)
            
            if citations:
                with st.expander("📚 Sources", expanded=False):
                    for c in citations:
                        if hasattr(c, "document"):
                            doc = c.document
                            section = getattr(c, "section", "")
                        elif isinstance(c, dict):
                            doc = c.get("document", "Forest Act")
                            section = c.get("section", "")
                        else:
                            doc = str(c)
                            section = ""
                        
                        if section:
                            st.markdown(f"- **{doc}**, Section {section}")
                        else:
                            st.markdown(f"- **{doc}**")
                            
        # Phase 3: Adaptive Learning - Collect Feedback
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()
        st.markdown("### 📝 System Feedback")
        with st.expander("Provide Feedback to Improve GreenLawAI (1-minute)"):
            with st.form("feedback_form", clear_on_submit=True):
                f_col1, f_col2 = st.columns([1, 4])
                with f_col1:
                    rating = st.slider("Rating", 1, 5, 5, help="5=Excellent, 1=Poor")
                with f_col2:
                    comment = st.text_input("Comments (Optional)", placeholder="How can we improve this answer?")
                
                submitted = st.form_submit_button("Submit Feedback")
                if submitted:
                    prod_features.collect_feedback(current_query, result, rating, comment)
                    st.success("Thank you! Your feedback helps the system learn.")
                    
    else:
        st.error("No legal response could be generated. Please try rephrasing your question.")
        # Debug info (you can remove this in production)
        with st.expander("Debug Info", expanded=False):
            st.json(result if isinstance(result, dict) else {"type": str(type(result))})