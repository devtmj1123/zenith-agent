"""Weather tool — fetch current weather from wttr.in (free, no API key)."""
from __future__ import annotations
import aiohttp
import logging
import re
from typing import Dict, Any

log = logging.getLogger(__name__)


class WeatherTool:
    name = "weather"
    description = "Get current weather for a location"

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        location = params.get("location", "").strip()
        if not location:
            return {"success": False, "error": "No location provided"}

        try:
            url = f"https://wttr.in/{location}?format=j1"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        return {"success": False, "error": f"Weather API returned {resp.status}"}
                    data = await resp.json(content_type=None)

            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]
            area_name = area.get("areaName", [{}])[0].get("value", location)
            country = area.get("country", [{}])[0].get("value", "")

            temp_c = current.get("temp_C", "?")
            temp_f = current.get("temp_F", "?")
            feels_c = current.get("FeelsLikeC", "?")
            feels_f = current.get("FeelsLikeF", "?")
            humidity = current.get("humidity", "?")
            wind_kmph = current.get("windspeedKmph", "?")
            wind_dir = current.get("winddir16Point", "")
            desc = current.get("weatherDesc", [{}])[0].get("value", "")
            visibility = current.get("visibility", "?")
            uv = current.get("uvIndex", "?")
            precip_mm = current.get("precipMM", "?")

            result = {
                "success": True,
                "location": f"{area_name}, {country}" if country else area_name,
                "temperature": f"{temp_c}°C ({temp_f}°F)",
                "feels_like": f"{feels_c}°C ({feels_f}°F)",
                "condition": desc,
                "humidity": f"{humidity}%",
                "wind": f"{wind_kmph} km/h {wind_dir}",
                "precipitation": f"{precip_mm} mm",
                "visibility": f"{visibility} km",
                "uv_index": uv,
            }

            # Today's forecast
            weather_list = data.get("weather", [])
            if weather_list:
                today = weather_list[0]
                result["today_max"] = f"{today.get('maxtempC', '?')}°C"
                result["today_min"] = f"{today.get('mintempC', '?')}°C"
                # Hourly summary
                hourly = today.get("hourly", [])
                if hourly:
                    noon = hourly[4] if len(hourly) > 4 else hourly[0]
                    result["afternoon"] = noon.get("weatherDesc", [{}])[0].get("value", "")

            return result

        except aiohttp.ClientError as e:
            return {"success": False, "error": f"Network error: {e}"}
        except Exception as e:
            log.debug(f"Weather error: {e}")
            return {"success": False, "error": str(e)}
