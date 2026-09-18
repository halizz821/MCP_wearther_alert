"""Environment Canada Weather Alerts API Client.

Fetches weather alerts from https://api.weather.gc.ca/collections/weather-alerts/items
and cleans/groups features based on feature_id and alert metadata.
"""

import logging
from typing import Any, Dict, List, Optional, Union
import httpx
from shapely.geometry import Point, shape

logger = logging.getLogger(__name__)

ENVIRONMENT_CANADA_ALERTS_URL = "https://api.weather.gc.ca/collections/weather-alerts/items"

class EnvironmentCanadaAPI:
    """API Client for Environment Canada Weather Alerts."""

    def __init__(self, base_url: str = ENVIRONMENT_CANADA_ALERTS_URL, timeout: float = 15.0):
        self.base_url = base_url
        self.timeout = timeout

    def fetch_raw_alerts(self, limit: int = 2000) -> Optional[Dict[str, Any]]:
        """Fetches raw weather alerts synchronously from the Environment Canada OGC API.

        Queries the official Environment Canada weather-alerts endpoint conforming to
        the OGC API - Features specification.

        Args:
            limit: Maximum number of GeoJSON features to request from the API endpoint.
                Defaults to 2000.

        Returns:
            A dictionary parsed from the GeoJSON response containing:
                - "type": "FeatureCollection"
                - "features": List of GeoJSON Feature dictionaries, each having "geometry"
                  (Polygon or MultiPolygon) and "properties" with alert metadata.
                - "numberMatched": Total number of available features on the server.
                - "numberReturned": Number of features included in this payload.
            Returns None if an HTTP error or network failure occurs.
        """
        params = {
            "f": "json",
            "limit": limit,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.base_url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching weather alerts: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching weather alerts: {e}")
            return None

    
    def clean_and_group_features(self, raw_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cleans, normalizes, and groups raw GeoJSON features from Environment Canada.

        Filters out invalid or empty features, standardizes alert properties into a
        consistent internal structure, preserves distinct alert types/codes for the same
        geographic feature_id, and deduplicates successive updates of the same alert by
        retaining the most recently published item.

        Args:
            raw_data: Raw GeoJSON FeatureCollection dictionary returned by the API
                (containing a "features" list), or None.

        Returns:
            A list of cleaned alert dictionaries containing normalized attributes:
                - "id": Unique alert item ID (UUID or URI).
                - "feature_id": Geographic zone identifier code (e.g., '043200').
                - "feature_name_en" / "feature_name_fr": Alert zone name (e.g., 'Kingston - Odessa').
                - "province": Two-letter province/territory code (e.g., 'ON', 'QC').
                - "alert_code": Specific alert code (e.g., 'windWarning', 'snowfallWarning').
                - "alert_type": Broad classification ('warning', 'watch', 'advisory', 'statement').
                - "alert_name_en" / "alert_name_fr": Display title of the alert.
                - "alert_short_name_en" / "alert_short_name_fr": Short headline.
                - "alert_text_en" / "alert_text_fr": Full narrative text and safety advice.
                - "risk_colour_en" / "risk_colour_fr": Severity color (e.g., 'red', 'yellow').
                - "status_en" / "status_fr": Alert lifecycle status ('active', 'ended', 'actif', 'terminé').
                - "publication_datetime": ISO 8601 timestamp when alert was published.
                - "expiration_datetime": ISO 8601 timestamp when alert expires.
                - "validity_datetime": ISO 8601 timestamp when alert becomes valid.
                - "event_end_datetime": ISO 8601 timestamp when the event is expected to end.
                - "geometry": GeoJSON geometry dictionary (Polygon or MultiPolygon coordinates).
        """
        if not raw_data or "features" not in raw_data:
            return []

        features = raw_data.get("features", [])
        cleaned_alerts_by_key: Dict[str, Dict[str, Any]] = {}

        for item in features:
            props = item.get("properties", {})
            feature_id = props.get("feature_id") or item.get("id", "")
            
            # Extract geometry if present
            geom = item.get("geometry")

            cleaned_alert = {
                "id": item.get("id"),
                "feature_id": feature_id,
                "feature_name_en": props.get("feature_name_en"),
                "feature_name_fr": props.get("feature_name_fr"),
                "province": props.get("province"),
                "alert_code": props.get("alert_code"),
                "alert_type": props.get("alert_type"),
                "alert_name_en": props.get("alert_name_en"),
                "alert_name_fr": props.get("alert_name_fr"),
                "alert_short_name_en": props.get("alert_short_name_en"),
                "alert_short_name_fr": props.get("alert_short_name_fr"),
                "alert_text_en": props.get("alert_text_en"),
                "alert_text_fr": props.get("alert_text_fr"),
                "risk_colour_en": props.get("risk_colour_en"),
                "risk_colour_fr": props.get("risk_colour_fr"),
                "status_en": props.get("status_en", "active"),
                "status_fr": props.get("status_fr", "actif"),
                "publication_datetime": props.get("publication_datetime"),
                "expiration_datetime": props.get("expiration_datetime"),
                "validity_datetime": props.get("validity_datetime"),
                "event_end_datetime": props.get("event_end_datetime"),
                "geometry": geom,
            }

            # Construct composite key so multiple distinct alert types/codes for the same
            # feature_id are preserved, but duplicate updates of the same alert type are deduplicated.
            alert_code = props.get("alert_code")
            alert_type = props.get("alert_type")
            alert_name = props.get("alert_name_en") or props.get("alert_name_fr")

            if feature_id:
                if alert_code:
                    key = f"{feature_id}:{alert_code}"
                elif alert_type or alert_name:
                    key = f"{feature_id}:{alert_type}:{alert_name}"
                else:
                    key = item.get("id") or feature_id
            else:
                key = item.get("id") or str(len(cleaned_alerts_by_key))

            # Deduplicate by key: if key exists, keep the most recently published alert
            if key not in cleaned_alerts_by_key:
                cleaned_alerts_by_key[key] = cleaned_alert
            else:
                existing_pub = cleaned_alerts_by_key[key].get("publication_datetime") or ""
                new_pub = cleaned_alert.get("publication_datetime") or ""
                if new_pub > existing_pub:
                    cleaned_alerts_by_key[key] = cleaned_alert

        return list(cleaned_alerts_by_key.values())

    def get_weather_alerts(
        self,
        province: Optional[str] = None,
        alert_type: Optional[str] = None,
        search_query: Optional[str] = None,
        language: str = "en",
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Fetches, cleans, filters, and formats real-time weather alerts.

        Queries alerts, cleans them, applies optional filtering criteria
        (province, alert type, and keyword search across zone names and alert descriptions),
        and formats them according to the requested language.
        Note: Status is not used as a filter (all active and ended alerts are returned),
        and each alert dictionary includes its 'status' field in the returned JSON.

        Args:
            province: Optional two-letter Canadian province/territory abbreviation
                (e.g., 'ON', 'BC', 'AB', 'QC', 'NS', 'NB', 'MB', 'SK', 'PE', 'NL', 'YT', 'NT', 'NU').
            alert_type: Optional alert severity filter, matched case-insensitively
                ('warning', 'watch', 'advisory', 'statement').
            search_query: Case-insensitive search keyword matched against zone names
                (e.g., 'Kingston', 'Toronto') or alert text descriptions (e.g., 'snowfall', 'blizzard').
            language: Desired output language for text fields: 'en' for English (default) or 'fr' for French.
            limit: Maximum number of raw alerts to fetch before filtering. Defaults to 2000.

        Returns:
            A list of localized alert dictionaries formatted for downstream consumption.
            Each dictionary contains:
                - "id": Unique alert item ID string.
                - "feature_id": Zone/region identifier code.
                - "feature_name": Localized zone name (e.g., 'Kingston - Odessa - Frontenac Islands').
                - "province": Province code (e.g., 'ON').
                - "alert_code": Specific alert code (e.g., 'windWarning').
                - "alert_type": Alert classification (e.g., 'warning', 'watch').
                - "alert_name": Localized headline (e.g., 'Wind Warning').
                - "alert_short_name": Short localized alert label.
                - "alert_text": Full localized alert narrative and instructions.
                - "risk_colour": Risk level color ('red', 'yellow', etc.).
                - "status": Localized status ('active', 'ended', etc.).
                - "publication_datetime": ISO 8601 publication timestamp.
                - "expiration_datetime": ISO 8601 expiration timestamp.
                - "event_end_datetime": ISO 8601 event end timestamp.
            (Note: Heavy polygon geometry is excluded to optimize response size and token usage.)
        """
        raw_data = self.fetch_raw_alerts(limit=limit)
        cleaned_features = self.clean_and_group_features(raw_data)

        filtered = []
        for alert in cleaned_features:
            # Province filter
            if province and alert.get("province"):
                if alert["province"].upper() != province.upper():
                    continue

            # Alert type filter (e.g. warning, watch, advisory, statement)
            if alert_type and alert.get("alert_type"):
                if alert_type.lower() not in alert["alert_type"].lower():
                    continue

            # Search query filter in feature name or alert text
            if search_query:
                q = search_query.lower()
                name_en = (alert.get("feature_name_en") or "").lower()
                name_fr = (alert.get("feature_name_fr") or "").lower()
                text_en = (alert.get("alert_text_en") or "").lower()
                text_fr = (alert.get("alert_text_fr") or "").lower()
                if q not in name_en and q not in name_fr and q not in text_en and q not in text_fr:
                    continue

            # Exclude full geometry in concise output to save tokens, keep essential metadata
            concise_alert = self._format_alert_output(alert, language=language, include_geometry=False)
            filtered.append(concise_alert)

        return filtered

    def get_alert_summary(self, province: Optional[str] = None) -> Dict[str, Any]:
        """Provides an executive breakdown summary of active Canadian weather alerts.

        Scans active alerts and aggregates counts overall, by province, and by alert category.

        Args:
            province: Optional two-letter province code (e.g., 'ON', 'QC') to restrict
                the summary metrics to a single province.

        Returns:
            A dictionary containing aggregated alert statistics:
                - "total_features_scanned": Total number of distinct alerts processed.
                - "active_alerts_count": Total count of currently active alerts.
                - "by_province": Dictionary mapping province codes to active alert counts
                  (e.g., {"ON": 5, "BC": 2}).
                - "by_alert_type": Dictionary mapping alert categories to counts
                  (e.g., {"warning": 3, "watch": 1, "statement": 4}).
                - "warnings_count": Total active warnings.
                - "watches_count": Total active watches.
                - "advisories_count": Total active advisories.
                - "statements_count": Total active statements.
        """
        raw_data = self.fetch_raw_alerts()
        cleaned_features = self.clean_and_group_features(raw_data)

        summary = {
            "total_features_scanned": len(cleaned_features),
            "active_alerts_count": 0,
            "by_province": {},
            "by_alert_type": {},
            "warnings_count": 0,
            "watches_count": 0,
            "advisories_count": 0,
            "statements_count": 0,
        }

        for alert in cleaned_features:
            prov = alert.get("province") or "UNKNOWN"
            if province and prov.upper() != province.upper():
                continue

            st_en = (alert.get("status_en") or "").lower()
            if st_en == "ended":
                continue

            summary["active_alerts_count"] += 1
            summary["by_province"][prov] = summary["by_province"].get(prov, 0) + 1

            atype = (alert.get("alert_type") or "other").lower()
            summary["by_alert_type"][atype] = summary["by_alert_type"].get(atype, 0) + 1

            if "warning" in atype:
                summary["warnings_count"] += 1
            elif "watch" in atype:
                summary["watches_count"] += 1
            elif "advisory" in atype:
                summary["advisories_count"] += 1
            elif "statement" in atype:
                summary["statements_count"] += 1

        return summary

    def get_alerts_near_coordinates(
        self,
        latitude: float,
        longitude: float,
        language: str = "en",
    ) -> List[Dict[str, Any]]:
        """Finds weather alerts containing or intersecting specific GPS coordinates.

        Uses Shapely spatial geometry to evaluate whether the given latitude/longitude point
        falls within or touches the polygon boundary of each alert region. This completely
        bypasses inconsistent naming conventions across compound geographic zones.
        Note: Alerts of all statuses are returned, and each alert includes its 'status' field in the returned JSON.

        Args:
            latitude: Latitude in decimal degrees (e.g., 44.2312 for Kingston, ON).
            longitude: Longitude in decimal degrees (e.g., -76.4860 for Kingston, ON).
            language: Preferred output language: 'en' (English, default) or 'fr' (French).

        Returns:
            A list of localized alert dictionaries (without heavy geometry polygons)
            for alerts whose spatial boundary polygon encloses or touches the specified coordinate.
        """
        point = Point(longitude, latitude)
        raw_data = self.fetch_raw_alerts()
        cleaned_features = self.clean_and_group_features(raw_data)

        matching_alerts = []
        for alert in cleaned_features:
            geom_dict = alert.get("geometry")
            if not geom_dict:
                continue

            try:
                geom_shape = shape(geom_dict)
                if geom_shape.contains(point) or geom_shape.touches(point):
                    matching_alerts.append(
                        self._format_alert_output(alert, language=language, include_geometry=False)
                    )
            except Exception as e:
                logger.debug(f"Error checking point containment for feature {alert.get('feature_id')}: {e}")
                continue

        return matching_alerts

    def get_alert_details(self, feature_id_or_id: str, language: str = "en") -> Optional[Dict[str, Any]]:
        """Retrieves complete details, including boundary geometry, for a specific alert.

        Looks up an alert matching either the geographic feature_id (zone code) or the
        unique item ID, and formats it in the requested language while retaining the
        full GeoJSON boundary geometry.

        Args:
            feature_id_or_id: Unique alert item identifier or geographic feature ID
                (e.g., '043200' or item UUID).
            language: Preferred output language: 'en' (English, default) or 'fr' (French).

        Returns:
            A localized dictionary containing all metadata fields plus:
                - "geometry": GeoJSON geometry dictionary (coordinates defining the boundary polygon),
            or None if no matching alert is found.
        """
        raw_data = self.fetch_raw_alerts()
        cleaned_features = self.clean_and_group_features(raw_data)

        for alert in cleaned_features:
            if alert.get("feature_id") == feature_id_or_id or alert.get("id") == feature_id_or_id:
                return self._format_alert_output(alert, language=language, include_geometry=True)

        return None

    def _format_alert_output(
        self,
        alert: Dict[str, Any],
        language: str = "en",
        include_geometry: bool = False,
    ) -> Dict[str, Any]:
        """Formats an internal alert dictionary based on target language and geometry preference.

        Extracts the language-specific version of bilingual fields (English vs French)
        and conditionally attaches the GeoJSON boundary geometry.

        Args:
            alert: Normalized alert dictionary containing bilingual fields.
            language: Target language code ('en' or 'fr'). Defaults to 'en'.
            include_geometry: Whether to include the GeoJSON 'geometry' field in the output.
                Defaults to False to minimize token and payload size.

        Returns:
            A dictionary with localized keys ('feature_name', 'alert_name', 'alert_text',
            'status', etc.) and optionally 'geometry'.
        """
        lang = language.lower()
        output = {
            "id": alert.get("id"),
            "feature_id": alert.get("feature_id"),
            "feature_name": alert.get("feature_name_en") if lang == "en" else alert.get("feature_name_fr"),
            "province": alert.get("province"),
            "alert_code": alert.get("alert_code"),
            "alert_type": alert.get("alert_type"),
            "alert_name": alert.get("alert_name_en") if lang == "en" else alert.get("alert_name_fr"),
            "alert_short_name": alert.get("alert_short_name_en") if lang == "en" else alert.get("alert_short_name_fr"),
            "alert_text": alert.get("alert_text_en") if lang == "en" else alert.get("alert_text_fr"),
            "risk_colour": alert.get("risk_colour_en") if lang == "en" else alert.get("risk_colour_fr"),
            "status": alert.get("status_en") if lang == "en" else alert.get("status_fr"),
            "publication_datetime": alert.get("publication_datetime"),
            "expiration_datetime": alert.get("expiration_datetime"),
            "event_end_datetime": alert.get("event_end_datetime"),
        }

        if include_geometry:
            output["geometry"] = alert.get("geometry")

        return output
