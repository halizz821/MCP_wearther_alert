"""Unit tests for EnvironmentCanadaAPI."""

import pytest
from unittest.mock import MagicMock, patch
from environment_canada_mcp.api import EnvironmentCanadaAPI

SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "1157231192044178045202609130501_fea1-1968",
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-79.5, 43.5],
                        [-79.0, 43.5],
                        [-79.0, 44.0],
                        [-79.5, 44.0],
                        [-79.5, 43.5]
                    ]
                ]
            },
            "properties": {
                "alert_code": "FGA",
                "alert_type": "advisory",
                "alert_name_en": "fog advisory",
                "alert_name_fr": "avis de brouillard",
                "alert_short_name_en": "Fog (advisory)",
                "alert_short_name_fr": "Brouillard (avis)",
                "publication_datetime": "2026-09-13T15:31:37.788Z",
                "expiration_datetime": "2026-09-13T18:30:37.788Z",
                "alert_text_en": "Near-zero visibility in fog continues over Toronto area.",
                "alert_text_fr": "La visibilité demeure presque nulle par endroits.",
                "risk_colour_en": "yellow",
                "risk_colour_fr": "jaune",
                "feature_name_en": "City of Toronto",
                "feature_name_fr": "Ville de Toronto",
                "province": "ON",
                "status_en": "active",
                "status_fr": "actif",
                "feature_id": "fea1-1968"
            }
        },
        {
            "id": "1157231192044178045202609130501_fea1-1969",
            "type": "Feature",
            "geometry": None,
            "properties": {
                "alert_code": "SVR",
                "alert_type": "warning",
                "alert_name_en": "severe thunderstorm warning",
                "alert_name_fr": "avertissement d'orage violent",
                "publication_datetime": "2026-09-13T16:00:00.000Z",
                "alert_text_en": "Severe thunderstorms with high winds and heavy rain.",
                "feature_name_en": "Calgary Region",
                "province": "AB",
                "status_en": "active",
                "feature_id": "fea1-1969"
            }
        },
        {
            "id": "1157231192044178045202609130501_fea1-1970",
            "type": "Feature",
            "geometry": None,
            "properties": {
                "alert_code": "WWA",
                "alert_type": "warning",
                "alert_name_en": "wind warning",
                "publication_datetime": "2026-09-13T10:00:00.000Z",
                "alert_text_en": "Strong winds have ended.",
                "feature_name_en": "Vancouver Island",
                "province": "BC",
                "status_en": "ended",
                "feature_id": "fea1-1970"
            }
        }
    ]
}


def test_clean_and_group_features():
    api = EnvironmentCanadaAPI()
    cleaned = api.clean_and_group_features(SAMPLE_GEOJSON)
    assert len(cleaned) == 3
    ids = [item["feature_id"] for item in cleaned]
    assert "fea1-1968" in ids
    assert "fea1-1969" in ids
    assert "fea1-1970" in ids


def test_clean_and_group_features_multiple_alerts_same_feature_id():
    api = EnvironmentCanadaAPI()
    multi_alert_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "item_1",
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "feature_id": "fea1-toronto",
                    "alert_code": "SVR",
                    "alert_type": "watch",
                    "alert_name_en": "severe thunderstorm watch",
                    "publication_datetime": "2026-09-13T10:00:00.000Z",
                    "province": "ON",
                    "status_en": "active",
                },
            },
            {
                "id": "item_2",
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "feature_id": "fea1-toronto",
                    "alert_code": "HEAT",
                    "alert_type": "warning",
                    "alert_name_en": "heat warning",
                    "publication_datetime": "2026-09-13T10:05:00.000Z",
                    "province": "ON",
                    "status_en": "active",
                },
            },
            {
                "id": "item_3_old",
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "feature_id": "fea1-toronto",
                    "alert_code": "HEAT",
                    "alert_type": "warning",
                    "alert_name_en": "heat warning",
                    "publication_datetime": "2026-09-13T09:00:00.000Z",
                    "province": "ON",
                    "status_en": "active",
                },
            },
        ],
    }
    cleaned = api.clean_and_group_features(multi_alert_geojson)
    # Should preserve both Severe Thunderstorm Watch AND Heat Warning for feature_id 'fea1-toronto'
    assert len(cleaned) == 2
    alert_codes = {item["alert_code"] for item in cleaned}
    assert alert_codes == {"SVR", "HEAT"}
    # Verify that the Heat Warning kept is the newest publication datetime (10:05, not 09:00)
    heat_alert = next(item for item in cleaned if item["alert_code"] == "HEAT")
    assert heat_alert["id"] == "item_2"
    assert heat_alert["publication_datetime"] == "2026-09-13T10:05:00.000Z"



