#E:\GL_AI\src\ui\components\maps.py
import folium
import hashlib
import streamlit as st
from streamlit_folium import st_folium
import os


def render_monitoring_map(geo_events=None, width=1200, height=500, 
                          active_layers=None, time_days=30, min_severity="MEDIUM",
                          center_override=None, zoom_override=None):
    """
    Renders a military-grade GIS monitoring map with interactive layers.
    """
    if active_layers is None:
        active_layers = ["fire", "deforestation", "logging", "incident", "correlated_threat"]

    if geo_events is None:
        geo_events = {}

    # Center on Hazara Division (Abbottabad Region) or use override
    map_center = center_override if center_override else [34.1689, 73.2215]
    map_zoom = zoom_override if zoom_override else 9
    
    m = folium.Map(
        location=map_center, 
        zoom_start=map_zoom, 
        control_scale=True,
        tiles="OpenStreetMap" # Restored base layer
    )
    # Add strict Hazara Operational Boundary overlay via explicit GeoJSON
    geojson_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "hazara_boundary.geojson")
    if os.path.exists(geojson_path):
        folium.GeoJson(
            geojson_path,
            name="Hazara Operations Box",
            tooltip="Hazara Division Operational Zone",
            style_function=lambda x: {'color': '#2563eb', 'weight': 2, 'fillOpacity': 0.05}
        ).add_to(m)
    
    # Time context overlay
    title_html = f'''
             <h3 align="center" style="font-size:16px; margin-top:0;">
             <b>Active Intelligence Feed: Last {time_days} Days</b>
             </h3>
             '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # --- GIS Layer Setup ---
    layer_fire = folium.FeatureGroup(name="🔥 Fire Alerts", show="fire" in active_layers)
    layer_def = folium.FeatureGroup(name="🌳 Deforestation", show="deforestation" in active_layers)
    layer_log = folium.FeatureGroup(name="⚠️ Illegal Logging", show="logging" in active_layers)
    layer_trns = folium.FeatureGroup(name="🚚 Transport", show="transport" in active_layers)
    layer_inc = folium.FeatureGroup(name="🚨 Recent Incidents", show="incident" in active_layers)
    layer_heat = folium.FeatureGroup(name="🌡️ Intensity Heatmap", show="heatmap" in active_layers)
    layer_corr = folium.FeatureGroup(name="🚨 FUSION THREATS", show="correlated_threat" in active_layers)
    layer_future = folium.FeatureGroup(name="🔮 Future Risk Heatmap", show="future_risk" in active_layers)
    layer_prop = folium.FeatureGroup(name="🔮 30-Day Propensity Zones", show="propensity_forecast" in active_layers)

    # Initialize Tactical Marker Clusters for separate data
    from folium.plugins import MarkerCluster, HeatMap
    mc_fire = MarkerCluster().add_to(layer_fire)
    mc_def = MarkerCluster().add_to(layer_def)
    mc_log = MarkerCluster().add_to(layer_log)
    mc_trns = MarkerCluster().add_to(layer_trns)
    mc_inc = MarkerCluster().add_to(layer_inc)
    mc_corr = MarkerCluster().add_to(layer_corr)
    mc_prop = MarkerCluster().add_to(layer_prop)
    
    # Heatmap data collection (lat, lon, intensity)
    heat_data = []

    def get_truth_profile(ev):
        lineage = ev.details.get("lineage", "")
        # Forced Truth Routing
        if "FUSED" in lineage or "->" in lineage or ev.type == "correlated_threat":
            return "CORRELATED", 1.0, "#ef4444" # Red
        elif ev.source in ["NASA-FIRMS", "GFW-Integrated", "GFW-SATELLITE", "Field-Alert"]:
            return "TACTICAL", 0.6, "#f59e0b" # Orange
        else:
            return "ANOMALOUS", 0.3, "#64748b" # Gray

    def build_popup_html(title, ev):
        score = ev.details.get("confidence_score", 0.6)
        recall = ev.details.get("system_recall_est", 1.0)
        # Truth-Aware Recall (Now verifiable)
        recall_display = f"{int(recall*100)}% (Verifiable Performance)" if recall > 0.0 else "0% (Zero Detection)"
        lineage = ev.details.get("lineage", ev.source)
        
        # Reasoning Metadata
        narrative = ev.details.get("strategic_narrative", "Individual signal - no regional fusion.")
        detected_utc = ev.timestamp.strftime('%Y-%m-%d %H:%M UTC')
        limitations = ev.details.get("limitations", "Single-source observation point")
        
        # Cluster Metrics
        cluster_size = ev.details.get("cluster_size")
        sensor_div = ev.details.get("sensor_diversity")
        
        cluster_html = f"""
            <div style='background: #f1f5f9; padding: 6px; border-radius: 4px; margin: 4px 0;'>
                <b>CLUSTER SIZE:</b> {cluster_size} Signals<br/>
                <b>SENSOR DIVERSITY:</b> {sensor_div} Sources
            </div>
        """ if cluster_size else ""
        
        # Carbon Risk (Milestone 2)
        carbon = ev.details.get("carbon_risk", {})
        has_carbon = isinstance(carbon, dict) and len(carbon) > 0
        carbon_html = f"""
            <div style='background: #f0fdf4; border: 1px solid #10b981; padding: 10px; border-radius: 8px; margin: 10px 0;'>
                <b style='color: #10b981; font-size: 12px;'>🌍 CARBON SEQUESTRATION AT RISK</b><br/>
                <span style='font-size: 16px; font-weight: bold;'>{carbon.get('total_mtco2_risk', 0):,} MTCO2</span><br/>
                <span style='font-size: 11px; color: #166534;'>
                    Biomass: {carbon.get('biomass_loss', 0):,} | 
                    Annual Lost: {carbon.get('sequestration_lost', 0):,}<br/>
                    Est. Area: {carbon.get('area_estimate_ha', 0):,} ha
                </span>
            </div>
        """ if has_carbon else ""
        
        return f"""
        <div style='min-width: 260px; font-size: 13px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.4; color: #1e293b; padding: 5px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <b style='color:{get_truth_profile(ev)[2]}; font-size: 14px;'>{title}</b>
                <span style='background: #e2e8f0; padding: 2px 6px; border-radius: 10px; font-size: 10px;'>{ev.severity}</span>
            </div>
            <hr style='margin:4px 0; border: 0; border-top: 1px solid #e2e8f0;'>
            
            <b>ID:</b> <code>{ev.id}</code><br/>
            <b>SOURCE:</b> {ev.source}<br/>
            <b>DETECTED:</b> {detected_utc}<br/>
            <b>📍 LOCAL AREA:</b> <b style='color: #2563eb;'>{ev.details.get('sector_name', 'Hazara Division')}</b><br/>
            
            <div style='margin: 10px 0; color: #334155; font-style: italic; border-left: 3px solid #3b82f6; padding-left: 8px; background: #f8fafc; padding: 8px;'>
                "{narrative}"
            </div>
            
            {cluster_html}
            {carbon_html}
            
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 5px;'>
                <div>
                    <span style='font-size: 10px; color: #64748b;'>CONFIDENCE</span><br/>
                    <b>{int(score*100)}%</b>
                </div>
                <div>
                    <span style='font-size: 10px; color: #64748b;'>SYSTEM RECALL</span><br/>
                    <b>{recall_display}</b>
                </div>
            </div>
            
            <hr style='margin:10px 0; border: 0; border-top: 1px solid #e2e8f0;'>
            <div style='font-size: 11px; color: #94a3b8;'>LINEAGE: {lineage}</div>
        </div>
        """

    # 1. NASA FIRMS Fire Markers (Pulsing Fire Emoji)
    if "fire" in active_layers:
        for ev in geo_events.get("fire", []):
            truth_score, _, hex_color = get_truth_profile(ev)
            
            # Milestone 4.5: UNIFIED VERIFIED ICON (Proximity + Decision Sync)
            coord_key = f"{round(ev.lat, 2)}_{round(ev.lon, 2)}"
            is_verified = (st.session_state.operator_decisions.get(coord_key) == "VERIFIED" or 
                           st.session_state.operator_decisions.get(ev.id) == "VERIFIED" or
                           "VERIFIED" in getattr(ev, 'confidence', '').upper())
            
            if is_verified:
                icon_char, icon_size, anchor = "🛡️", "34px", (17,17)
            else:
                icon_char, icon_size, anchor = "🔥", "24px", (15,15)
                
            # Create a pulsing halo effect based on truth color
            icon_html = f'''
                <div style="
                    font-size: {icon_size};
                    text-shadow: 0 0 10px {hex_color};
                    animation: {'pulse 1s infinite' if is_verified else 'pulse 2s infinite'};
                    display: flex;
                    justify-content: center;
                    align-items: center;
                ">{icon_char}</div>
            '''
            folium.Marker(
                location=[ev.lat, ev.lon],
                popup=build_popup_html("🛡️ VERIFIED FIRE" if is_verified else "🔥 NASA THERMAL ANOMALY", ev),
                icon=folium.DivIcon(html=icon_html, icon_anchor=anchor)
            ).add_to(mc_fire)

            # --- INDIVIDUAL FIRE SPREAD VECTORS (PHASE 12.16) ---
            spread_risk = ev.details.get("spread_risk_index", 0)
            if spread_risk > 0.15: # Lower threshold to ensure visibility in simulation
                wind_deg = ev.details.get("wind_deg", 0)
                import math
                rad = math.radians(90 - wind_deg)
                end_lat = ev.lat + (0.05 * math.sin(rad))
                end_lon = ev.lon + (0.05 * math.cos(rad))
                
                folium.PolyLine(
                    locations=[[ev.lat, ev.lon], [end_lat, end_lon]],
                    color="#ef4444", weight=2, opacity=0.7, dash_array='4, 8',
                    tooltip=f"FIRE SPREAD VECTOR ({int(spread_risk*100)}% Risk)"
                ).add_to(mc_fire)
                
                folium.CircleMarker(
                    location=[end_lat, end_lon], radius=2, color="#ef4444", 
                    fill=True, fill_color="#ef4444"
                ).add_to(mc_fire)
            heat_data.append([ev.lat, ev.lon, 1.0])

    # 2. GFW Deforestation Markers (Stunning Tree Emoji)
    if "deforestation" in active_layers:
        for ev in geo_events.get("deforestation", []):
            _, _, hex_color = get_truth_profile(ev)
            
            coord_key = f"{round(ev.lat, 2)}_{round(ev.lon, 2)}"
            is_verified = (st.session_state.operator_decisions.get(coord_key) == "VERIFIED" or 
                           st.session_state.operator_decisions.get(ev.id) == "VERIFIED" or
                           "VERIFIED" in getattr(ev, 'confidence', '').upper())
            
            icon_char, icon_size = ("🛡️", "34px") if is_verified else ("🌳", "22px")
            
            icon_html = f'<div style="font-size: {icon_size}; text-shadow: 0 0 8px {hex_color};"> {icon_char}</div>'
            folium.Marker(
                location=[ev.lat, ev.lon],
                popup=build_popup_html("🛡️ VERIFIED AREA" if is_verified else "🌳 DEFORESTATION DETECTED", ev),
                icon=folium.DivIcon(html=icon_html, icon_anchor=(17,17) if is_verified else (11,11))
            ).add_to(mc_def)
            heat_data.append([ev.lat, ev.lon, 0.6])

    # 3. Illegal Logging Markers (Wood Log Emoji)
    if "logging" in active_layers:
        for ev in geo_events.get("logging", []):
            _, _, hex_color = get_truth_profile(ev)
            
            coord_key = f"{round(ev.lat, 2)}_{round(ev.lon, 2)}"
            is_verified = (st.session_state.operator_decisions.get(coord_key) == "VERIFIED" or 
                           st.session_state.operator_decisions.get(ev.id) == "VERIFIED" or
                           "VERIFIED" in getattr(ev, 'confidence', '').upper())
            
            icon_char, icon_size = ("🛡️", "34px") if is_verified else ("🪵", "22px")
            
            icon_html = f'<div style="font-size: {icon_size}; text-shadow: 0 0 8px {hex_color};"> {icon_char}</div>'
            folium.Marker(
                location=[ev.lat, ev.lon],
                popup=build_popup_html("🛡️ VERIFIED LOGGING" if is_verified else "⚠️ SUSPECTED ILLEGAL LOGGING", ev),
                icon=folium.DivIcon(html=icon_html, icon_anchor=(17,17) if is_verified else (11,11))
            ).add_to(mc_log)

    # 4. Transportation Marks (Truck Emoji)
    if "transport" in active_layers:
        for ev in geo_events.get("transport", []):
            _, _, hex_color = get_truth_profile(ev)
            
            coord_key = f"{round(ev.lat, 2)}_{round(ev.lon, 2)}"
            is_verified = (st.session_state.operator_decisions.get(coord_key) == "VERIFIED" or 
                           st.session_state.operator_decisions.get(ev.id) == "VERIFIED" or
                           "VERIFIED" in getattr(ev, 'confidence', '').upper())
            
            icon_char, icon_size = ("🛡️", "34px") if is_verified else ("🚚", "22px")
            
            icon_html = f'<div style="font-size: {icon_size}; text-shadow: 0 0 8px {hex_color};"> {icon_char}</div>'
            folium.Marker(
                location=[ev.lat, ev.lon],
                popup=build_popup_html("🛡️ VERIFIED SHIPMENT" if is_verified else "🚚 SUSPICIOUS TRANSPORT", ev),
                icon=folium.DivIcon(html=icon_html, icon_anchor=(17,17) if is_verified else (11,11))
            ).add_to(mc_trns)

    # 5. RECENT INCIDENTS (Bullhorn for Field Reports, Shield for Verified Intel)
    if "incident" in active_layers:
        for ev in geo_events.get("incident", []):
            truth_score, _, hex_color = get_truth_profile(ev)
            
            # Milestone 4.5: UNIFIED VERIFIED ICON (Proximity + Decision Sync)
            coord_key = f"{round(ev.lat, 2)}_{round(ev.lon, 2)}"
            is_verified = (st.session_state.operator_decisions.get(coord_key) == "VERIFIED" or 
                           st.session_state.operator_decisions.get(ev.id) == "VERIFIED" or
                           "VERIFIED" in getattr(ev, 'confidence', '').upper())
            
            icon_char = "🛡️" if is_verified else "📢"
            size = "34px" if is_verified else "22px"
            
            icon_html = f'''
                <div style="
                    font-size: {size}; 
                    text-shadow: 0 0 10px {hex_color};
                    animation: {'pulse 1s infinite' if is_verified else 'none'};
                ">{icon_char}</div>
            '''
            folium.Marker(
                location=[ev.lat, ev.lon],
                popup=build_popup_html("🛡️ VERIFIED INCIDENT" if is_verified else "🚨 ACTIVE FIELD REPORT", ev),
                icon=folium.DivIcon(html=icon_html, icon_anchor=(17,17) if is_verified else (11,11))
            ).add_to(mc_inc)

            # --- RENDER SPREAD VECTORS FOR INCIDENTS (PHASE 12.11) ---
            spread_risk = ev.details.get("spread_risk_index", 0)
            if spread_risk > 0.35:
                wind_deg = ev.details.get("wind_deg", 0)
                import math
                rad = math.radians(90 - wind_deg)
                end_lat = ev.lat + (0.05 * math.sin(rad))
                end_lon = ev.lon + (0.05 * math.cos(rad))
                folium.PolyLine(
                    locations=[[ev.lat, ev.lon], [end_lat, end_lon]],
                    color="#ef4444", weight=3, opacity=0.8, dash_array='5, 10',
                    tooltip=f"PREDICTED SPREAD VECTOR ({int(spread_risk*100)}% Risk)"
                ).add_to(mc_inc)
                folium.CircleMarker(
                    location=[end_lat, end_lon], radius=3, color="#ef4444", 
                    fill=True, fill_color="#ef4444"
                ).add_to(mc_inc)

    # 6. CORRELATED THREATS (Target Emoji + Impact Zone + Spread Vector)
    if "correlated_threat" in active_layers:
        for ev in geo_events.get("correlated_threat", []):
            truth_score, _, hex_color = get_truth_profile(ev)
            
            # Milestone 4.5: UNIFIED VERIFIED ICON (Proximity + Decision Sync)
            coord_key = f"{round(ev.lat, 2)}_{round(ev.lon, 2)}"
            is_verified = (st.session_state.operator_decisions.get(coord_key) == "VERIFIED" or 
                           st.session_state.operator_decisions.get(ev.id) == "VERIFIED" or
                           "VERIFIED" in getattr(ev, 'confidence', '').upper())
            
            icon_char = "🛡️" if is_verified else "🎯"
            ring_color = "#10b981" if is_verified else "#ef4444" # Green for verified
            
            icon_html = f'''
                <div style="
                    font-size: {'34px' if is_verified else '26px'}; 
                    text-shadow: 0 0 15px {hex_color};
                    animation: {'pulse 1s infinite' if is_verified else 'none'};
                ">{icon_char}</div>
            '''
            
            # Impact Zone Circle (10km radius)
            folium.Circle(
                location=[ev.lat, ev.lon],
                radius=10000, 
                color=ring_color,
                weight=2 if is_verified else 1,
                fill=True,
                fill_opacity=0.2 if is_verified else 0.1,
                tooltip=f"Verified Control Zone" if is_verified else f"Intelligence Hot-Zone (10km Cluster Radius)"
            ).add_to(mc_corr)
            
            # Milestone 4: Spread Vector visualization (Arrows)
            spread_risk = ev.details.get("spread_risk_index", 0)
            if spread_risk > 0.35: # Lowered threshold slightly
                wind_deg = ev.details.get("wind_deg", 0)
                # Calculate arrow endpoint (approx 5km distance in wind direction)
                # 0.05 deg ~= 5.5km
                import math
                rad = math.radians(90 - wind_deg) # Convert bearing to cartesian
                end_lat = ev.lat + (0.05 * math.sin(rad))
                end_lon = ev.lon + (0.05 * math.cos(rad))
                
                folium.PolyLine(
                    locations=[[ev.lat, ev.lon], [end_lat, end_lon]],
                    color="#ef4444",
                    weight=3,
                    opacity=0.8,
                    dash_array='5, 10',
                    tooltip=f"PREDICTED SPREAD VECTOR ({int(spread_risk*100)}% Risk)"
                ).add_to(mc_corr)
                
                # Arrow head (dot at end)
                folium.CircleMarker(
                    location=[end_lat, end_lon],
                    radius=3,
                    color="#ef4444",
                    fill=True
                ).add_to(mc_corr)
            
            folium.Marker(
                location=[ev.lat, ev.lon],
                popup=build_popup_html("🛡️ VERIFIED INCIDENT" if is_verified else "🚨 HIGH PROBABILITY THREAT", ev),
                icon=folium.DivIcon(html=icon_html, icon_anchor=(15,15) if is_verified else (13,13))
            ).add_to(mc_corr)

    # 7. 30-DAY THREAT PROPENSITY FORECASTS
    if "propensity_forecast" in active_layers:
        for ev in geo_events.get("propensity_forecast", []):
            icon_html = f'<div style="font-size: 26px; text-shadow: 0 0 10px #8b5cf6;">🔮</div>'
            score = ev.details.get("vulnerability_score", 50)
            
            folium.Circle(
                location=[ev.lat, ev.lon],
                radius=score * 50, # Dynamic radius scaling based on risk multiplier
                color="#8b5cf6", # Predictive purple
                weight=2,
                fill=True,
                fill_opacity=0.15,
                tooltip=f"Propensity Vulnerability Zone (Risk Multiplier: {score})"
            ).add_to(mc_prop)

            folium.Marker(
                location=[ev.lat, ev.lon],
                popup=build_popup_html("🔮 PREDICTED FUTURE SPREAD THREAT", ev),
                icon=folium.DivIcon(html=icon_html, icon_anchor=(13,13))
            ).add_to(mc_prop)

    # --- Feature Layer Finalization ---
    # Merge layers to map
    for layer in [layer_fire, layer_def, layer_log, layer_trns, layer_inc, layer_corr, layer_future, layer_prop]:
        layer.add_to(m)
    
    # Milestone 3: Future Risk Layer
    if "future_risk" in active_layers:
        try:
            from data.predictive_engine import predictive_engine
            # Use current events as context for predictions
            all_list = []
            for k in geo_events: all_list.extend(geo_events[k])
            
            risk_nodes = predictive_engine.generate_risk_nodes(all_list, weather_forecast=[])
            future_heat_data = [[n['lat'], n['lon'], n['risk_score']] for n in risk_nodes]
            
            if future_heat_data:
                HeatMap(future_heat_data, radius=30, blur=20, gradient={0.4: 'yellow', 0.65: 'orange', 0.9: 'red'}).add_to(layer_future)
                
            for node in risk_nodes:
                folium.CircleMarker(
                    location=[node['lat'], node['lon']],
                    radius=5,
                    color="purple",
                    fill=True,
                    popup=f"<b>30-DAY RISK NODE</b><br/>Score: {node['risk_score']}<br/>{node['rationale']}"
                ).add_to(layer_future)
        except Exception as e:
            st.error(f"Predictive Layer Error: {e}")
    
    # Heatmap is a separate visual layer, lowered opacity so it doesn't distract
    if "heatmap" in active_layers and heat_data:
        HeatMap(heat_data, radius=15, blur=15, min_opacity=0.3, max_val=0.7).add_to(layer_heat)
        layer_heat.add_to(m)

    # Build-in Folium Layer Control (optional visibility toggle in map)
    folium.LayerControl(position='topright', collapsed=False).add_to(m)

    # Combined key for re-rendering triggers
    # Milestone 4.5: ADDING DECISIONS TO KEY (Flewing Fix)
    decisions_hash = hashlib.md5(str(st.session_state.get("operator_decisions", {})).encode()).hexdigest()[:8]
    map_key = f"gis_map_stable_{hash(str(active_layers))}_{time_days}_{min_severity}_{decisions_hash}"
    
    return st_folium(m, width=width, height=height, key=map_key)


def render_map_legend():
    """
    Renders a professional, external map reading guide below the map.
    """
    st.markdown("""
    <div style="background-color: #f9fafb; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; margin-top: 20px;">
        <h4 style="margin-top: 0; color: #111827;">🗺️ Confidence-Based Validation Guide</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 15px;">
            <div>
                <p style="margin: 5px 0;">🔴 <b style="color: #ef4444;">Red Halo</b> — VERIFIED (Multi-source)</p>
                <p style="margin: 5px 0;">🟠 <b style="color: #f59e0b;">Orange Halo</b> — TACTICAL (Single-source)</p>
                <p style="margin: 5px 0;">⚪ <b style="color: #64748b;">Gray Halo</b> — ANOMALOUS (Unverified / Noise)</p>
            </div>
            <div>
                <p style="margin: 5px 0;">🔥 <b style="color: #111827;">Fire / Leaf</b> — Raw API Hit</p>
                <p style="margin: 5px 0;">⚠️ <b style="color: #111827;">Triangle / Truck / 📢</b> — Logging / Transport / Field Report</p>
                <p style="margin: 5px 0;">🔵 <b style="color: #2563eb;">Blue Polygon</b> — Verified Hazara GPS Topology</p>
            </div>
        </div>
        <hr style="margin: 15px 0; border: 0; border-top: 1px solid #d1d5db;">
        <p style="margin: 0; font-size: 0.9rem; color: #6b7280; font-style: italic;">
            Data Governance: Every intelligence point strictly inherits its visual color-band from its verified origin source. Click any marker to view its unalterable cryptographic source ID and Mathematical Truth Score.
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_heatmap(heatmap_data, width=1200, height=400):
    """
    Renders the deforestation risk heatmap with division markers.
    """
    if not heatmap_data or not heatmap_data.get("heatmap_points"):
        st.info("No heatmap data available.")
        return

    from folium.plugins import HeatMap

    pm = folium.Map(location=[34.5, 72.5], zoom_start=7, tiles="CartoDB dark_matter")
    HeatMap(heatmap_data["heatmap_points"], radius=25, blur=15).add_to(pm)

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

    st_folium(pm, width=width, height=height, key="heatmap_map")
