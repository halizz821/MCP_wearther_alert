"""Environment Canada Weather Alerts MCP Server.

Provides tools, resources, and prompts to interact with Environment Canada Weather Alerts.
"""

import json
import logging
from typing import Optional

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from environment_canada_mcp.api import EnvironmentCanadaAPI

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = MCPServer(
    name="Environment Canada Weather Alerts",
)

api = EnvironmentCanadaAPI()


# ------------------------------------------------------------------------------
# TOOLS
# ------------------------------------------------------------------------------

@mcp.tool()
def get_weather_alerts(
    province: Optional[str] = None,
    alert_type: Optional[str] = None,
    search_query: Optional[str] = None,
    language: str = "en",
) -> str:
    """Fetches real-time weather alerts from Environment Canada.

    Args:
        province: Two-letter Canadian province/territory code (e.g. 'ON', 'BC', 'AB', 'QC', 'NS', 'NB', 'MB', 'SK', 'PE', 'NL', 'YT', 'NT', 'NU').
        alert_type: Type of alert filter ('warning', 'watch', 'advisory', 'statement').
        search_query: Optional keyword to search in location names or alert description (e.g., 'Toronto', 'blizzard', 'fog').
        language: Language for names and description ('en' for English, 'fr' for French). Default is 'en'.

    Returns:
        JSON formatted string containing matching weather alerts. Each alert includes its 'status' (e.g. 'active', 'ended').
    """
    alerts = api.get_weather_alerts(
        province=province,
        alert_type=alert_type,
        search_query=search_query,
        language=language,
    )
    return json.dumps({"count": len(alerts), "alerts": alerts}, indent=2, ensure_ascii=False)


@mcp.tool()
def get_alert_summary(province: Optional[str] = None) -> str:
    """Gets an executive breakdown summary of active Canadian weather alerts.

    Args:
        province: Optional two-letter province code to restrict summary (e.g. 'ON').

    Returns:
        JSON string summarizing alert counts (warnings, watches, advisories) by province.
    """
    summary = api.get_alert_summary(province=province)
    return json.dumps(summary, indent=2, ensure_ascii=False)


@mcp.tool()
def get_alerts_near_coordinates(
    latitude: float,
    longitude: float,
    language: str = "en",
) -> str:
    """Checks for weather alerts intersecting a specific latitude and longitude coordinate.

    Args:
        latitude: Latitude in decimal degrees (e.g., 43.6532 for Toronto).
        longitude: Longitude in decimal degrees (e.g., -79.3832 for Toronto).
        language: Output language ('en' or 'fr'). Default is 'en'.

    Returns:
        JSON string of alerts affecting the given coordinates. Each alert includes its 'status'.
    """
    alerts = api.get_alerts_near_coordinates(
        latitude=latitude,
        longitude=longitude,
        language=language,
    )
    return json.dumps(
        {
            "query_location": {"latitude": latitude, "longitude": longitude},
            "count": len(alerts),
            "alerts": alerts,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def get_alert_details(feature_id: str, language: str = "en") -> str:
    """Retrieves full details including text description and boundary geometry for a specific alert.

    Args:
        feature_id: Unique feature ID or item ID of the weather alert.
        language: Output language ('en' or 'fr'). Default is 'en'.

    Returns:
        JSON string containing detailed alert metadata and polygon geometry.
    """
    details = api.get_alert_details(feature_id_or_id=feature_id, language=language)
    if not details:
        return json.dumps({"error": f"Alert with feature_id '{feature_id}' not found."}, indent=2)
    return json.dumps(details, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------------------
# RESOURCES
# ------------------------------------------------------------------------------

@mcp.resource("weather-alerts://active")
def active_alerts_resource() -> str:
    """Resource providing live JSON stream of weather alerts in Canada."""
    alerts = api.get_weather_alerts()
    return json.dumps({"active_alerts": alerts}, indent=2, ensure_ascii=False)


@mcp.resource("weather-alerts://summary")
def summary_alerts_resource() -> str:
    """Resource providing a national summary breakdown of active weather alerts."""
    summary = api.get_alert_summary()
    return json.dumps(summary, indent=2, ensure_ascii=False)


@mcp.resource("weather-alerts://province/{province}")
def province_alerts_resource(province: str) -> str:
    """Resource providing weather alerts for a specific Canadian province (e.g., weather-alerts://province/ON)."""
    alerts = api.get_weather_alerts(province=province)
    return json.dumps({"province": province.upper(), "count": len(alerts), "alerts": alerts}, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------------------
# PROMPTS
# ------------------------------------------------------------------------------

@mcp.prompt()
def analyze_weather_safety(province: str = "ON", location: str = "") -> str:
    """Generates an prompt for analyzing weather safety and providing emergency advice based on current alerts.

    Args:
        province: Canadian province code (e.g. 'ON', 'BC').
        location: Specific city or region name (e.g. 'Toronto', 'Ottawa').
    """
    target = f"{location}, {province.upper()}" if location else province.upper()
    return f"""You are a meteorology safety assistant. Please fetch active weather alerts for {target} using the `get_weather_alerts` tool or coordinate lookup tool.

Once you retrieve the alerts:
1. Summarize any active Warnings, Watches, or Advisories in effect.
2. Outline specific safety precautions and emergency preparedness steps for affected residents or travelers.
3. Highlight severity level, expected timeline, and high-risk conditions (e.g., zero visibility, flooding, high winds, extreme cold/heat).
4. If no active alerts are found, confirm that weather conditions in {target} currently have no Environment Canada warnings issued.
"""


@mcp.prompt()
def daily_weather_alert_briefing(provinces: str = "ON,QC,BC,AB") -> str:
    """Generates an executive briefing prompt on active severe weather across Canadian provinces.

    Args:
        provinces: Comma-separated list of province codes (e.g. 'ON,QC,BC,AB').
    """
    return f"""You are an executive weather analyst creating a daily Canadian weather risk briefing for: {provinces}.

Please perform the following:
1. Use `get_alert_summary` to review the current active alert volume across Canada.
2. For each requested province ({provinces}), use `get_weather_alerts` to identify major warnings or watches.
3. Synthesize your findings into a clean, professional executive summary with sections:
   - **National Overview**
   - **High-Risk Zones & Active Severe Warnings**
   - **Travel & Logistics Operational Impact**
   - **Outlook & Next Updates**
"""


@mcp.prompt()
def severe_weather_report(alert_id: str = "") -> str:
    """Generates a formal severe weather incident report prompt for a specific alert ID.

    Args:
        alert_id: Feature ID or alert ID.
    """
    return f"""You are an emergency response specialist. Please retrieve the detailed alert information using `get_alert_details` for alert ID: '{alert_id}'.

Create a formal Incident Weather Report containing:
1. **Event Metadata**: Alert Code, Type, Affected Feature/Location, Publication & Validity Datetime.
2. **Official Warning Content**: Clean synthesis of the official Environment Canada alert text.
3. **Potential Hazards & Risk Level**: Risk color classification, direct impact to infrastructure/transportation.
4. **Recommended Action Plan**: Recommended local authority response and public safety instructions.
"""


def main():
    """Server CLI entrypoint."""
    mcp.run()


if __name__ == "__main__":
    main()
