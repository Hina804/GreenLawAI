# ui/components/__init__.py
# Canonical component library — mirrors ui/components.py
import streamlit as st
from datetime import datetime
COLORS = {
    # surfaces
    "bg_card":       "#FFFFFF",
    "bg_secondary":  "#F7F6F4",
    "bg_hover":      "#EFEEEB",
    "bg_page":       "#FAFAF9",

    # borders
    "border":        "#C9C6BF",
    "border_light":  "#CFCDC7",
    "border_strong": "#A8A59D",

    # text
    "text_primary":   "#1A1A18",
    "text_secondary": "#3D3C39",
    "text_muted":     "#8B8983",
    "text_light":     "#FFFFFF",

    # radius
    "radius": "12px",
    "radius_sm": "8px",

    # accents (used by status badges etc.)
    "accent":      "#161614",
    "green":       "#2F6B45",
    "green_bg":    "#EAF3EC",
    "amber":       "#B6791E",
    "amber_bg":    "#FBF3E6",
    "red":         "#A23B2E",
    "red_bg":      "#FBEDEA",
}

STATUS = {
    "VERIFIED":   "#2F6B45",
    "DISMISSED":  "#A23B2E",
    "PENDING":    "#B6791E",
    "DISPATCHED": "#161614",
    "OFFLINE":    "#8B8983",
}

def get_color(c):
    return COLORS.get(c, "#1A1A18")

def get_status_color(s):
    return STATUS.get(s.upper(), "#8B8983")
# ── Session-state guard ──────────────────────────────────────────────────────

def _init_session():
    if "active_page_index" not in st.session_state:
        st.session_state.active_page_index = 0


# ── Header ────────────────────────────────────────────────────────────────────

def render_header():
    """Render clean header — exactly like screenshot"""
    _init_session()
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;
             padding-bottom: 0.5rem; border-bottom: 1px solid {COLORS['border']};">
            <div>
                <h1 style="font-size: 1.5rem; font-weight: 600; margin: 0; color: {COLORS['text_primary']};">
                    GreenLawAI
                </h1>
                <span style="color: {COLORS['text_muted']}; font-size: 0.85rem; font-weight: 400;">
                    Unified Intelligence Platform
                </span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 0.8rem; color: {COLORS['text_muted']};">
                    {datetime.now().strftime('%H:%M')}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Navigation ────────────────────────────────────────────────────────────────

