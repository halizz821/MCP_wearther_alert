"""Unit tests for Environment Canada MCP Server module."""

import json
from unittest.mock import patch
import pytest
from environment_canada_mcp.server import (
    get_weather_alerts,
    get_alert_summary,
    get_alerts_near_coordinates,
    get_alert_details,
    active_alerts_resource,
    summary_alerts_resource,
    province_alerts_resource,
    analyze_weather_safety,
    daily_weather_alert_briefing,
    severe_weather_report,
)
from tests.test_api import SAMPLE_GEOJSON


@patch("environment_canada_mcp.api.EnvironmentCanadaAPI.fetch_raw_alerts", return_value=SAMPLE_GEOJSON)
def test_server_tools(mock_fetch):
    # Test get_weather_alerts tool
    res_str = get_weather_alerts(province="ON")
    data = json.loads(res_str)
    assert data["count"] == 1
    assert data["alerts"][0]["province"] == "ON"

    # Test get_alert_summary tool
    summary_str = get_alert_summary()
    summary = json.loads(summary_str)
    assert summary["active_alerts_count"] == 2

    # Test get_alerts_near_coordinates tool
    coord_str = get_alerts_near_coordinates(latitude=43.75, longitude=-79.25)
    coord_data = json.loads(coord_str)
    assert coord_data["count"] == 1

    # Test get_alert_details tool
    details_str = get_alert_details(feature_id="fea1-1968")
    details = json.loads(details_str)
    assert details["feature_id"] == "fea1-1968"


@patch("environment_canada_mcp.api.EnvironmentCanadaAPI.fetch_raw_alerts", return_value=SAMPLE_GEOJSON)
def test_server_resources(mock_fetch):
    active_res = active_alerts_resource()
    active_data = json.loads(active_res)
    assert "active_alerts" in active_data

    sum_res = summary_alerts_resource()
    sum_data = json.loads(sum_res)
    assert "active_alerts_count" in sum_data

    prov_res = province_alerts_resource(province="AB")
    prov_data = json.loads(prov_res)
    assert prov_data["province"] == "AB"


def test_server_prompts():
    safety_prompt = analyze_weather_safety(province="ON", location="Toronto")
    assert "Toronto, ON" in safety_prompt
    assert "get_weather_alerts" in safety_prompt

    briefing_prompt = daily_weather_alert_briefing(provinces="ON,BC")
    assert "ON,BC" in briefing_prompt
    assert "get_alert_summary" in briefing_prompt

    report_prompt = severe_weather_report(alert_id="fea1-1968")
    assert "fea1-1968" in report_prompt
    assert "get_alert_details" in report_prompt