@patch.object(EnvironmentCanadaAPI, "fetch_raw_alerts", return_value=SAMPLE_GEOJSON)
def test_get_weather_alerts_filtering(mock_fetch):
    api = EnvironmentCanadaAPI()

    # Fetch all alerts (no status filtering - returns both active and ended)
    all_alerts = api.get_weather_alerts()
    assert len(all_alerts) == 3
    # Verify status is present in the return json
    assert all("status" in alert for alert in all_alerts)
    assert all_alerts[0]["status"] == "active"
    assert all_alerts[2]["status"] == "ended"

    # Filter by province ON
    on_alerts = api.get_weather_alerts(province="ON")
    assert len(on_alerts) == 1
    assert on_alerts[0]["province"] == "ON"
    assert on_alerts[0]["feature_name"] == "City of Toronto"
    assert on_alerts[0]["status"] == "active"

    # Filter by alert_type warning (both active AB warning and ended BC warning are returned)
    warning_alerts = api.get_weather_alerts(alert_type="warning")
    assert len(warning_alerts) == 2
    provinces = {a["province"] for a in warning_alerts}
    assert provinces == {"AB", "BC"}
    assert any(a["status"] == "ended" for a in warning_alerts)
    assert any(a["status"] == "active" for a in warning_alerts)

    # Filter by search_query
    toronto_alerts = api.get_weather_alerts(search_query="Toronto")
    assert len(toronto_alerts) == 1
    assert toronto_alerts[0]["status"] == "active"


@patch.object(EnvironmentCanadaAPI, "fetch_raw_alerts", return_value=SAMPLE_GEOJSON)
def test_get_alert_summary(mock_fetch):
    api = EnvironmentCanadaAPI()
    summary = api.get_alert_summary()
    assert summary["active_alerts_count"] == 2
    assert summary["by_province"]["ON"] == 1
    assert summary["by_province"]["AB"] == 1
    assert summary["advisories_count"] == 1
    assert summary["warnings_count"] == 1


@patch.object(EnvironmentCanadaAPI, "fetch_raw_alerts", return_value=SAMPLE_GEOJSON)
def test_get_alerts_near_coordinates(mock_fetch):
    api = EnvironmentCanadaAPI()
    # Point (-79.25, 43.75) is inside Toronto polygon bounding box
    inside_alerts = api.get_alerts_near_coordinates(latitude=43.75, longitude=-79.25)
    assert len(inside_alerts) == 1
    assert inside_alerts[0]["feature_name"] == "City of Toronto"

    # Point outside polygon
    outside_alerts = api.get_alerts_near_coordinates(latitude=50.0, longitude=-120.0)
    assert len(outside_alerts) == 0


@patch.object(EnvironmentCanadaAPI, "fetch_raw_alerts", return_value=SAMPLE_GEOJSON)
def test_get_alert_details(mock_fetch):
    api = EnvironmentCanadaAPI()
    details = api.get_alert_details("fea1-1968")
    assert details is not None
    assert details["feature_id"] == "fea1-1968"
    assert "geometry" in details
