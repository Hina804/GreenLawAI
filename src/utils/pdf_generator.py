from fpdf import FPDF
from datetime import datetime
import io
import re

def sanitize_text(text: str) -> str:
    """Removes emojis and non-Latin-1 characters that break FPDF default fonts."""
    if not text:
        return ""
    # Remove common emojis and non-latin-1 characters
    return text.encode('ascii', 'ignore').decode('ascii')

class GreenLawPDF(FPDF):
    def header(self):
        # Professional Header
        self.set_fill_color(46, 125, 50)  # Forest Green
        self.rect(0, 0, 210, 40, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font('helvetica', 'B', 24)
        self.cell(0, 10, 'GreenLawAI', ln=True, align='C')
        self.set_font('helvetica', 'I', 12)
        self.cell(0, 10, 'Phase 3: Real-Time Legal & Environmental Intelligence', ln=True, align='C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()} | Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', align='C')

def generate_report(query, result_data):
    pdf = GreenLawPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 1. Query Section
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, 'Legal Consultation Report', ln=True)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, f'Query: "{sanitize_text(query)}"', ln=True)
    pdf.ln(5)
    
    # 2. Legal Analysis (IRAC)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, ' Legal Analysis (IRAC)', ln=True, fill=True)
    pdf.set_font('helvetica', '', 11)
    
    legal_text = result_data.get('legal_text', 'No legal data available.')
    # Clean up markdown-style bolding for PDF
    clean_legal = sanitize_text(legal_text.replace('**', ''))
    pdf.multi_cell(0, 8, clean_legal)
    pdf.ln(5)
    
    # 3. Environment Section
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, ' Environmental & Situational Data', ln=True, fill=True)
    pdf.set_font('helvetica', '', 11)
    
    climate = result_data.get('climate_text', 'No climate data.')
    monitoring = result_data.get('monitoring_text', 'No situational data.')
    
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 8, 'Climate Insights:', ln=True)
    pdf.set_font('helvetica', '', 11)
    pdf.multi_cell(0, 8, sanitize_text(climate.replace('**', '')))
    
    pdf.ln(3)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 8, 'Situational Awareness:', ln=True)
    pdf.set_font('helvetica', '', 11)
    pdf.multi_cell(0, 8, sanitize_text(monitoring.replace('**', '')))
    pdf.ln(5)
    
    # 4. Real-Time Metrics
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, ' Real-Time Technical Metrics', ln=True, fill=True)
    
    fstats = result_data.get('fire_stats', {})
    wstats = result_data.get('weather_stats', {})
    
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 8, sanitize_text(f"- NASA FIRMS: {fstats.get('total_fires', 0)} active fires detected in last 24h."), ln=True)
    pdf.cell(0, 8, sanitize_text(f"- Fire Intensity: {round(fstats.get('avg_brightness', 0), 1)} Kelvin."), ln=True)
    pdf.cell(0, 8, sanitize_text(f"- Local Weather: {wstats.get('temp', 'N/A')}°C | Fire Risk Index: {wstats.get('risk_index', 'N/A')}/100."), ln=True)
    
    # 5. Statutory Citations
    citations = result_data.get('citations', [])
    if citations:
        pdf.ln(5)
        pdf.set_font('helvetica', 'B', 12)
        pdf.cell(0, 10, 'Statutory References:', ln=True)
        pdf.set_font('helvetica', 'I', 10)
        for c in citations:
            pdf.cell(0, 6, f"- {sanitize_text(str(c))}", ln=True)

    # Output as binary bytes (Streamlit expects bytes, not bytearray)
    return bytes(pdf.output())
