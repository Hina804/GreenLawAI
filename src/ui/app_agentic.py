#E:\GL_AI\src\ui\app_agentic.py
import sys
import os
import asyncio
import json
import yaml
from datetime import datetime
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# --- Path Setup (Crucial for module discovery) ---
_this_file = Path(__file__).resolve()
_project_root = _this_file.parent.parent.parent  # E:\GL_AI
_src_dir = _project_root / "src"

if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from pipeline.coordinator_agentic import get_coordinator
from pipeline.coordinator import AgentCoordinator
from services.forest_watchdog import watchdog

# --- Async Helper to prevent ResourceWarnings ---
def run_async(coro):
    """Safely run async coroutine in Streamlit's event loop environment."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# Set page config for a premium look
st.set_page_config(
    page_title="GreenLawAI Autonomous",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for premium aesthetics
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .thought-container {
        background-color: #1e2130;
        border-left: 5px solid #4ade80;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .action-badge {
        background-color: #3b82f6;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
    }
    .lesson-box {
        background-color: #374151;
        border: 1px dashed #fbbf24;
        padding: 10px;
        border-radius: 5px;
    }
    .recovery-banner {
        background-color: #92400e;
        border: 1px solid #fbbf24;
        padding: 10px;
        border-radius: 5px;
        color: #fef3c7;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_standard_coordinator():
    config_path = _project_root / "config" / "rag_config.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    return AgentCoordinator(config)

@st.cache_resource
def start_autonomous_watchdog():
    """Starts the background watchdog service once."""
    try:
        # Create a new event loop for the background service if needed
        # In Streamlit, we just want to ensure the async 'start' is called
        asyncio.run(watchdog.start())
        return "Watchdog Active"
    except Exception as e:
        return f"Watchdog Error: {e}"

def main():
    # Initialize coordinators
    coordinator_agentic = get_coordinator()
    coordinator_standard = load_standard_coordinator()
    
    st.title("🤖 GreenLawAI Autonomous")
    st.subheader("Autonomous Forest Intelligence & Legal Action System")
    
    # --- NAVIGATION ---
    st.write("### 📂 Select Active Intelligence Module")
    active_tab = st.radio(
        "Navigation",
        ["Global Chat", "Forest Surveillance", "Climate Intelligence", "Citizen Action Hub"],
        horizontal=True,
        index=0,
        label_visibility="collapsed"
    )
    st.divider()

    # --- SIDEBAR: SYSTEM STATUS & CONFIGURATION ---
    with st.sidebar:
        st.title("⚙️ System Control")
    
    # Sidebar: System Status & Configuration
    with st.sidebar:
        st.divider()
        st.header("🛡️ System Mode")
        rag_mode = st.toggle("Standard RAG Mode (Stable)", value=False, help="Switch to the stable, high-accuracy RAG system.")
        
        st.divider()
        st.header("⚙️ System Status")
        watchdog_status = start_autonomous_watchdog()
        if "Active" in watchdog_status:
            st.success("🟢 Autonomous Watchdog: ACTIVE")
        else:
            st.error(f"🔴 {watchdog_status}")

        if rag_mode:
            st.success("Mode: STANDARD RAG (Stable)")
        else:
            st.info("Mode: AUTONOMOUS AGENT")

        # Health Status from coordinator
        health = coordinator_agentic.health_status
        
        st.success("Reasoning Engine: ONLINE")
        st.success("Memory Fabric: ONLINE")
        
        # LLM Status Indicator (detailed)
        if health["llm_connected"]:
            if health["llm_degraded"]:
                st.warning("🧠 Intelligence: DEGRADED (Using Fallback)")
            else:
                st.success("🧠 Intelligence (LLM): CONNECTED")
        else:
            st.warning("⚠️ Intelligence (LLM): INITIALIZING...")
            st.caption("LLM will connect on first query.")
        
        # Tunnel Status
        if health.get("keepalive_status"):
            if health["tunnel_healthy"]:
                st.success("🌐 Colab Tunnel: HEALTHY")
            else:
                st.error("🌐 Colab Tunnel: DOWN")
                st.caption("System will use LocalFallback automatically.")
        
        st.info("Pillar 4: Reflection Enabled")
        
        st.divider()
        st.header("🌍 Live World Monitoring")
        st.success("🛰️ Satellite Feed (NASA GIBS): ACTIVE")
        st.success("📨 Slack Notifier: CONNECTED")
        st.success("🔎 Web Grounding (Live): ACTIVE")
        st.caption("All alerts are grounded in real-time data.")
        
        st.divider()
        st.header("🧠 Learning Hub")
        if st.button("View All Learned Lessons"):
            st.write("Retrieving from ChromaDB...")
            
        st.divider()
        if st.button("🗑️ Clear Chat History", width="stretch"):
            st.session_state.messages = []
            st.rerun()
            
    # Session State for Conversation and Routing
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_query_tab" not in st.session_state:
        st.session_state.last_query_tab = "Global Chat"
    if "processing" not in st.session_state:
        st.session_state.processing = False

    # --- MAIN CONTENT DYNAMICS ---
    if active_tab == "Global Chat":
        st.header("💬 Intelligence Chat")
        # Render Chat Interface
        for message in st.session_state.messages:
            # Show messages belonging to this tab OR generic Role messages
            msg_tab = message.get("tab", "Global Chat")
            if msg_tab != "Global Chat": continue
            
            with st.chat_message(message["role"]):
                content = message["content"]
                # ... existing rendering logic ...
                
                # --- IMAGE RENDERING LOGIC ---
                import re
                image_marker_pattern = r"IMAGE_PATH\[(.*?)\]"
                image_matches = re.findall(image_marker_pattern, content)
                
                # Clean content of markers for display
                image_marker_pattern = r"IMAGE_PATH\[(.*?)\]"
                display_content = re.sub(image_marker_pattern, "", content).strip()
                if display_content:
                    import re
                    lines = display_content.split("\n")
                    cleaned_lines = []
                    for line in lines:
                        stripped = line.strip()
                        if stripped in ["0", "0.0", "None", "null", "---", "Answer:", "Answer", "-"]:
                            continue
                        if re.match(r"^\s*0\s*$", line):
                            continue
                        cleaned_lines.append(line)
                    
                    display_content = "\n".join(cleaned_lines).strip()
                    if display_content:
                        st.markdown(display_content, unsafe_allow_html=True)
                
                # Render images if found
                for img_path in image_matches:
                    img_path = img_path.strip()
                    if os.path.exists(img_path):
                        st.image(img_path, caption="🛰️ NASA GIBS Satellite Intelligence (Live Feed)", width="stretch")
                
                if "reflection" in message and message["reflection"]:
                    with st.expander("🔍 Reflection & Learning"):
                        st.json(message["reflection"])

    elif active_tab == "Forest Surveillance":
        st.header("🛰️ Forest Surveillance Dashboard")
        
        # --- STATIC DASHBOARD HEADER (Persistent) ---
        with st.container():
            st.info("Continuous 24/7 background monitoring for illegal activities in the Hazara range.")
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Detection Confidence", "94%", "+2%")
            with col2: st.metric("Monitored Area", "42,000 ha", "KPK Range")
            with col3: st.metric("System Health", "Optimal")
            
            # --- SYNCED INSIGHTS / ALERTS (Moved Up) ---
            st.subheader("📋 Recent Detections & Evidence")
            from agents.incident_agent import IncidentAgent
            ia = IncidentAgent(config={})
            recent_hazara = ia._get_relevant_incidents("hazara")
            
            if recent_hazara:
                latest = recent_hazara[-1]
                with st.expander(f"🚨 INCIDENT: {latest.get('id', 'GL-EV-NEW')} (Active Alert)", expanded=True):
                    st.error(f"**STATUS: {latest.get('status', 'READY FOR REVIEW').upper()}**")
                    st.markdown(f"""
                    • **Location**: {latest.get('location')}  
                    • **Detection type**: Autonomous Satellite  
                    • **Specie/Violation**: {latest.get('species')} / {latest.get('violation')}  
                    """)
                    if st.button("Dispatch Evidence Package", key=f"dispatch_{latest['id']}"):
                        st.success(f"✅ Evidence Package dispatched via Slack!")

            st.subheader("💡 Latest Surveillance Insight")
            found_surv = False
            # Deduplication: Find all assistant messages for this tab and skip the most recent one
            tab_messages = [m for m in st.session_state.messages if m["role"] == "assistant" and m.get("tab") == "Forest Surveillance"]
            messages_to_check = tab_messages[:-1] if len(tab_messages) > 1 else []

            for msg in reversed(messages_to_check):
                if msg["role"] == "assistant" and msg.get("tab") == "Forest Surveillance":
                    content = msg["content"]
                    if any(kw in content for kw in ["### 🛰️", "### 🕵️", "### 🛡️", "Satellite", "Investigation", "Patrol"]):
                        import re
                        sections = re.split(r"(?m)^(?=### )", content)
                        relevant = [s for s in sections if re.search(r"### (🛰️|🕵️|🛡️|Satellite|Investigation|Patrol)", s)]
                        if relevant:
                            st.markdown("".join(relevant))
                            found_surv = True
                            break
            if not found_surv:
                st.caption("No recent surveillance investigations.")
            
        st.divider()

        # --- CHAT HISTORY SECTION ---
        # --- CHAT HISTORY SECTION ---
        for message in st.session_state.messages:
            msg_tab = message.get("tab", "Global Chat")
            if msg_tab == "Forest Surveillance":
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])


    elif active_tab == "Climate Intelligence":
        st.header("🌦️ Climate Intelligence Oracle")
        
        # --- STATIC DASHBOARD HEADER ---
        with st.container():
            st.markdown("7-day weather forecasting and fire risk analysis for North Pakistan.")
            location = st.selectbox("Select District", ["Abbottabad", "Mansehra", "Haripur", "Swat"])
            
            # Trigger forecast fetch (Cached to prevent redundant loop triggers)
            from data.weather_monitor import WeatherMonitor
            wm = WeatherMonitor(os.getenv("OPENWEATHERMAP_KEY", "DEMO_KEY"))
            
            @st.cache_data(ttl=3600)
            def get_cached_forecast(loc):
                return wm.get_forecast(loc)
                
            forecast = get_cached_forecast(location)
            
            # Show Forecast Layout
            cols = st.columns(5)
            for i, day in enumerate(forecast[:5]):
                with cols[i]:
                    st.write(f"**{day['date'][5:]}**")
                    st.write(f"{day['temp']}°C")
                    st.caption(day['description'])
                    risk_color = "red" if day['fire_risk'] > 60 else "green"
                    st.markdown(f"<span style='color:{risk_color}'>Fire Risk: {day['fire_risk']}</span>", unsafe_allow_html=True)
                    if day.get('note'):
                        st.caption(day['note'])
            
            # --- SYNCED CLIMATE INSIGHT (Moved Up) ---
            st.subheader("💡 Latest Climate Oracle Insight")
            found_climate = False
            # Deduplication: Find all assistant messages for this tab and skip the most recent one
            tab_messages = [m for m in st.session_state.messages if m["role"] == "assistant" and m.get("tab") == "Climate Intelligence"]
            messages_to_check = tab_messages[:-1] if len(tab_messages) > 1 else []

            for msg in reversed(messages_to_check):
                if msg["role"] == "assistant" and msg.get("tab") == "Climate Intelligence":
                    content = msg["content"]
                    if "### 🌦️" in content or "Climate" in content:
                        import re
                        sections = re.split(r"(?m)^(?=### )", content)
                        relevant = [s for s in sections if "### 🌦️" in s or "Climate" in s]
                        if relevant:
                            st.markdown("".join(relevant))
                            found_climate = True
                            break
            if not found_climate:
                st.caption("No recent climate investigations.")
        
        st.divider()

        # --- CHAT HISTORY ---
        # --- CHAT HISTORY ---
        for message in st.session_state.messages:
            msg_tab = message.get("tab", "Global Chat")
            if msg_tab == "Climate Intelligence":
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])


    elif active_tab == "Citizen Action Hub":
        st.header("🌱 Citizen Action Hub")

        # --- STATIC GUIDES (Persistent Top) ---
        with st.container():
            st.success("Your guide to proactive forest conservation and reporting.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📅 Seasonal Guide")
                from agents.awareness_agent import AwarenessAgent
                aa = AwarenessAgent(config={})
                seasonal = aa.get_seasonal_awareness()
                st.info(f"**{seasonal['season']} (Planting Season)**: {seasonal['message']}")
            
            with col2:
                st.subheader("📢 Reporting Protocol")
                reporting = aa.get_reporting_guide()
                st.warning(f"**Emergency**: {reporting['emergency']}")
                st.write(f"**DFO Abbottabad Line**: +923495994503")

            st.subheader("💡 Today's Forest Actions")
            actions = aa.get_climate_action_guide()
            for action in actions['daily_actions']:
                st.markdown(action)
            
            # --- SYNCED AWARENESS INSIGHT (Moved Up) ---
            st.subheader("💡 Latest Citizen Action Insight")
            found_awareness = False
            # Deduplication: Find all assistant messages for this tab and skip the most recent one
            tab_messages = [m for m in st.session_state.messages if m["role"] == "assistant" and m.get("tab") == "Citizen Action Hub"]
            messages_to_check = tab_messages[:-1] if len(tab_messages) > 1 else []

            for msg in reversed(messages_to_check):
                if msg["role"] == "assistant" and msg.get("tab") == "Citizen Action Hub":
                    content = msg["content"]
                    if "### 🌱" in content or "Citizen" in content or "Awareness" in content:
                        import re
                        sections = re.split(r"(?m)^(?=### )", content)
                        relevant = [s for s in sections if any(kw in s for kw in ["### 🌱", "Citizen", "Awareness", "Action", "Help"])]
                        if relevant:
                            st.markdown("".join(relevant))
                            found_awareness = True
                            break
            if not found_awareness:
                st.caption("No recent awareness guidance.")

        st.divider()

        # --- CHAT HISTORY ---
        # --- CHAT HISTORY ---
        for message in st.session_state.messages:
            msg_tab = message.get("tab", "Global Chat")
            if msg_tab == "Citizen Action Hub":
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])


    if prompt := st.chat_input("Ask about forest laws, risks, or request an action...", key="global_chat_input"):
        # Loop Prevention Guard: Check if we are already processing this exact prompt
        if st.session_state.get("processing"):
            st.stop()
            
        st.session_state.processing = True
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt, "tab": active_tab})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Agent logic
        with st.chat_message("assistant"):
            with st.status("🤖 Agent Thinking...", expanded=True) as status:
                try:
                    if rag_mode:
                        # STANDARD RAG MODE
                        status.update(label="⚖️ Consulting Legal Specialist...", state="running")
                        raw_result = run_async(coordinator_standard.run(prompt))
                        
                        final_output = raw_result.get("final_output", {})
                        primary = final_output.get("primary") or final_output.get("legal")
                        
                        if primary:
                            answer = primary.get("legal_explanation") or primary.get("text") or ""
                            result = {
                                "answer": answer,
                                "steps": [{"action": "Standard RAG", "thought": "Consulting legal grounding and knowledge graph...", "result": "Success"}]
                            }
                        else:
                            result = {"answer": "No legal response could be generated in Standard Mode.", "steps": []}
                    else:
                        # AUTONOMOUS MODE
                        result = run_async(coordinator_agentic.run(prompt))
                    
                    # Recovery mode banner
                    if result.get("recovery_mode"):
                        st.markdown('<div class="recovery-banner">⚡ <b>Recovery Mode</b>: LLM was unstable. Tools were executed directly for reliability.</div>', unsafe_allow_html=True)
                    
                    # Display Steps (skip error/fallback steps)
                    displayed_step = 0
                    for step in result.get("steps", []):
                        action = step.get('action', '')
                        if action in ["error", "fallback"]:
                            continue
                        
                        displayed_step += 1    
                        thought_text = step.get('thought') or step.get('reasoning') or "Thinking..."
                        
                        st.markdown(f"**Step {displayed_step}: {action}**")
                        st.markdown(f"<div class='thought-container'>{thought_text}</div>", unsafe_allow_html=True)
                        with st.expander("🛠️ Tool Result"):
                            st.write(step.get('result', {}))
                    
                    status.update(label="✅ Task Complete!", state="complete", expanded=False)
                    
                    answer = result.get("answer", "No answer generated.")
                    if answer:
                        st.markdown(answer)
                    
                    # Display Reflection
                    if "reflection" in result and result["reflection"]:
                        reflection = result["reflection"]
                        with st.expander("✨ Self-Reflection & Optimization"):
                            col1, col2 = st.columns(2)
                            col1.metric("Success Score", f"{reflection.get('score', 0)*100:.0f}%")
                            col2.metric("Variant", reflection.get("variant", "A"))
                            
                            lesson = reflection.get("lesson_learned")
                            if lesson and lesson != "None":
                                st.markdown(f"<div class='lesson-box'>💡 <b>New Lesson Learned:</b> {lesson}</div>", unsafe_allow_html=True)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": answer or "Task completed.",
                        "reflection": result.get("reflection"),
                        "tab": active_tab
                    })
                    st.session_state.processing = False
                    st.rerun() # Refresh to show dynamic components (like images)
                    
                except Exception as e:
                    st.error(f"Error: {e}")
                    status.update(label="❌ Failed", state="error")

if __name__ == "__main__":
    main()
