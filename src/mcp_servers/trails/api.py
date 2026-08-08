"""FastAPI REST API for the trails repository."""

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .repository import TrailsRepository


def make_api(repo: TrailsRepository) -> FastAPI:
    api = FastAPI(title="TrailBear API", version="1.0.0")

    # ── Pydantic schemas ──────────────────────────────────────────────────────

    class TrailCreate(BaseModel):
        name: str = Field(..., min_length=2)
        activity_type: str = "hiking"
        trail_type: str | None = None
        url: str | None = None
        description: str | None = None
        distance_km: float | None = Field(default=None, ge=0)
        hike_duration_min: float | None = Field(default=None, ge=0)
        elevation_gain_m: int | None = Field(default=None, ge=0)
        elevation_loss_m: int | None = Field(default=None, ge=0)
        drive_distance_km: float | None = Field(default=None, ge=0)
        drive_time_min: float | None = Field(default=None, ge=0)
        gpx_url: str | None = None
        garmin_course_url: str | None = None

    class TrailUpdate(BaseModel):
        new_name: str | None = Field(default=None, min_length=2)
        trail_type: str | None = None
        url: str | None = None
        description: str | None = None
        distance_km: float | None = Field(default=None, ge=0)
        hike_duration_min: float | None = Field(default=None, ge=0)
        elevation_gain_m: int | None = Field(default=None, ge=0)
        elevation_loss_m: int | None = Field(default=None, ge=0)
        drive_distance_km: float | None = Field(default=None, ge=0)
        drive_time_min: float | None = Field(default=None, ge=0)
        gpx_url: str | None = None
        garmin_course_url: str | None = None

    class ExecutionCreate(BaseModel):
        executed_on: str

    class ExecutionUpdate(BaseModel):
        executed_on: str

    class ImpressionCreate(BaseModel):
        overall_rating: float | None = Field(default=None, ge=1, le=5)
        notes: str | None = None
        weather: str | None = None
        difficulty: str | None = None

    class ImpressionUpdate(BaseModel):
        overall_rating: float | None = Field(default=None, ge=1, le=5)
        notes: str | None = None
        weather: str | None = None
        difficulty: str | None = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _trail_dict(t) -> dict:
        return {
            "id": t.id,
            "name": t.name,
            "activity_type": t.activity_type,
            "trail_type": t.trail_type,
            "url": t.url,
            "description": t.description,
            "distance_km": t.distance_km,
            "hike_duration_min": t.hike_duration_min,
            "elevation_gain_m": t.elevation_gain_m,
            "elevation_loss_m": t.elevation_loss_m,
            "drive_distance_km": t.drive_distance_km,
            "drive_time_min": t.drive_time_min,
            "avg_overall_rating": t.avg_overall_rating,
            "gpx_url": t.gpx_url,
            "garmin_course_url": t.garmin_course_url,
            "last_executed_on": t.last_executed_on,
        }

    def _execution_dict(e) -> dict:
        return {"id": e.id, "trail_id": e.trail_id, "executed_on": e.executed_on}

    def _impression_dict(i) -> dict:
        return {
            "id": i.id,
            "execution_id": i.execution_id,
            "trail_id": i.trail_id,
            "overall_rating": i.overall_rating,
            "notes": i.notes,
            "weather": i.weather,
            "difficulty": i.difficulty,
        }

    # ── Trails ────────────────────────────────────────────────────────────────

    @api.get("/api/trails")
    def list_trails(
        activity_type: str | None = None,
        hiked: bool | None = None,
        rated: bool | None = None,
        sort_by: Literal["rating", "distance_km", "elevation_gain_m", "drive_time_min", "last_executed_on"] | None = None,
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_length_km: float | None = None,
        max_length_km: float | None = None,
        min_hike_duration_min: float | None = None,
        max_hike_duration_min: float | None = None,
        min_ascend_m: int | None = None,
        max_ascend_m: int | None = None,
        min_drive_duration_min: float | None = None,
        max_drive_duration_min: float | None = None,
        trail_type: str | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        rows = repo.list_trails(
            limit=limit,
            offset=offset,
            activity_type=activity_type,
            only_hiked=hiked,
            rated=rated,
            sort_by=sort_by,
            search=search,
            date_from=date_from,
            date_to=date_to,
            min_length_km=min_length_km,
            max_length_km=max_length_km,
            min_hike_duration_min=min_hike_duration_min,
            max_hike_duration_min=max_hike_duration_min,
            min_ascend_m=min_ascend_m,
            max_ascend_m=max_ascend_m,
            min_drive_duration_min=min_drive_duration_min,
            max_drive_duration_min=max_drive_duration_min,
            trail_type=trail_type,
        )
        return {"count": len(rows), "items": [_trail_dict(r) for r in rows]}

    @api.post("/api/trails", status_code=201)
    def create_trail(body: TrailCreate):
        try:
            trail = repo.add_trail(body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return _trail_dict(trail)

    @api.get("/api/trails/{trail_id}")
    def get_trail(trail_id: int):
        rows = repo.list_trails(
            limit=1, offset=0, activity_type=None, only_hiked=None, rated=None,
            sort_by=None, search=None, date_from=None, date_to=None,
            min_length_km=None, max_length_km=None, min_hike_duration_min=None,
            max_hike_duration_min=None, min_ascend_m=None, max_ascend_m=None,
            min_drive_duration_min=None, max_drive_duration_min=None, trail_type=None,
        )
        # find by id since we don't have get_by_id — use get_by_name fallback via full scan
        trail = repo.get_trail_by_id(trail_id)
        if not trail:
            raise HTTPException(status_code=404, detail="Trail not found")
        return _trail_dict(trail)

    @api.patch("/api/trails/{trail_id}")
    def update_trail(trail_id: int, body: TrailUpdate):
        trail = repo.get_trail_by_id(trail_id)
        if not trail:
            raise HTTPException(status_code=404, detail="Trail not found")

        updates: dict = {}
        if body.new_name is not None:
            updates["name"] = body.new_name
        for field in ("trail_type", "url", "description", "distance_km", "hike_duration_min",
                       "elevation_gain_m", "elevation_loss_m", "drive_distance_km",
                       "drive_time_min", "gpx_url", "garmin_course_url"):
            if field in body.model_fields_set:
                updates[field] = getattr(body, field)

        try:
            updated = repo.update_trail(
                trail_name=trail.name,
                activity_type=trail.activity_type,
                updates=updates,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return _trail_dict(updated)

    @api.delete("/api/trails/{trail_id}", status_code=204)
    def delete_trail(trail_id: int):
        trail = repo.get_trail_by_id(trail_id)
        if not trail:
            raise HTTPException(status_code=404, detail="Trail not found")
        repo.delete_trail(trail_id)

    # ── Executions ────────────────────────────────────────────────────────────

    @api.get("/api/executions")
    def list_all_executions(
        trail_name: str | None = None,
        activity_type: str | None = None,
        sort_by: Literal["executed_on_asc", "executed_on_desc"] | None = "executed_on_desc",
        after: str | None = None,
        before: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ):
        rows = repo.list_executions(
            trail_name=trail_name,
            limit=limit,
            activity_type=activity_type,
            sort_by=sort_by,
            after=after,
            before=before,
        )
        return {
            "count": len(rows),
            "items": [
                {"id": e.id, "trail_id": e.trail_id, "trail_name": e.trail_name, "executed_on": e.executed_on}
                for e in rows
            ],
        }

    @api.get("/api/trails/{trail_id}/executions")
    def list_executions(trail_id: int, limit: int = Query(default=50, ge=1, le=200)):
        trail = repo.get_trail_by_id(trail_id)
        if not trail:
            raise HTTPException(status_code=404, detail="Trail not found")
        rows = repo.list_executions(trail_name=trail.name, limit=limit, activity_type=trail.activity_type)
        return {"count": len(rows), "items": [_execution_dict(e) for e in rows]}

    @api.post("/api/trails/{trail_id}/executions", status_code=201)
    def create_execution(trail_id: int, body: ExecutionCreate):
        trail = repo.get_trail_by_id(trail_id)
        if not trail:
            raise HTTPException(status_code=404, detail="Trail not found")
        try:
            execution = repo.record_execution(
                trail_name=trail.name,
                executed_on=body.executed_on,
                activity_type=trail.activity_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return _execution_dict(execution)

    @api.patch("/api/executions/{execution_id}")
    def update_execution(execution_id: int, body: ExecutionUpdate):
        try:
            execution = repo.update_execution(execution_id=execution_id, executed_on=body.executed_on)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _execution_dict(execution)

    @api.delete("/api/executions/{execution_id}", status_code=204)
    def delete_execution(execution_id: int):
        deleted = repo.delete_execution(execution_id=execution_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Execution not found")

    # ── Impressions ───────────────────────────────────────────────────────────

    @api.get("/api/trails/{trail_id}/impressions")
    def list_impressions(trail_id: int, limit: int = Query(default=50, ge=1, le=200)):
        trail = repo.get_trail_by_id(trail_id)
        if not trail:
            raise HTTPException(status_code=404, detail="Trail not found")
        rows = repo.list_impressions(trail_name=trail.name, limit=limit, activity_type=trail.activity_type)
        return {"count": len(rows), "items": [_impression_dict(i) for i in rows]}

    @api.post("/api/executions/{execution_id}/impressions", status_code=201)
    def create_impression(execution_id: int, body: ImpressionCreate):
        try:
            impression = repo.add_impression(
                execution_id=execution_id,
                overall_rating=body.overall_rating,
                notes=body.notes,
                weather=body.weather,
                difficulty=body.difficulty,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _impression_dict(impression)

    @api.patch("/api/impressions/{impression_id}")
    def update_impression(impression_id: int, body: ImpressionUpdate):
        updates = {k: v for k, v in body.model_dump().items() if k in body.model_fields_set}
        try:
            impression = repo.update_impression(impression_id=impression_id, updates=updates)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _impression_dict(impression)

    @api.delete("/api/impressions/{impression_id}", status_code=204)
    def delete_impression(impression_id: int):
        deleted = repo.delete_impression(impression_id=impression_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Impression not found")

    # ── Stats ─────────────────────────────────────────────────────────────────

    @api.get("/api/stats")
    def get_stats():
        stats = repo.get_stats()
        return {
            "total": stats.total,
            "hiked": stats.hiked,
            "not_hiked": stats.total - stats.hiked,
            "avg_rating": round(sum(stats.ratings) / len(stats.ratings), 2) if stats.ratings else None,
            "rated_count": len(stats.ratings),
            "distances_km": stats.distances_km,
            "drive_times_min": stats.drive_times_min,
            "ratings": stats.ratings,
        }

    return api
