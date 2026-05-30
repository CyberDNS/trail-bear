from __future__ import annotations

import asyncio
import json
from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1"
USER_AGENT = "driving-distance-mcp/1.0"
TIMEOUT = 15.0

Profile = Literal["driving", "cycling", "walking"]

mcp = FastMCP("driving_distance", stateless_http=True, json_response=True)


class DrivingInfoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    origin: str = Field(..., min_length=2)
    destination: str = Field(..., min_length=2)
    profile: Profile = Field(default="driving")


class CompareRoutesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    origin: str = Field(..., min_length=2)
    destination: str = Field(..., min_length=2)


def format_duration(seconds: float) -> str:
    total = int(seconds)
    hours, minutes = divmod(total // 60, 60)
    return f"{hours}h {minutes}min" if hours > 0 else f"{minutes} min"


def format_distance(meters: float) -> str:
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{int(round(meters))} m"


def parse_coord(value: str) -> tuple[float, float] | None:
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    return None


async def geocode(address: str) -> tuple[float, float, str]:
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as client:
        response = await client.get(NOMINATIM_URL, params={"q": address, "format": "json", "limit": 1})
        response.raise_for_status()
        payload = response.json()
    if not payload:
        raise ValueError(f'Could not find location: "{address}"')
    return float(payload[0]["lat"]), float(payload[0]["lon"]), payload[0]["display_name"]


async def resolve_location(value: str) -> tuple[float, float, str]:
    coord = parse_coord(value)
    if coord:
        return coord[0], coord[1], value
    return await geocode(value)


async def fetch_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    profile: Profile,
) -> dict:
    coords = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    url = f"{OSRM_URL}/{profile}/{coords}"
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as client:
        response = await client.get(url, params={"overview": "false", "steps": "false"})
        response.raise_for_status()
        payload = response.json()
    if payload.get("code") != "Ok":
        raise ValueError(f"Routing failed: {payload.get('code', 'unknown')}")
    return payload["routes"][0]


@mcp.tool(name="get_driving_info")
async def get_driving_info(params: DrivingInfoInput) -> str:
    try:
        o_lat, o_lon, o_label = await resolve_location(params.origin)
        d_lat, d_lon, d_label = await resolve_location(params.destination)
        route = await fetch_route(o_lat, o_lon, d_lat, d_lon, params.profile)
        result = {
            "origin_resolved": o_label,
            "destination_resolved": d_label,
            "profile": params.profile,
            "distance_meters": round(route["distance"]),
            "distance": format_distance(route["distance"]),
            "duration_seconds": round(route["duration"]),
            "duration": format_duration(route["duration"]),
        }
        return json.dumps(result, indent=2)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


@mcp.tool(name="compare_routes")
async def compare_routes(params: CompareRoutesInput) -> str:
    try:
        o_lat, o_lon, o_label = await resolve_location(params.origin)
        d_lat, d_lon, d_label = await resolve_location(params.destination)
        profiles: list[Profile] = ["driving", "cycling", "walking"]

        async def safe_fetch(profile: Profile) -> dict | None:
            try:
                return await fetch_route(o_lat, o_lon, d_lat, d_lon, profile)
            except Exception:
                return None

        raw_routes = await asyncio.gather(*[safe_fetch(profile) for profile in profiles])

        routes: dict[str, dict] = {}
        for profile, route in zip(profiles, raw_routes):
            if not route:
                routes[profile] = {"error": "unavailable"}
                continue
            routes[profile] = {
                "distance_meters": round(route["distance"]),
                "distance": format_distance(route["distance"]),
                "duration_seconds": round(route["duration"]),
                "duration": format_duration(route["duration"]),
            }

        result = {
            "origin_resolved": o_label,
            "destination_resolved": d_label,
            "routes": routes,
        }
        return json.dumps(result, indent=2)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"
