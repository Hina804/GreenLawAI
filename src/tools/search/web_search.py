# E:\GL_AI\src\tools\search\web_search.py

import logging
import asyncio
import warnings
import re
import random
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List
from duckduckgo_search import DDGS
from tools.base_tool import BaseTool
import os

warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Pakistani News Sources
PAKISTAN_NEWS_SOURCES = [
    "geo.tv", "arynews.tv", "samaa.tv", "dunyanews.tv", "express.pk",
    "thenews.com.pk", "dawn.com", "tribune.com.pk", "bolnews.com",
    "gnn.tv", "humnews.pk", "aaj.tv", "ptvnews.gov.pk"
]

PAKISTAN_NEWS_CURATED_LINKS = [
    {"name": "Dawn News", "url": "https://www.dawn.com/news/environment", "category": "Environment"},
    {"name": "The News International", "url": "https://www.thenews.com.pk/latest/kpk", "category": "KPK"},
    {"name": "Express Tribune", "url": "https://tribune.com.pk/climate", "category": "Climate"},
    {"name": "Geo News", "url": "https://www.geo.tv/environment", "category": "Environment"},
    {"name": "ARY News", "url": "https://arynews.tv/category/khyber-pakhtunkhwa/", "category": "KPK"},
    {"name": "Samaa TV", "url": "https://www.samaa.tv/environment", "category": "Environment"},
    {"name": "Dunya News", "url": "https://dunyanews.tv/environment", "category": "Environment"},
    {"name": "PTV News", "url": "https://ptvnews.gov.pk/category/environment/", "category": "National"},
    {"name": "Pakistan Observer", "url": "https://pakobserver.net/category/environment/", "category": "Environment"},
]

