from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
from typing import Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mcp.server.fastmcp import FastMCP, Image
from pydantic import BaseModel, ConfigDict, Field

from .repository import make_repository


def _default_db_url() -> str:
    if os.environ.get("TRAILS_DB_URL"):
        return os.environ["TRAILS_DB_URL"]

    # Docker volume mount
    if Path("/data").is_dir():
        return "sqlite:////data/trails.db"

    # Dev fallback: data/ next to the repo root (only works in editable install)
    repo_root = Path(__file__).resolve().parents[3]
    db_file = repo_root / "data" / "trails.db"
    if db_file.exists():
        return f"sqlite:///{db_file}"

    return "sqlite:////data/trails.db"


DEFAULT_DB_URL = _default_db_url()


def _default_asset_path() -> Path:
    assets_dir = Path(__file__).resolve().parents[3] / "assets"
    preferred = assets_dir / "Traumschleifen-Saar-Hunsrück.json"
    if preferred.exists():
        return preferred

    fallback = assets_dir / "Traumschleifen-Saar-Hunsrueck.json"
    if fallback.exists():
        return fallback

    matches = sorted(assets_dir.glob("Traumschleifen-Saar-Hunsr*ck.json"))
    if matches:
        return matches[0]

    return preferred


DEFAULT_ASSET_PATH = _default_asset_path()


mcp = FastMCP("trails", stateless_http=True, json_response=True)
repo = make_repository(DEFAULT_DB_URL)
repo.init_schema()


class ImportTrailsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    asset_path: str = Field(default=str(DEFAULT_ASSET_PATH))
    activity_type: str = Field(default="hiking", description="Example: hiking, biking, mtb, gravel, road")


class ListTrailsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    activity_type: str | None = Field(default=None, description="Filter by activity type (e.g., hiking, biking)")
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    hiked: bool | None = Field(default=None, description="true: only hiked, false: only not hiked, null: all")
    rated: bool | None = Field(default=None, description="true: rated, false: unrated, null: all")
    sort_by: Literal["rating", "distance_km", "elevation_gain_m", "drive_time_min", "last_executed_on"] | None = Field(
        default=None,
        description="Sort by rating, distance, ascent, or drive time",
    )
    search: str | None = Field(default=None)
    date_from: str | None = Field(default=None, description="Filter hikes on/after date (YYYY-MM-DD)")
    date_to: str | None = Field(default=None, description="Filter hikes on/before date (YYYY-MM-DD)")
    min_length_km: float | None = Field(default=None, ge=0)
    max_length_km: float | None = Field(default=None, ge=0)
    min_hike_duration_min: float | None = Field(default=None, ge=0)
    max_hike_duration_min: float | None = Field(default=None, ge=0)
    min_ascend_m: int | None = Field(default=None, ge=0)
    max_ascend_m: int | None = Field(default=None, ge=0)
    min_drive_duration_min: float | None = Field(default=None, ge=0)
    max_drive_duration_min: float | None = Field(default=None, ge=0)
    trail_type: str | None = Field(default=None, description="Example: Traumschleife, Auto-Pedestre")
    format: Literal["json", "table"] = Field(default="json", description="Output format: json or markdown table")


class GetTrailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=2)
    activity_type: str | None = Field(default=None)


class AddImpressionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    execution_id: int = Field(..., ge=1)
    overall_rating: float | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None)
    weather: str | None = Field(default=None)
    difficulty: str | None = Field(default=None)


class AddTrailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=2)
    activity_type: str = Field(default="hiking")
    trail_type: str | None = Field(default=None)
    url: str | None = Field(default=None)
    description: str | None = Field(default=None)
    distance_km: float | None = Field(default=None, ge=0)
    hike_duration_min: float | None = Field(default=None, ge=0)
    elevation_gain_m: int | None = Field(default=None, ge=0)
    elevation_loss_m: int | None = Field(default=None, ge=0)
    drive_distance_km: float | None = Field(default=None, ge=0)
    drive_time_min: float | None = Field(default=None, ge=0)
    gpx_url: str | None = Field(default=None)
    garmin_course_url: str | None = Field(default=None)


class AddExecutionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trail_name: str = Field(..., min_length=2)
    activity_type: str | None = Field(default=None)
    executed_on: str = Field(..., description="Date string, e.g. 2026-05-02")


class EditExecutionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    execution_id: int = Field(..., ge=1)
    executed_on: str = Field(..., description="Date string, e.g. 2026-05-02")


class DeleteExecutionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    execution_id: int = Field(..., ge=1)


class EditImpressionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    impression_id: int = Field(..., ge=1)
    overall_rating: float | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None)
    weather: str | None = Field(default=None)
    difficulty: str | None = Field(default=None)


class DeleteImpressionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    impression_id: int = Field(..., ge=1)


class ListImpressionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trail_name: str = Field(..., min_length=2)
    activity_type: str | None = Field(default=None)
    limit: int = Field(default=20, ge=1, le=200)


class ListExecutionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trail_name: str | None = Field(default=None, min_length=2, description="Filter by trail name. Omit to list across all trails.")
    activity_type: str | None = Field(default=None)
    limit: int = Field(default=20, ge=1, le=200)
    sort_by: Literal["executed_on_asc", "executed_on_desc"] | None = Field(
        default="executed_on_desc",
        description="Sort order. Defaults to most-recent first.",
    )
    after: str | None = Field(default=None, description="Only executions on or after this date (YYYY-MM-DD)")
    before: str | None = Field(default=None, description="Only executions on or before this date (YYYY-MM-DD)")


class SetTrailGarminCourseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trail_name: str = Field(..., min_length=2)
    activity_type: str | None = Field(default=None)
    garmin_course_url: str | None = Field(default=None)


class EditTrailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trail_name: str = Field(..., min_length=2)
    activity_type: str | None = Field(default=None)
    new_name: str | None = Field(default=None, min_length=2)
    trail_type: str | None = Field(default=None)
    url: str | None = Field(default=None)
    description: str | None = Field(default=None)
    distance_km: float | None = Field(default=None, ge=0)
    hike_duration_min: float | None = Field(default=None, ge=0)
    elevation_gain_m: int | None = Field(default=None, ge=0)
    elevation_loss_m: int | None = Field(default=None, ge=0)
    drive_distance_km: float | None = Field(default=None, ge=0)
    drive_time_min: float | None = Field(default=None, ge=0)
    gpx_url: str | None = Field(default=None)
    garmin_course_url: str | None = Field(default=None)


def _extract_hike_dates(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _extract_hike_duration_min(description: str | None) -> float | None:
    if not description:
        return None

    text = description.lower()
    if "gehzeit" not in text:
        return None

    segment = text.split("gehzeit", 1)[1]
    stop_markers = ("saison", "profil", "länge", "distanz")
    cut_at = len(segment)
    for marker in stop_markers:
        idx = segment.find(marker)
        if idx != -1:
            cut_at = min(cut_at, idx)
    segment = segment[:cut_at]

    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[\.,]\d+)?", segment)]
    if not nums:
        return None

    if "bis" in text and len(nums) >= 2:
        hours = (nums[0] + nums[1]) / 2.0
    else:
        hours = nums[0]
    return round(hours * 60.0, 1)


def _extract_trail_type(name: str) -> str:
    normalized = name.strip().lower()
    if normalized.startswith("traumschleife"):
        return "Traumschleife"
    if normalized.startswith("auto-pedestre") or normalized.startswith("auto-pédestre"):
        return "Auto-Pedestre"
    return "Other"


@mcp.tool(name="import_trails_from_asset")
async def import_trails_from_asset(params: ImportTrailsInput) -> str:
    path = Path(params.asset_path)
    if not path.exists():
        return f"Error: asset file not found: {path}"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"Error: could not parse JSON: {type(exc).__name__}: {exc}"

    trails = payload.get("Traumschleifen", [])
    if not isinstance(trails, list):
        return "Error: invalid JSON structure: key 'Traumschleifen' must be an array"

    imported = 0
    for row in trails:
        if not isinstance(row, dict):
            continue
        name = row.get("Name")
        if not isinstance(name, str) or not name.strip():
            continue

        record = {
            "name": name.strip(),
            "activity_type": params.activity_type,
            "trail_type": (
                row.get("Trail Type")
                or row.get("Typ")
                or row.get("Wegtyp")
                or _extract_trail_type(name)
            ),
            "url": row.get("URL"),
            "description": row.get("Beschreibung"),
            "distance_km": row.get("Distanz (km)"),
            "hike_duration_min": _extract_hike_duration_min(row.get("Beschreibung")),
            "elevation_gain_m": row.get("Höhengewinn (m)"),
            "elevation_loss_m": row.get("Höhenverlust (m)"),
            "drive_distance_km": row.get("Fahrtstrecke (km)"),
            "drive_time_min": row.get("Fahrzeit (min)"),
            "gpx_url": row.get("GPX URL"),
            "garmin_course_url": row.get("Garmin Course URL"),
            "source_hike_dates": _extract_hike_dates(row.get("Wanderdaten")),
        }
        repo.upsert_trail(record)
        imported += 1

    return json.dumps(
        {
            "ok": True,
            "imported": imported,
            "activity_type": params.activity_type,
            "source": str(path),
            "db_url": DEFAULT_DB_URL,
        },
        indent=2,
    )


