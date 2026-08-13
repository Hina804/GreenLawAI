import streamlit as st
import folium
from streamlit_folium import st_folium
import asyncio
from src.agents.permit.decision_engine import PermitDecisionEngine

# Page config
st.set_page_config(page_title="Permit Intelligence", page_icon="🪪", layout="wide")

st.title("🪪 Forest Permit Intelligence System")
st.caption("AI-powered permit decision engine with real-time environmental validation")

permit_tab1, permit_tab2, permit_tab3, permit_tab4, permit_tab5 = st.tabs([
    "📝 Apply for Permit",
    "🔍 Check Status",
    "📋 My Permits",
    "⚖️ Permit Rules",
    "📊 Permit Analytics"
])

def run_decision_engine(request_data):
    # Synchronous wrapper for asyncio call
    engine = PermitDecisionEngine()
    return asyncio.run(engine.evaluate(request_data))

with permit_tab1:
    st.subheader("New Permit Application")
    
    # Step 1: Applicant Information
    with st.expander("👤 Applicant Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name *")
            cnic = st.text_input("CNIC Number *")
        with col2:
            father_name = st.text_input("Father's Name *")
            contact = st.text_input("Contact Number *")
    
    # Step 2: Location Details (with map)
    with st.expander("📍 Location Details", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            district = st.selectbox("District *", ["Abbottabad", "Mansehra", "Swat", "Haripur", "Batagram"])
            tehsil = st.text_input("Tehsil *")
            village = st.text_input("Village/Mouza *")
            khasra_number = st.text_input("Khasra Number *")
        with col2:
            st.write("**Select Location on Map**")
            # Folium map for coordinate picking
            m = folium.Map(location=[34.5, 73.0], zoom_start=8)
            st_folium(m, height=300)
            coordinates_input = st.text_input("Or enter coordinates (lat, lon)", placeholder="35.22, 72.48")
    
    # Step 3: Permit Request
    with st.expander("🌳 Permit Request Details", expanded=True):
        permit_type = st.selectbox("Permit Type *", [
            "Timber Extraction", "Firewood Collection", "Grazing", 
            "Transit Permit", "Non-Timber Forest Produce"
        ])
        
        species = []
        tree_count = 0
        purpose = ""
        duration = 30
        justification = ""
        
        if permit_type == "Timber Extraction":
            col1, col2 = st.columns(2)
            with col1:
                species = st.multiselect("Tree Species *", ["Deodar", "Chir", "Spruce", "Fir"])
                tree_count = st.number_input("Number of Trees *", min_value=1, max_value=50)
            with col2:
                purpose = st.selectbox("Purpose *", ["House Construction", "Commercial", "Furniture", "Other"])
                duration = st.number_input("Duration (days) *", min_value=1, max_value=365, value=30)
            
            justification = st.text_area("Justification *", placeholder="Explain why you need this permit...")
    
    # Step 4: Supporting Documents
    with st.expander("📎 Supporting Documents"):
        land_doc = st.file_uploader("Land Ownership Proof (PDF)", type=['pdf'])
        map_doc = st.file_uploader("Site Map/Sketch", type=['pdf', 'jpg', 'png'])
    
    # Step 5: Declaration
    with st.expander("📜 Declaration", expanded=True):
        no_violations = st.checkbox("I confirm no previous forest law violations *")
        accurate_info = st.checkbox("I confirm all information is accurate *")
    
    # Step 6: Submit with AI Validation
    if st.button("🚀 Submit for AI Review", type="primary"):
        if all([name, cnic, district, khasra_number, accurate_info, justification]):
            with st.spinner("Running environmental and legal validation..."):
                request_data = {
                    "applicant": {"name": name, "cnic": cnic},
                    "location": {"district": district, "khasra_number": khasra_number, "coordinates": coordinates_input},
                    "request": {
                        "permit_type": permit_type, "species": species, "tree_count": tree_count, 
                        "purpose": purpose, "duration": duration, "justification": justification,
                        "application_date": "2026-04-16"
                    }
                }
                
                decision = run_decision_engine(request_data)
                
                # Display decision
                if decision['status'] == 'approved':
                    st.success(f"✅ **APPROVED** (Confidence: {decision['confidence']}%)")
                    st.info(f"**Reasoning:** {decision['reasoning']}")
                    if decision.get('permit_pdf'):
                        st.download_button("📄 Download Permit", data=decision['permit_pdf'], file_name=f"permit_{decision['permit_id']}.pdf")
                elif decision['status'] == 'conditional':
                    st.warning(f"⚠️ **CONDITIONALLY APPROVED** (Confidence: {decision['confidence']}%)")
                    st.info(f"**Conditions:** {decision['conditions']}")
                    st.info(f"**Reasoning:** {decision['reasoning']}")
                    if decision.get('permit_pdf'):
                        st.download_button("📄 Download Conditional Permit", data=decision['permit_pdf'], file_name=f"permit_{decision['permit_id']}.pdf")
                else:
                    st.error(f"❌ **REJECTED** (Confidence: {decision['confidence']}%)")
                    st.info(f"**Reasoning:** {decision['reasoning']}")
                    if decision.get('recommendation'):
                        st.info(f"**Recommendation:** {decision['recommendation']}")
        else:
            st.error("Please fill all required fields")
