"""
GreenLawAI Unified Portal — Metric & KPI Components
Reusable cards for fire stats, weather, and forecast display.
"""
import streamlit as st


def render_fire_stats(fire_stats):
    """Render NASA FIRMS fire statistics as 3-column KPI cards."""
    if not fire_stats:
        return
    st.write("🛰️ **NASA FIRMS Real-Time Fire Report**")
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Fires (24h)", fire_stats.get('total_fires', 0))
    c2.metric("High Confidence", fire_stats.get('high_confidence', 0))
    avg_b = fire_stats.get('avg_brightness', 0)
    c3.metric("Avg Intensity", f"{round(avg_b, 1)} K" if fire_stats.get('total_fires', 0) > 0 else "0 K")


def render_weather_stats(weather):
    """Render local weather and fire risk as 4-column KPI cards."""
    if not weather:
        return
    st.write(f"🌤️ **Local Weather & Fire Risk ({weather.get('city', 'Regional')})**")
    wc1, wc2, wc3, wc4 = st.columns(4)
    wc1.metric("Temperature",  f"{weather.get('temp', 'N/A')}°C")
    wc2.metric("Humidity",     f"{weather.get('humidity', 'N/A')}%")
    wc3.metric("Wind Speed",   f"{weather.get('wind_speed', 'N/A')} m/s")

    risk = weather.get('risk_index', 0)
    risk_color = "#A23B2E" if risk >= 60 else "#B6791E" if risk >= 30 else "#2F6B45"
    risk_label = "HIGH" if risk >= 60 else "MEDIUM" if risk >= 30 else "LOW"
    wc4.markdown(f"""
    <div style="background:#FFFFFF; padding:18px 20px; border-radius:12px;
                border:1.5px solid #C9C6BF; position:relative; overflow:hidden;
                box-shadow:0 1px 2px rgba(26,26,24,0.04);">
        <div style="position:absolute; left:0; top:0; bottom:0; width:3px;
                    background:{risk_color};"></div>
        <div style="font-size:0.66rem; color:#8B8983; font-weight:600;
                    text-transform:uppercase; letter-spacing:0.08em;">Fire Risk Index</div>
        <div style="font-size:1.8rem; font-weight:800; color:{risk_color}; margin:4px 0;">
            {risk}<span style="font-size:1rem;">/100</span>
        </div>
        <div style="font-size:0.75rem; font-weight:600; color:{risk_color};">{risk_label}</div>
    </div>
    """, unsafe_allow_html=True)
def render_forecast_cards(forecast, max_days=5):
    if not forecast:
        st.info("No forecast data available.")
        return
    cols = st.columns(max_days)
    for i, day in enumerate(forecast[:max_days]):
        with cols[i]:
            risk = day.get('fire_risk', 0)
            risk_color = "#A23B2E" if risk > 60 else "#2F6B45"
            st.markdown(f"""
            <div style="background:#FFFFFF; padding:16px; border-radius:12px;
                        text-align:center; border:1.5px solid #C9C6BF;
                        box-shadow:0 1px 2px rgba(26,26,24,0.04);">
                <div style="font-size:0.75rem; color:#8B8983; font-weight:600;
                            text-transform:uppercase; letter-spacing:0.05em;">
                    {day.get('date', '')[-5:]}
                </div>
                <div style="font-size:1.6rem; font-weight:800; color:#1A1A18; margin:6px 0;">
                    {day.get('temp', 'N/A')}°C
                </div>
                <div style="font-size:0.78rem; color:#5C5A56;">
                    {day.get('description', '')}
                </div>
                <hr style="border:none; border-top:1px solid #CFCDC7; margin:8px 0;">
                <div style="font-size:0.75rem; font-weight:600; color:{risk_color};">
                    Risk: {risk}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if day.get('note'):
                st.caption(day['note'])


def render_kpi_row(items):
    cols = st.columns(len(items))
    for i, item in enumerate(items):
        color = item.get('color', '#1A1A18')
        with cols[i]:
            st.markdown(f"""
            <div style="background:#FFFFFF; padding:18px 20px; border-radius:12px;
                        border:1.5px solid #C9C6BF; position:relative; overflow:hidden;
                        box-shadow:0 1px 2px rgba(26,26,24,0.04);">
                <div style="position:absolute; left:0; top:0; bottom:0; width:3px;
                            background:{color}; opacity:0.85;"></div>
                <div style="font-size:0.66rem; color:#8B8983; font-weight:600;
                            text-transform:uppercase; letter-spacing:0.08em;">
                    {item['label']}
                </div>
                <div style="font-size:1.8rem; font-weight:800; color:#1A1A18; margin:4px 0;">
                    {item['value']}
                </div>
                <div style="font-size:0.75rem; color:#8B8983;">
                    {item.get('subtitle', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)