@mcp.tool(name="list_trails")
async def list_trails(params: ListTrailsInput) -> str:
    rows = repo.list_trails(
        limit=params.limit,
        offset=params.offset,
        activity_type=params.activity_type,
        only_hiked=params.hiked,
        rated=params.rated,
        sort_by=params.sort_by,
        search=params.search,
        date_from=params.date_from,
        date_to=params.date_to,
        min_length_km=params.min_length_km,
        max_length_km=params.max_length_km,
        min_hike_duration_min=params.min_hike_duration_min,
        max_hike_duration_min=params.max_hike_duration_min,
        min_ascend_m=params.min_ascend_m,
        max_ascend_m=params.max_ascend_m,
        min_drive_duration_min=params.min_drive_duration_min,
        max_drive_duration_min=params.max_drive_duration_min,
        trail_type=params.trail_type,
    )
    result = [
        {
            "id": r.id,
            "name": r.name,
            "activity_type": r.activity_type,
            "trail_type": r.trail_type,
            "distance_km": r.distance_km,
            "hike_duration_min": r.hike_duration_min,
            "elevation_gain_m": r.elevation_gain_m,
            "drive_distance_km": r.drive_distance_km,
            "drive_time_min": r.drive_time_min,
            "avg_overall_rating": r.avg_overall_rating,
            "garmin_course_url": r.garmin_course_url,
        }
        for r in rows
    ]

    if params.format == "table":
        return _trails_as_markdown_table(result)

    return json.dumps({"count": len(result), "items": result}, indent=2)


@mcp.tool(name="get_trail")
async def get_trail(params: GetTrailInput) -> str:
    trail = repo.get_trail_by_name(params.name, params.activity_type)
    if not trail:
        return f"Error: trail not found: {params.name}"

    result = {
        "id": trail.id,
        "name": trail.name,
        "activity_type": trail.activity_type,
        "trail_type": trail.trail_type,
        "url": trail.url,
        "description": trail.description,
        "distance_km": trail.distance_km,
        "hike_duration_min": trail.hike_duration_min,
        "elevation_gain_m": trail.elevation_gain_m,
        "elevation_loss_m": trail.elevation_loss_m,
        "drive_distance_km": trail.drive_distance_km,
        "drive_time_min": trail.drive_time_min,
        "gpx_url": trail.gpx_url,
        "garmin_course_url": trail.garmin_course_url,
    }
    return json.dumps(result, indent=2)


@mcp.tool(name="add_trail")
async def add_trail(params: AddTrailInput) -> str:
    payload = {
        "name": params.name,
        "activity_type": params.activity_type,
        "trail_type": params.trail_type,
        "url": params.url,
        "description": params.description,
        "distance_km": params.distance_km,
        "hike_duration_min": params.hike_duration_min,
        "elevation_gain_m": params.elevation_gain_m,
        "elevation_loss_m": params.elevation_loss_m,
        "drive_distance_km": params.drive_distance_km,
        "drive_time_min": params.drive_time_min,
        "gpx_url": params.gpx_url,
        "garmin_course_url": params.garmin_course_url,
    }

    try:
        trail = repo.add_trail(payload)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return json.dumps(
        {
            "id": trail.id,
            "name": trail.name,
            "activity_type": trail.activity_type,
            "trail_type": trail.trail_type,
            "url": trail.url,
            "description": trail.description,
            "distance_km": trail.distance_km,
            "hike_duration_min": trail.hike_duration_min,
            "elevation_gain_m": trail.elevation_gain_m,
            "elevation_loss_m": trail.elevation_loss_m,
            "drive_distance_km": trail.drive_distance_km,
            "drive_time_min": trail.drive_time_min,
            "gpx_url": trail.gpx_url,
            "garmin_course_url": trail.garmin_course_url,
        },
        indent=2,
    )


