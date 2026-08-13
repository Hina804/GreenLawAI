# ui/components.py
import streamlit as st
from ui.theme import COLORS, STATUS, get_color, get_status_color

def render_header():
    """Render the main header with GreenLawAI branding"""
    st.markdown(f"""
    <div style="background: {COLORS['bg_secondary']}; 
         padding: 1rem 2rem; 
         border-radius: 12px; 
         margin-bottom: 2rem;
         border: 2px solid {COLORS['border']};">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="font-size: 2.5rem;">🌲</div>
                <div>
                    <h1 style="margin: 0; font-size: 2rem; font-weight: 800; 
                         background: linear-gradient(135deg, {COLORS['primary_dark']}, {COLORS['primary']});
                         -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                         background-clip: text;">
                        GreenLawAI
                    </h1>
                    <span style="color: {COLORS['text_secondary']}; font-size: 0.85rem; font-weight: 500;">
                        Unified Intelligence Platform
                    </span>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="display: flex; align-items: center; gap: 0.5rem;
                     background: {COLORS['bg_primary']}; padding: 0.5rem 1rem;
                     border-radius: 20px; border: 2px solid {COLORS['border']};">
                    <span style="width: 8px; height: 8px; border-radius: 50%;
                         background: {COLORS['primary_light'] if not st.session_state.get('offline_mode', False) else COLORS['primary']};
                         display: inline-block;"></span>
                    <span style="font-size: 0.8rem; font-weight: 600; color: {COLORS['text_secondary']};">
                        {'🟢 Online' if not st.session_state.get('offline_mode', False) else '🔴 Offline'}
                    </span>
                </span>
                <span style="font-size: 0.8rem; color: {COLORS['text_muted']};">
                    v3.0
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_metric_card(label, value, subtitle="", icon="📊", color=None):
    """Render a styled metric card"""
    color = color or COLORS["primary"]
    st.markdown(f"""
    <div style="background: {COLORS['bg_primary']}; 
         border-radius: 12px; 
         padding: 1.25rem; 
         border: 2px solid {COLORS['border']};
         box-shadow: 0 2px 8px {COLORS['shadow']};
         transition: all 0.3s ease;
         height: 100%;">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
            <span style="font-size: 1.5rem;">{icon}</span>
            <span style="color: {COLORS['text_secondary']}; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">
                {label}
            </span>
        </div>
        <div style="font-size: 2rem; font-weight: 800; color: {COLORS['text_primary']}; margin-bottom: 0.25rem;">
            {value}
        </div>
        <div style="color: {COLORS['text_muted']}; font-size: 0.75rem;">
            {subtitle}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_status_badge(status, size="small"):
    """Render a status badge with theme colors"""
    color = get_status_color(status)
    size_class = "small" if size == "small" else "large"
    font_size = "0.7rem" if size == "small" else "0.9rem"
    padding = "0.25rem 0.75rem" if size == "small" else "0.5rem 1.25rem"
    
    return f"""
    <span style="background: {color}; 
         color: {COLORS['text_light'] if status.upper() in ['DISMISSED', 'CRITICAL', 'OFFLINE'] else COLORS['text_primary']};
         padding: {padding};
         border-radius: 20px;
         font-size: {font_size};
         font-weight: 700;
         text-transform: uppercase;
         letter-spacing: 0.05em;
         display: inline-block;">
        {status.upper()}
    </span>
    """

def render_pill(text, color="#3C7A69", text_color="#FFFFFF", size="small"):
    """Render a generic inline HTML pill/badge"""
    font_size = "0.7rem" if size == "small" else "0.9rem"
    padding = "0.25rem 0.75rem" if size == "small" else "0.5rem 1.25rem"
    
    return f"""
    <span style="background: {color}; 
         color: {text_color};
         padding: {padding};
         border-radius: 20px;
         font-size: {font_size};
         font-weight: 700;
         text-transform: uppercase;
         letter-spacing: 0.05em;
         display: inline-block;
         margin: 0 0.2rem;">
        {text}
    </span>
    """

def render_section_header(title, description=None, icon="📋"):
    """Render a section header with theme styling"""
    st.markdown(f"""
    <div style="margin: 2rem 0 1.25rem 0; padding-bottom: 0.75rem; border-bottom: 3px solid {COLORS['primary_light']};">
        <h3 style="color: {COLORS['text_primary']}; margin: 0; display: flex; align-items: center; gap: 0.75rem; font-size: 1.25rem;">
            <span style="font-size: 1.5rem;">{icon}</span> 
            {title}
        </h3>
        {f'<p style="color: {COLORS["text_secondary"]}; margin: 0.25rem 0 0 0; font-size: 0.9rem;">{description}</p>' if description else ''}
    </div>
    """, unsafe_allow_html=True)

def render_alert(message, type="info"):
    """Render a themed alert"""
    colors = {
        "info": (COLORS["bg_secondary"], COLORS["primary"]),
        "success": (COLORS["bg_secondary"], COLORS["secondary"]),
        "warning": (COLORS["bg_secondary"], COLORS["primary_light"]),
        "error": (COLORS["bg_secondary"], COLORS["primary_dark"]),
    }
    bg, border = colors.get(type, colors["info"])
    
    st.markdown(f"""
    <div style="background: {bg}; 
         border-left: 4px solid {border};
         padding: 1rem 1.25rem;
         border-radius: 8px;
         margin: 0.75rem 0;
         color: {COLORS['text_primary']};">
        {message}
    </div>
    """, unsafe_allow_html=True)

def render_green_button(text, key=None):
    """Render a themed button"""
    return st.button(text, key=key, use_container_width=True)

def render_metric_row(metrics):
    """Render a row of metric cards"""
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics):
        with col:
            render_metric_card(
                label=metric.get("label", ""),
                value=metric.get("value", ""),
                subtitle=metric.get("subtitle", ""),
                icon=metric.get("icon", "📊"),
                color=metric.get("color", COLORS["primary"])
            )