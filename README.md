# Environment Canada Weather Alerts MCP Server

An Model Context Protocol (MCP) server providing real-time weather alerts and warnings from the Environment Canada API (`https://api.weather.gc.ca/collections/weather-alerts/items`).

## Features

- **Tools**:
  - `get_weather_alerts`: Search and filter weather alerts by province, alert type, or keyword (includes status in results).
  - `get_alert_summary`: View national and provincial alert counts (warnings, watches, advisories).
  - `get_alerts_near_coordinates`: Check for weather alerts affecting a specific latitude and longitude.
  - `get_alert_details`: Retrieve full alert details, affected features, and official English/French text by feature ID.
- **Resources**:
  - `weather-alerts://active`: Live JSON feed of active Canadian weather alerts.
  - `weather-alerts://summary`: Executive summary statistics.
  - `weather-alerts://province/{province}`: Province-filtered weather alert JSON streams (e.g. `ON`, `BC`, `AB`).
- **Prompts**:
  - `analyze_weather_safety`: Generates emergency safety advice based on current weather warnings.
  - `daily_weather_alert_briefing`: Generates concise daily weather risk briefings for target regions.
  - `severe_weather_report`: Generates structured incident reports for severe weather events.

## Running the MCP Server (Zero Setup)

With `uv` installed, there is **no need to manually create a virtual environment or run pip install**. `uvx` will automatically provision an isolated environment, resolve dependencies from `pyproject.toml`, and run the server:

```bash
# Run directly from the project directory:
uvx --from . environment-canada-mcp

# Or run from anywhere by specifying the absolute path:
uvx --from /path/to/MCP_wearther_alert environment-canada-mcp
```

### Local Development / Contributing
If you are developing or modifying the code directly:
```bash
uv venv
uv pip install -e ".[dev]"
```

## Integration with MCP Clients

Add the server to your MCP client configuration. Because it uses `uvx`, dependencies install automatically in the background on first launch with zero upfront manual steps.

> **Note**: Replace `/path/to/MCP_wearther_alert` with the actual absolute path to where you cloned this repository (e.g. `C:/projects/MCP_wearther_alert` on Windows or `/home/user/MCP_wearther_alert` on Linux/macOS).

### Claude Desktop Configuration

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "environment-canada-weather": {
      "command": "uvx",
      "args": [
        "--from",
        "/path/to/MCP_wearther_alert",
        "environment-canada-mcp"
      ]
    }
  }
}
```

### Cursor / Antigravity / VS Code Configuration

Add the following to your MCP settings:

```json
{
  "mcp": {
    "servers": {
      "environment-canada-weather": {
        "command": "uvx",
        "args": [
          "--from",
          "/path/to/MCP_wearther_alert",
          "environment-canada-mcp"
        ]
      }
    }
  }
}
```