@mcp.tool(name="add_impression")
async def add_impression(params: AddImpressionInput) -> str:
    try:
        impression = repo.add_impression(
            execution_id=params.execution_id,
            overall_rating=params.overall_rating,
            notes=params.notes,
            weather=params.weather,
            difficulty=params.difficulty,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return json.dumps(
        {
            "id": impression.id,
            "execution_id": impression.execution_id,
            "trail_id": impression.trail_id,
            "overall_rating": impression.overall_rating,
            "notes": impression.notes,
            "weather": impression.weather,
            "difficulty": impression.difficulty,
        },
        indent=2,
    )


@mcp.tool(name="add_execution")
async def add_execution(params: AddExecutionInput) -> str:
    try:
        execution = repo.record_execution(
            trail_name=params.trail_name,
            executed_on=params.executed_on,
            activity_type=params.activity_type,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return json.dumps(
        {
            "id": execution.id,
            "trail_id": execution.trail_id,
            "executed_on": execution.executed_on,
        },
        indent=2,
    )


@mcp.tool(name="edit_execution")
async def edit_execution(params: EditExecutionInput) -> str:
    try:
        execution = repo.update_execution(
            execution_id=params.execution_id,
            executed_on=params.executed_on,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return json.dumps(
        {
            "id": execution.id,
            "trail_id": execution.trail_id,
            "executed_on": execution.executed_on,
        },
        indent=2,
    )


@mcp.tool(name="delete_execution")
async def delete_execution(params: DeleteExecutionInput) -> str:
    try:
        deleted = repo.delete_execution(execution_id=params.execution_id)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    if not deleted:
        return f"Error: ValueError: Execution not found: {params.execution_id}"

    return json.dumps({"ok": True, "deleted_id": params.execution_id}, indent=2)


@mcp.tool(name="edit_impression")
async def edit_impression(params: EditImpressionInput) -> str:
    updates: dict[str, float | str | None] = {}
    for field_name in ("overall_rating", "notes", "weather", "difficulty"):
        if field_name in params.model_fields_set:
            updates[field_name] = getattr(params, field_name)

    try:
        impression = repo.update_impression(
            impression_id=params.impression_id,
            updates=updates,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return json.dumps(
        {
            "id": impression.id,
            "execution_id": impression.execution_id,
            "trail_id": impression.trail_id,
            "overall_rating": impression.overall_rating,
            "notes": impression.notes,
            "weather": impression.weather,
            "difficulty": impression.difficulty,
        },
        indent=2,
    )


@mcp.tool(name="delete_impression")
async def delete_impression(params: DeleteImpressionInput) -> str:
    try:
        deleted = repo.delete_impression(impression_id=params.impression_id)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    if not deleted:
        return f"Error: ValueError: Impression not found: {params.impression_id}"

    return json.dumps({"ok": True, "deleted_id": params.impression_id}, indent=2)


@mcp.tool(name="list_impressions")
async def list_impressions(params: ListImpressionsInput) -> str:
    try:
        rows = repo.list_impressions(
            trail_name=params.trail_name,
            limit=params.limit,
            activity_type=params.activity_type,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    result = [
        {
            "id": row.id,
            "execution_id": row.execution_id,
            "trail_id": row.trail_id,
            "overall_rating": row.overall_rating,
            "notes": row.notes,
            "weather": row.weather,
            "difficulty": row.difficulty,
        }
        for row in rows
    ]
    return json.dumps({"count": len(result), "items": result}, indent=2)


@mcp.tool(name="list_executions")
async def list_executions(params: ListExecutionsInput) -> str:
    try:
        rows = repo.list_executions(
            trail_name=params.trail_name,
            limit=params.limit,
            activity_type=params.activity_type,
            sort_by=params.sort_by,
            after=params.after,
            before=params.before,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    result = [
        {
            "id": row.id,
            "trail_id": row.trail_id,
            "trail_name": row.trail_name,
            "executed_on": row.executed_on,
        }
        for row in rows
    ]
    return json.dumps({"count": len(result), "items": result}, indent=2)


@mcp.tool(name="set_trail_garmin_course")
async def set_trail_garmin_course(params: SetTrailGarminCourseInput) -> str:
    if not params.garmin_course_url:
        return "Error: garmin_course_url is required"

    try:
        trail = repo.update_trail_garmin_course(
            trail_name=params.trail_name,
            activity_type=params.activity_type,
            garmin_course_url=params.garmin_course_url,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return json.dumps(
        {
            "id": trail.id,
            "name": trail.name,
            "activity_type": trail.activity_type,
            "garmin_course_url": trail.garmin_course_url,
        },
        indent=2,
    )


@mcp.tool(name="edit_trail")
async def edit_trail(params: EditTrailInput) -> str:
    updates: dict[str, float | int | str | None] = {}
    editable_fields = (
        "trail_type",
        "url",
        "description",
        "distance_km",
        "hike_duration_min",
        "elevation_gain_m",
        "elevation_loss_m",
        "drive_distance_km",
        "drive_time_min",
        "gpx_url",
        "garmin_course_url",
    )

    if "new_name" in params.model_fields_set:
        updates["name"] = params.new_name

    for field_name in editable_fields:
        if field_name in params.model_fields_set:
            updates[field_name] = getattr(params, field_name)

    try:
        trail = repo.update_trail(
            trail_name=params.trail_name,
            activity_type=params.activity_type,
            updates=updates,
        )
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    return json.dumps(
        {
            "id": trail.id,
            "name": trail.name,
            "activity_type": trail.activity_type,
            "trail_type": trail.trail_type,
            "url": trail.url,
            "description": trail.description,
            "distance_km": trail.distance_km,
            "hike_duration_min": trail.hike_duration_min,
            "elevation_gain_m": trail.elevation_gain_m,
            "elevation_loss_m": trail.elevation_loss_m,
            "drive_distance_km": trail.drive_distance_km,
            "drive_time_min": trail.drive_time_min,
            "gpx_url": trail.gpx_url,
            "garmin_course_url": trail.garmin_course_url,
        },
        indent=2,
    )


def _fmt_duration(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m"


def _trails_as_markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_No trails found._"

    lines = [
        "| Name | Type | km | Ascent (m) | Duration | Drive (min) | ★ |",
        "|------|------|----|------------|----------|-------------|---|",
    ]
    for r in rows:
        dist = f"{r['distance_km']:.1f}" if r["distance_km"] is not None else "—"
        ascent = str(r["elevation_gain_m"]) if r["elevation_gain_m"] is not None else "—"
        dur = _fmt_duration(r["hike_duration_min"])
        drive = f"{r['drive_time_min']:.0f}" if r["drive_time_min"] is not None else "—"
        rating = f"{r['avg_overall_rating']:.1f}" if r["avg_overall_rating"] is not None else "—"
        trail_type = r["trail_type"] or "—"
        lines.append(f"| {r['name']} | {trail_type} | {dist} | {ascent} | {dur} | {drive} | {rating} |")

    return "\n".join(lines)


@mcp.tool(name="get_trails_overview")
async def get_trails_overview() -> Image:
    try:
        stats = repo.get_stats()
    except Exception as exc:
        raise RuntimeError(f"Could not fetch trail stats — is the API reachable? ({exc})") from exc

    accent = "#4a90d9"
    hiked_color = "#2ecc71"
    not_hiked_color = "#bdc3c7"

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Trails Overview", fontsize=15, fontweight="bold", y=0.98)
    fig.patch.set_facecolor("#f8f9fa")
    for ax in axes.flat:
        ax.set_facecolor("#ffffff")

    # Hiked vs not-hiked
    ax = axes[0, 0]
    not_hiked = stats.total - stats.hiked
    ax.bar(["Hiked", "Not hiked"], [stats.hiked, not_hiked],
           color=[hiked_color, not_hiked_color], edgecolor="white", linewidth=0.5)
    ax.set_title("Hiked Status", fontweight="bold")
    ax.set_ylabel("Trails")
    for bar, val in zip(ax.patches, [stats.hiked, not_hiked]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                str(val), ha="center", va="bottom", fontsize=10)

    # Rating distribution
    ax = axes[0, 1]
    if stats.ratings:
        bins = [r / 2 - 0.25 for r in range(2, 12)]
        ax.hist(stats.ratings, bins=bins, color=accent, edgecolor="white", linewidth=0.5)
        ax.set_title("Rating Distribution", fontweight="bold")
        ax.set_xlabel("Stars")
        ax.set_ylabel("Count")
        ax.set_xticks([1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5])
        ax.set_xlim(0.75, 5.25)
    else:
        ax.text(0.5, 0.5, "No ratings yet", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="#888")
        ax.set_title("Rating Distribution", fontweight="bold")

    # Distance histogram
    ax = axes[1, 0]
    if stats.distances_km:
        ax.hist(stats.distances_km, bins=15, color="#9b59b6", edgecolor="white", linewidth=0.5)
        ax.set_title("Distance Distribution", fontweight="bold")
        ax.set_xlabel("km")
        ax.set_ylabel("Trails")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Distance Distribution", fontweight="bold")

    # Drive time histogram
    ax = axes[1, 1]
    if stats.drive_times_min:
        ax.hist(stats.drive_times_min, bins=15, color="#e67e22", edgecolor="white", linewidth=0.5)
        ax.set_title("Drive Time Distribution", fontweight="bold")
        ax.set_xlabel("minutes")
        ax.set_ylabel("Trails")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Drive Time Distribution", fontweight="bold")

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return Image(data=buf.read(), format="png")