class WebSearch(BaseTool):
    """
    Professional news search using NewsAPI with Pakistan focus.
    """
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Searches for news reports on forest fires, climate, and environmental issues in Pakistan."
        )
        self.news_api_key = os.getenv("NEWS_API_KEY", "e0282cd65a5249cbb05a5710f848faf9")
        
    def _get_curated_news_links_block(self) -> str:
        block = "---\n\n🔗 **Recommended News Sources for Forest Updates:**\n\n"
        for i, src in enumerate(PAKISTAN_NEWS_CURATED_LINKS[:5], 1): # Top 5
            block += f"{i}. **{src['name']} - {src['category']}**\n"
            block += f"   🔗 {src['url']}\n\n"
        return block

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        query = parameters.get("query", "")
        if not query:
            return {"error": "No query provided for web_search."}

        # Extract location from query
        location = self._extract_location(query)
        
        # Build search keywords
        keywords = self._build_keywords(query, location)
        
        logger.info(f"WebSearch: Location='{location}', Keywords='{keywords}'")
        
        # Step 1: Try NewsAPI first (most reliable)
        news_results = await self._search_news_api(keywords, location)
        
        if news_results:
            return self._format_response(news_results, location, "NewsAPI")
        
        # Step 2: Fallback to DuckDuckGo with proper filters
        ddg_results = await self._search_duckduckgo(keywords, location)
        
        if ddg_results:
            return self._format_response(ddg_results, location, "DuckDuckGo")
        
        # Step 3: No recent news - pivot to Historical Intelligence
        historical_data = self._get_historical_incidents(location)
        if historical_data.get("has_historical"):
            return self._format_historical_response(historical_data, location)
            
        # Step 4: Absolute fallback
        return self._no_results_response(location, keywords)

    def _extract_location(self, query: str) -> str:
        """Extract location from query"""
        query_lower = query.lower()
        locations = ["hazara", "abbottabad", "mansehra", "swat", "kpk", "peshawar", "islamabad"]
        for loc in locations:
            if loc in query_lower:
                return loc.capitalize()
        return "Hazara"

    def _build_keywords(self, query: str, location: str) -> str:
        """Build professional search keywords"""
        # Remove filler words
        filler = ["search for", "any news", "reports from", "regarding", "tell me", "find"]
        cleaned = query.lower()
        for f in filler:
            cleaned = cleaned.replace(f, "")
        
        # Build focused keywords
        if "forest fire" in cleaned or "fire" in cleaned:
            return f"forest fire {location} Pakistan"
        elif "deforestation" in cleaned:
            return f"deforestation {location} Pakistan"
        elif "climate" in cleaned:
            return f"climate change forest {location} Pakistan"
        else:
            return f"forest {location} Pakistan news"

    async def _search_news_api(self, keywords: str, location: str) -> List[Dict]:
        """Search using NewsAPI"""
        if not self.news_api_key or self.news_api_key == "e0282cd65a5249cbb05a5710f848faf9":
            logger.warning("NewsAPI key not configured")
            return []
        
        try:
            # Calculate date for last 7 days (better than 24h for low-frequency events)
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": f"({keywords}) AND (forest OR fire OR wildfire OR deforestation)",
                "from": from_date,
                "sortBy": "relevancy",
                "language": "en",
                "pageSize": 5,
                "apiKey": self.news_api_key
            }
            
            # Add source filtering for Pakistani news
            sources_param = ",".join(PAKISTAN_NEWS_SOURCES[:5])
            params["sources"] = sources_param
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])
                
                results = []
                for article in articles[:5]:
                    results.append({
                        "title": article.get("title", "No Title"),
                        "snippet": article.get("description", "No description available."),
                        "url": article.get("url", "#"),
                        "source": article.get("source", {}).get("name", "News Source"),
                        "date": article.get("publishedAt", "Recent")[:10]
                    })
                return results
            
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
        
        return []

    async def _search_duckduckgo(self, keywords: str, location: str) -> List[Dict]:
        """Fallback to DuckDuckGo with proper filters"""
        try:
            # Build a very specific query
            search_query = f'"{keywords}" "Pakistan" "forest" -app -"Nottingham" -"Black Forest" -"专注森林"'
            
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, self._ddg_search, search_query)
            
            # Filter out irrelevant results
            filtered = []
            for r in results:
                title_lower = r.get("title", "").lower()
                snippet_lower = r.get("body", "").lower()
                
                # Skip obviously irrelevant results
                if any(skip in title_lower for skip in ["nottingham", "football", "europa", "app", "download", "专注"]):
                    continue
                if any(skip in snippet_lower for skip in ["nottingham", "football", "europa", "app", "download"]):
                    continue
                
                # Must contain Pakistan or location related terms
                if "pakistan" in title_lower or "pakistan" in snippet_lower or location.lower() in title_lower:
                    filtered.append(r)
            
            return filtered[:5]
            
        except Exception as e:
            logger.error(f"DuckDuckGo error: {e}")
            return []

    def _ddg_search(self, query: str) -> List[Dict]:
        """Synchronous DuckDuckGo search"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                with DDGS() as ddgs:
                    results = []
                    for r in ddgs.text(query, max_results=10):
                        results.append({
                            "title": r.get("title", "No Title"),
                            "body": r.get("body", r.get("snippet", "No details available.")),
                            "url": r.get("href", "#"),
                            "source": "Search Result",
                            "date": "Recent"
                        })
                    return results
            except Exception as e:
                logger.error(f"DDGS error: {e}")
                return []

    def _get_historical_incidents(self, location: str) -> Dict:
        """Fetch REAL historical incidents from database and APIs"""
        from agents.incident_agent import IncidentAgent
        from data.fire_monitor import FIRMSFireMonitor
        from data.deforestation_monitor import GFWDeforestationMonitor
        
        try:
            # 1. Local Database Query
            incident_agent = IncidentAgent(config={})
            all_incidents = incident_agent._get_all_incidents()
            
            loc_lower = location.lower()
            relevant_incidents = []
            for inc in all_incidents:
                inc_loc = inc.get('location', '').lower()
                if loc_lower in inc_loc or inc_loc in loc_lower:
                    relevant_incidents.append(inc)
            relevant_incidents.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            # 2. NASA FIRMS Archive (Last 7 days - API limit)
            firms = FIRMSFireMonitor(os.getenv("NASA_FIRMS_TOKEN", "e0282cd65a5249cbb05a5710f848faf9")) # Use token env
            recent_fires = firms.get_active_fires(days=7)
            location_fires = [f for f in recent_fires if self._is_in_location(f.get('lat'), f.get('lon'), location)]
            
            # 3. GFW Archive (Last 90 days)
            gfw = GFWDeforestationMonitor()
            gfw_data = gfw.get_alerts(country="PAK", days=90)
            gfw_alerts = gfw_data.get('recent_hotspots', [])
            location_alerts = [a for a in gfw_alerts if self._is_in_location(a.get('lat'), a.get('lon'), location)]
            
            last_incident = None
            if relevant_incidents:
                last_incident = {
                    "date": relevant_incidents[0].get('date'),
                    "location": relevant_incidents[0].get('location'),
                    "description": relevant_incidents[0].get('violation'),
                    "source": "Field Report / Incident Agent",
                    "type": "field"
                }
            elif location_fires:
                last_incident = {
                    "date": location_fires[0].get('date'),
                    "location": location,
                    "description": f"Fire detected via NASA FIRMS satellite. Brightness: {location_fires[0].get('brightness')}K",
                    "source": "NASA FIRMS",
                    "type": "fire"
                }
            elif location_alerts:
                last_incident = {
                    "date": location_alerts[0].get('date'),
                    "location": location_alerts[0].get('zone', location),
                    "description": f"Deforestation alert detected via GFW satellite. Confidence: {location_alerts[0].get('confidence')}",
                    "source": "Global Forest Watch",
                    "type": "deforestation"
                }
                
            return {
                "has_historical": last_incident is not None,
                "last_incident": last_incident,
                "recent_incidents": relevant_incidents[:3],
                "recent_fires": location_fires[:3],
                "recent_alerts": location_alerts[:3]
            }
        except Exception as e:
            logger.error(f"Historical fetch error: {e}")
            return {"has_historical": False}

    def _is_in_location(self, lat: float, lon: float, location: str) -> bool:
        """Check if coordinates are within tactical bounding boxes"""
        bounds = {
            "hazara": {"lat_min": 33.8, "lat_max": 35.5, "lon_min": 72.0, "lon_max": 74.0},
            "abbottabad": {"lat_min": 34.0, "lat_max": 34.4, "lon_min": 73.1, "lon_max": 73.4},
            "swat": {"lat_min": 35.0, "lat_max": 35.5, "lon_min": 72.2, "lon_max": 72.8},
            "mansehra": {"lat_min": 34.2, "lat_max": 34.6, "lon_min": 73.0, "lon_max": 73.4},
        }
        loc_lower = location.lower()
        for key, box in bounds.items():
            if key in loc_lower or loc_lower in key:
                if lat and lon:
                    return (box["lat_min"] <= lat <= box["lat_max"] and 
                            box["lon_min"] <= lon <= box["lon_max"])
        return False

    def _format_historical_response(self, data: Dict, location: str) -> Dict:
        """Format historical fallback with real-time alert awareness"""
        import datetime
        today_date = datetime.date.today()
        yesterday_date = today_date - datetime.timedelta(days=1)
        
        last = data.get("last_incident", {})
        last_date_str = last.get('date', '')
        
        # Determine category for the last incident
        try:
            last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
            if last_date == today_date:
                category = "🚨 **CURRENT ALERT DETECTED (Today)**"
                status = "success_realtime"
                header = f"🚨 **SATELLITE INTELLIGENCE: REAL-TIME DETECTION for {location}**"
            elif last_date == yesterday_date:
                category = "⚠️ **RECENT ALERT (Yesterday)**"
                status = "success_recent"
                header = f"⚠️ **RECENT SATELLITE DETECTION for {location}**"
            else:
                category = "📜 **HISTORICAL RECORD (Grounded Data)**"
                status = "success_historical"
                header = f"📋 **No Recent News Found (Last 24 Hours) for {location}**"
        except Exception:
            category = "📜 **HISTORICAL RECORD**"
            status = "success_historical"
            header = f"📋 **Historical Baseline for {location}**"

        hist_report = f"{header}\n\n"
        if status == "success_realtime":
            hist_report += f"A high-priority alert has been detected within the last 24 hours via tactical sensors.\n\n"
        else:
            hist_report += f"However, the following historical records have been identified:\n\n"
            
        hist_report += f"---\n\n{category}:\n"
        hist_report += f"• **Date:** {last_date_str}\n"
        hist_report += f"• **Location:** {last.get('location')}\n"
        hist_report += f"• **Description:** {last.get('description')}\n"
        
        # Add dynamic links based on detection type
        if last.get('type') == 'fire':
            lat, lon = last.get('lat', 34.2), last.get('lon', 73.3)
            firms_map = f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{lon:.1f},{lat:.1f},12z"
            hist_report += f"• **Source:** {last.get('source')} 🔗 [View Map]({firms_map})\n\n"
        elif last.get('type') == 'deforestation':
            gfw_map = "https://www.globalforestwatch.org/map/country/PAK/"
            hist_report += f"• **Source:** {last.get('source')} 🔗 [View Map]({gfw_map})\n\n"
        else:
            hist_report += f"• **Source:** {last.get('source')}\n\n"
        
        if data.get("recent_fires"):
            hist_report += f"🔥 **Recent Fire Detections (Last 30 days):**\n"
            for f in data["recent_fires"]:
                flat, flon = f.get('lat', 34.2), f.get('lon', 73.3)
                f_map = f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{flon:.1f},{flat:.1f},12z"
                hist_report += f"• {f.get('date')}: Thermal anomaly in {location} 🔗 [Map]({f_map})\n"
            hist_report += "\n"
            
        if data.get("recent_alerts"):
            hist_report += f"🌳 **Recent Deforestation Alerts (Last 90 days):**\n"
            gfw_country = "https://www.globalforestwatch.org/map/country/PAK/"
            for a in data["recent_alerts"]:
                label = " (TODAY)" if a.get('date') == str(today_date) else ""
                hist_report += f"• {a.get('date')}{label}: Tree cover change detected 🔗 [Map]({gfw_country})\n"
            hist_report += "\n"

        hist_report += f"⏱️ *Real-time monitors (GFW/NASA) are active. Click [Map] links to verify tactical detections.*\n\n"
        hist_report += self._get_curated_news_links_block()
        
        return {
            "status": status,
            "results": [],
            "note": f"Real-time sensor detection active for {location}." if status == "success_realtime" else "Live news restricted. Citing historical baseline.",
            "historical_context": hist_report
        }

    def _format_response(self, results: List[Dict], location: str, source: str) -> Dict:
        """Format successful search response"""
        return {
            "status": "success",
            "results": results,
            "note": f"Found {len(results)} relevant news items for {location} (Source: {source})"
        }

    def _no_results_response(self, location: str, keywords: str) -> Dict:
        """Professional response when no news found"""
        no_res_ctx = f"No recent or historical matches found for {location}. Strategic monitoring remains active.\n\n"
        no_res_ctx += self._get_curated_news_links_block()
        return {
            "status": "no_recent_news",
            "results": [],
            "note": f"No recent forest fire incidents reported in {location} within the last 7 days.",
            "historical_context": no_res_ctx
        }