def render_navigation():
    """Render clean pill-style navigation scoped inside .nav-container."""
    _init_session()

    pages = [
        "Dashboard", "Chat", "Legal", "Judiciary",
        "Monitoring", "Predict", "Operations", "Citizen", "Permit"
    ]

    st.markdown(f"""
    <div style="margin-bottom: 0.5rem;">
        <span style="font-size: 0.75rem; color: {COLORS['text_muted']}; text-transform: uppercase;
             letter-spacing: 0.05em; font-weight: 500;">
            Select Intelligence Module
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Wrap in .nav-container so CSS can scope styles to nav buttons only
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    cols = st.columns(len(pages))
    for idx, col in enumerate(cols):
        page = pages[idx]
        is_active = st.session_state.active_page_index == idx
        if col.button(
            page,
            key=f"nav_{idx}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_page_index = idx
            st.session_state["_nav_override"] = page
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)



# ── Page / Section headers ────────────────────────────────────────────────────

def render_page_header(title, description=""):
    """Backward-compat alias for render_section_header."""
    render_section_header(title, description or None)


def render_section_header(title, description=None):
    """Render clean section header."""
    desc_html = (
        f'<p style="color: {COLORS["text_muted"]}; font-size: 0.85rem; margin: 0.1rem 0 0 0;">'
        f'{description}</p>'
        if description else ""
    )
    st.markdown(f"""
    <div style="margin: 0 0 1rem 0;">
        <h2 style="font-size: 1.1rem; font-weight: 600; color: {COLORS['text_primary']}; margin: 0;">
            {title}
        </h2>
        {desc_html}
    </div>
    """, unsafe_allow_html=True)


def render_section_title(title, icon=None):
    """Backward-compat: thin section title with optional icon."""
    icon_html = f"<span style='margin-right:0.3rem;'>{icon}</span>" if icon else ""
    st.markdown(f"""
    <div style="margin: 1.25rem 0 0.5rem 0;">
        <h3 style="font-size: 0.95rem; font-weight: 600; color: {COLORS['text_primary']};
                   margin: 0; display: flex; align-items: center;">
            {icon_html}{title}
        </h3>
    </div>
    """, unsafe_allow_html=True)


# ── Metric card ───────────────────────────────────────────────────────────────

def render_metric_card(label, value, subtitle="", border=True):
    """Render clean metric card."""
    border_style = f"border: 1px solid {COLORS['border']};" if border else ""
    radius = COLORS.get("radius", "6px")
    st.markdown(f"""
    <div style="background: {COLORS['bg_card']};
         border-radius: {radius};
         padding: 0.75rem 1rem;
         {border_style}">
        <div style="font-size: 0.75rem; color: {COLORS['text_muted']}; font-weight: 500;
                    text-transform: uppercase; letter-spacing: 0.03em;">
            {label}
        </div>
        <div style="font-size: 1.5rem; font-weight: 600; color: {COLORS['text_primary']}; margin: 0.1rem 0;">
            {value}
        </div>
        <div style="font-size: 0.75rem; color: {COLORS['text_muted']};">
            {subtitle}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Status badge ──────────────────────────────────────────────────────────────

def render_status_badge(status):
    """Render inline status badge (subtle pill)."""
    color = get_status_color(status)
    dark_text_statuses = {"CRITICAL", "DISMISSED", "OFFLINE"}
    text_color = COLORS["text_light"] if status.upper() in dark_text_statuses else COLORS["text_primary"]
    st.markdown(f"""
    <span style="display: inline-block;
         background: {color};
         color: {text_color};
         padding: 0.1rem 0.6rem;
         border-radius: 3px;
         font-size: 0.7rem;
         font-weight: 500;
         text-transform: uppercase;
         letter-spacing: 0.03em;">
        {status}
    </span>
    """, unsafe_allow_html=True)


# ── Offline / empty states ────────────────────────────────────────────────────

def render_offline_banner():
    """Render offline mode banner."""
    radius = COLORS.get("radius", "6px")
    st.markdown(f"""
    <div style="background: {COLORS['bg_secondary']};
         border: 1px solid {COLORS['border']};
         border-radius: {radius};
         padding: 0.5rem 1rem;
         margin: 0.5rem 0 1rem 0;
         display: flex;
         align-items: center;
         gap: 0.5rem;">
        <span style="color: {COLORS['text_muted']}; font-size: 1rem;">⚪</span>
        <span style="color: {COLORS['text_secondary']}; font-size: 0.85rem;">
            Offline Mode — Using cached responses
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_empty_state(message="No messages yet"):
    """Render centred empty-state block."""
    st.markdown(f"""
    <div style="text-align: center; padding: 3rem 1rem;">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem; opacity: 0.3;">💬</div>
        <div style="color: {COLORS['text_secondary']}; font-size: 1rem; font-weight: 500;">
            {message}
        </div>
        <div style="color: {COLORS['text_muted']}; font-size: 0.85rem; margin-top: 0.25rem;">
            Try asking about forest law, fire risk, or a permit request
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Chat ──────────────────────────────────────────────────────────────────────

def render_chat_message(content, role="assistant"):
    """Render a single chat bubble."""
    bg = COLORS["bg_hover"] if role == "user" else COLORS["bg_secondary"]
    radius = COLORS.get("radius", "6px")
    st.markdown(f"""
    <div style="background: {bg};
         border-radius: {radius};
         padding: 0.75rem 1rem;
         margin-bottom: 0.5rem;
         border: 1px solid {COLORS['border_light']};">
        <div style="color: {COLORS['text_primary']}; font-size: 0.9rem; line-height: 1.5;">
            {content}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Utility ───────────────────────────────────────────────────────────────────

def render_divider():
    """Render a thin horizontal rule."""
    st.markdown(f"""
    <hr style="border: none; border-top: 1px solid {COLORS['border_light']}; margin: 0.75rem 0;">
    """, unsafe_allow_html=True)


def render_chat_input_placeholder():
    """Render a static chat-input hint (backward compat)."""
    st.markdown(f"""
    <div style="border-top: 1px solid {COLORS['border']}; padding-top: 0.75rem; margin-top: 0.5rem;">
        <div style="color: {COLORS['text_muted']}; font-size: 0.8rem; font-weight: 400;">
            Ask about forest laws, risks, or request an action
        </div>
    </div>
    """, unsafe_allow_html=True)
