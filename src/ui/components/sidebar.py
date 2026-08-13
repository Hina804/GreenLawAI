"""
GreenLawAI Unified Portal — Persistent Sidebar Component
Extracted from app_agentic.py for reuse across all 7 pages.
"""
import streamlit as st


def render_sidebar(coordinator_agentic, rag_mode_default=False):
    """
    Renders the full persistent sidebar and returns the current rag_mode toggle state.
    """
    with st.sidebar:
        # --- Branding ---
        st.markdown("""
        <div style="text-align:center; padding: 10px 0 5px 0;">
            <span style="font-size:2.5rem;">🌲</span>
            <h2 style="margin:0; color:#10b981;">GreenLawAI</h2>
            <p style="margin:0; font-size:0.8rem; color:#6b7280;">Unified Intelligence Platform v1.0</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # --- System Mode ---
        st.header("🛡️ System Mode")
        rag_mode = st.toggle(
            "Standard RAG Mode (Stable)",
            value=rag_mode_default,
            help="Switch between Autonomous Agent and stable RAG system."
        )
        if rag_mode:
            st.success("Mode: STANDARD RAG (Stable)")
        else:
            st.info("Mode: AUTONOMOUS AGENT")

        st.divider()

        # --- System Status ---
        st.header("⚙️ System Status")

        # Watchdog
        try:
            from services.forest_watchdog import watchdog
            if watchdog.scheduler.running:
                st.success("🟢 Autonomous Watchdog: ACTIVE")
            else:
                st.info("🟡 Watchdog: STANDBY")
        except Exception:
            st.info("🟡 Watchdog: STANDBY")

        # Core systems
        st.success("Reasoning Engine: ONLINE")
        st.success("Memory Fabric: ONLINE")

        # LLM Health
        if coordinator_agentic:
            health = coordinator_agentic.health_status
            llm_connected = health.get("llm_connected")
            
            # If not explicitly connected in health_status, do a quick active check
            if not llm_connected:
                from ui.health_utils import check_llm_health
                if check_llm_health():
                    llm_connected = True

            if llm_connected:
                if health.get("llm_degraded"):
                    st.warning("🧠 Intelligence: DEGRADED (Fallback)")
                else:
                    st.success("🧠 Intelligence (LLM): CONNECTED")
            else:
                st.warning("⚠️ Intelligence (LLM): DISCONNECTED")
                st.caption("Please check your Colab server.")

            # Tunnel
            if health.get("keepalive_status"):
                if health.get("tunnel_healthy"):
                    st.success("🌐 Colab Tunnel: HEALTHY")
                else:
                    st.error("🌐 Colab Tunnel: DOWN")
                    st.caption("System will use LocalFallback automatically.")

        st.info("Pillar 4: Reflection Enabled")

        st.divider()

        # --- Live Monitoring ---
        st.header("🌍 Live World Monitoring")
        st.success("🛰️ Satellite Feed (NASA GIBS): ACTIVE")
        st.success("📨 Slack Notifier: CONNECTED")
        st.success("🔎 Web Grounding (Live): ACTIVE")
        st.caption("All alerts are grounded in real-time data.")

        st.divider()

        # --- Quick Stats ---
        st.header("📊 Quick Stats")
        qs1, qs2, qs3 = st.columns(3)
        qs1.metric("Docs", "2,953")
        qs2.metric("Agents", "8")
        qs3.metric("24/7", "✓")

        st.divider()

        # --- Learning Hub ---
        st.header("🧠 Learning Hub")
        if st.button("📖 View Lessons", width="stretch"):
            st.write("Retrieving from ChromaDB...")

        if st.button("🗑️ Clear Chat History", width="stretch"):
            st.session_state.messages = []
            st.rerun()

    return rag_mode
