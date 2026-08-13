"""
Phase 3 - Pillar 3: Seasonal Awareness Agent
Proactively generates public awareness bulletins based on the current
season and associated forestry risks.
"""

from loguru import logger
from datetime import datetime

class SeasonalAwarenessAgent:
    def __init__(self):
        pass

    def generate_bulletin(self):
        """Generates seasonal advice and warnings for the public."""
        month = datetime.now().month
        
        logger.info(f"[SeasonalAwareness] Generating bulletin for month {month}")
        
        # Determine the season and risk profile
        if 4 <= month <= 6:
            season = "Summer (Dry Season)"
            primary_risk = "Forest Fires"
            bulletin = {
                "title": "Summer Forest Fire Alert",
                "urgency": "HIGH",
                "message": (
                    "It is the peak dry season. Most forest fires are caused by human negligence. "
                    "Strictly NO open campfires, NO discarding of cigarettes, and NO burning of agricultural waste "
                    "near the forest boundaries. Report any smoke immediately to the Forest Department."
                ),
                "action_items": [
                    "Report smoke via hotline: 1122",
                    "Clear dry pine needles from around homes",
                    "Ensure extinguishing of all cooking fires"
                ]
            }
        elif 7 <= month <= 9:
            season = "Monsoon Season"
            primary_risk = "Landslides & Flooding"
            bulletin = {
                "title": "Monsoon Reforestation Drive",
                "urgency": "MEDIUM",
                "message": (
                    "The monsoon brings life to the forests but also risks of landslides in deforested areas. "
                    "Now is the best time for planting trees. The Forest Department is providing free saplings "
                    "for citizens to plant."
                ),
                "action_items": [
                    "Collect free saplings from your local forest office",
                    "Avoid traveling on remote forest roads during heavy rain",
                    "Report illegal timber smuggling taking advantage of rain cover"
                ]
            }
        elif 10 <= month <= 11:
            season = "Autumn (Felling Season)"
            primary_risk = "Illegal Felling"
            bulletin = {
                "title": "Winter Preparation Awareness",
                "urgency": "HIGH",
                "message": (
                    "As winter approaches, the illegal cutting of timber for firewood increases. "
                    "Remember that cutting green standing trees is a criminal offense punishable by heavy fines. "
                    "Please rely on designated dead-wood collection areas only."
                ),
                "action_items": [
                    "Collect only fallen dry branches for firewood",
                    "Report chainsaws operating at night",
                    "Purchase timber only from licensed depots"
                ]
            }
        else: # 12, 1, 2, 3
            season = "Winter"
            primary_risk = "Wildlife Poaching & Firewood Felling"
            bulletin = {
                "title": "Winter Forest Protection",
                "urgency": "MEDIUM",
                "message": (
                    "Winter conditions push wildlife lower into the valleys. Hunting protected wildlife "
                    "and illegal firewood collection are strictly prohibited."
                ),
                "action_items": [
                    "Do not buy illegal wildlife products",
                    "Ensure firewood is legally sourced",
                    "Report poachers to wildlife guards"
                ]
            }
            
        return {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "season": season,
            "primary_risk": primary_risk,
            "bulletin": bulletin
        }
