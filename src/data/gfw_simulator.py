# gfw_simulator.py
import random
from datetime import datetime, timedelta

class GFWDataSimulator:
    """
    Generates realistic deforestation alerts based on GFW's actual alert counts
    Since the GFW API restricts coordinate access, we use the counts to create
    realistic simulation data for the Hazara region
    """
    
    def __init__(self, total_alerts=124, high_confidence=45):
        """
        Initialize with real GFW counts from your API test
        """
        self.total_alerts = total_alerts
        self.high_confidence = high_confidence
        
        # Known forest divisions in Hazara/KPK with their boundaries
        self.forest_zones = [
            {"name": "Swat Valley", "lat_range": (35.0, 35.5), "lon_range": (72.2, 72.8), "risk": "HIGH", "weight": 0.25},
            {"name": "Shangla", "lat_range": (34.7, 35.0), "lon_range": (72.5, 72.9), "risk": "HIGH", "weight": 0.20},
            {"name": "Abbottabad", "lat_range": (34.0, 34.4), "lon_range": (73.1, 73.4), "risk": "MEDIUM", "weight": 0.15},
            {"name": "Mansehra", "lat_range": (34.2, 34.6), "lon_range": (73.0, 73.4), "risk": "HIGH", "weight": 0.20},
            {"name": "Kaghan", "lat_range": (34.7, 35.1), "lon_range": (73.5, 74.0), "risk": "HIGH", "weight": 0.10},
            {"name": "Dir", "lat_range": (35.0, 35.4), "lon_range": (71.7, 72.2), "risk": "MEDIUM", "weight": 0.05},
            {"name": "Chitral", "lat_range": (35.5, 36.0), "lon_range": (71.5, 72.0), "risk": "LOW", "weight": 0.03},
            {"name": "Haripur", "lat_range": (33.8, 34.1), "lon_range": (72.8, 73.1), "risk": "MEDIUM", "weight": 0.02},
        ]
        
        # Normalize weights to sum to 1
        total_weight = sum(z["weight"] for z in self.forest_zones)
        for zone in self.forest_zones:
            zone["weight"] = zone["weight"] / total_weight
        
    def get_recent_alerts(self, days=30, limit=50):
        """
        Generate realistic alert locations based on GFW's counts
        
        Args:
            days: Number of days to look back
            limit: Maximum number of alerts to return
        
        Returns:
            List of alert dictionaries with coordinates and metadata
        """
        alerts = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Calculate alerts per zone based on weights
        for zone in self.forest_zones:
            zone_alerts = int(self.total_alerts * zone["weight"])
            
            # Generate alerts for this zone
            for i in range(min(zone_alerts, limit)):
                # Random latitude/longitude within zone boundaries
                lat = random.uniform(zone["lat_range"][0], zone["lat_range"][1])
                lon = random.uniform(zone["lon_range"][0], zone["lon_range"][1])
                
                # Random date within the last 'days' days
                alert_date = start_date + timedelta(days=random.randint(0, days))
                
                # Determine confidence based on zone risk and random factor
                if zone["risk"] == "HIGH":
                    confidence = "HIGH" if random.random() > 0.3 else "MEDIUM"
                elif zone["risk"] == "MEDIUM":
                    confidence = "MEDIUM" if random.random() > 0.5 else "HIGH"
                else:
                    confidence = "LOW" if random.random() > 0.7 else "MEDIUM"
                
                alerts.append({
                    "id": f"GFW-{zone['name'][:3]}{i+1}",
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "date": alert_date.strftime("%Y-%m-%d"),
                    "confidence": confidence,
                    "zone": zone["name"],
                    "risk": zone["risk"],
                    "source": "GFW-SIMULATED"
                })
        
        # Sort by date (newest first)
        alerts.sort(key=lambda x: x["date"], reverse=True)
        
        # Limit to requested number
        return alerts[:limit]
    
    def get_statistics(self):
        """Return summary statistics matching GFW's reported numbers"""
        return {
            "total_alerts": self.total_alerts,
            "high_confidence_alerts": self.high_confidence,
            "estimated_loss_ha": round(self.total_alerts * 0.09, 2),  # 0.09 ha per alert on average
            "period": "30 days",
            "status": "STABLE",
            "source": "GFW Data API (Simulated from real counts)"
        }
    
    def get_alerts_by_zone(self):
        """Get alerts grouped by forest zone"""
        zone_stats = []
        for zone in self.forest_zones:
            zone_stats.append({
                "name": zone["name"],
                "risk": zone["risk"],
                "estimated_alerts": int(self.total_alerts * zone["weight"]),
                "bounding_box": {
                    "lat_min": zone["lat_range"][0],
                    "lat_max": zone["lat_range"][1],
                    "lon_min": zone["lon_range"][0],
                    "lon_max": zone["lon_range"][1]
                }
            })
        return zone_stats


# Test the simulator
if __name__ == "__main__":
    gfw = GFWDataSimulator(total_alerts=124, high_confidence=45)
    
    print("=" * 70)
    print("🌳 GFW DEFORESTATION ALERTS - SIMULATED FROM REAL COUNTS")
    print("=" * 70)
    
    stats = gfw.get_statistics()
    print(f"\n📊 STATISTICS (from GFW API):")
    print(f"   Total Alerts: {stats['total_alerts']}")
    print(f"   High Confidence: {stats['high_confidence_alerts']}")
    print(f"   Est. Loss: {stats['estimated_loss_ha']} ha")
    print(f"   Source: {stats['source']}")
    
    print(f"\n📍 RECENT ALERTS (last 30 days):")
    print("-" * 70)
    
    alerts = gfw.get_recent_alerts(limit=15)
    for alert in alerts[:10]:
        print(f"   {alert['lat']}, {alert['lon']} | {alert['date']} | {alert['zone']} | Confidence: {alert['confidence']}")
    
    if len(alerts) > 10:
        print(f"\n   ... and {len(alerts)-10} more alerts")
    
    print(f"\n📋 ALERTS BY ZONE:")
    print("-" * 70)
    for zone in gfw.get_alerts_by_zone():
        print(f"   {zone['name']}: {zone['estimated_alerts']} alerts (Risk: {zone['risk']})")