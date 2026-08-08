"""HTTP-backed TrailsRepository — calls the TrailBear REST API via httpx."""

from __future__ import annotations

import httpx

from .repository import ExecutionRecord, ImpressionRecord, TrailRecord, TrailStats


class HttpTrailsRepository:
    """Implements TrailsRepository by proxying all calls to a remote HTTP API."""

    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")
        # trust_env=False: ignore HTTP_PROXY/HTTPS_PROXY env vars that Claude Desktop
        # may inject — we always connect directly to the API.
        self._client = httpx.Client(base_url=self._base, timeout=30, trust_env=False)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                r = self._client.request(method, path, **kwargs)
                r.raise_for_status()
                return r
            except (httpx.ConnectError, httpx.NetworkError, OSError) as exc:
                last_exc = exc
                if attempt < 2:
                    import time
                    time.sleep(0.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    def _get(self, path: str, **params) -> dict:
        filtered = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=filtered).json()

    def _post(self, path: str, body: dict) -> dict:
        return self._request("POST", path, json=body).json()

    def _patch(self, path: str, body: dict) -> dict:
        return self._request("PATCH", path, json=body).json()

    def _delete(self, path: str) -> bool:
        try:
            r = self._request("DELETE", path)
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return False
            raise

    def init_schema(self) -> None:
        pass  # schema is managed server-side

    def _trail(self, d: dict) -> TrailRecord:
        return TrailRecord(
            id=d["id"],
            name=d["name"],
            activity_type=d["activity_type"],
            trail_type=d.get("trail_type"),
            url=d.get("url"),
            description=d.get("description"),
            distance_km=d.get("distance_km"),
            hike_duration_min=d.get("hike_duration_min"),
            elevation_gain_m=d.get("elevation_gain_m"),
            elevation_loss_m=d.get("elevation_loss_m"),
            drive_distance_km=d.get("drive_distance_km"),
            drive_time_min=d.get("drive_time_min"),
            avg_overall_rating=d.get("avg_overall_rating"),
            gpx_url=d.get("gpx_url"),
            garmin_course_url=d.get("garmin_course_url"),
        )

    def _execution(self, d: dict) -> ExecutionRecord:
        return ExecutionRecord(id=d["id"], trail_id=d["trail_id"], executed_on=d["executed_on"], trail_name=d.get("trail_name"))

    def _impression(self, d: dict) -> ImpressionRecord:
        return ImpressionRecord(
            id=d["id"],
            execution_id=d["execution_id"],
            trail_id=d["trail_id"],
            overall_rating=d.get("overall_rating"),
            notes=d.get("notes"),
            weather=d.get("weather"),
            difficulty=d.get("difficulty"),
        )

    def upsert_trail(self, payload: dict) -> int:
        d = self._post("/api/trails", payload)
        return d["id"]

    def add_trail(self, payload: dict) -> TrailRecord:
        d = self._post("/api/trails", payload)
        return self._trail(d)

    def get_trail_by_name(self, name: str, activity_type: str | None = None) -> TrailRecord | None:
        data = self._get("/api/trails", search=name, activity_type=activity_type, limit=50)
        for item in data.get("items", []):
            if item["name"] == name:
                if activity_type is None or item["activity_type"].lower() == activity_type.lower():
                    return self._trail(item)
        return None

    def get_trail_by_id(self, trail_id: int) -> TrailRecord | None:
        try:
            d = self._get(f"/api/trails/{trail_id}")
            return self._trail(d)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def delete_trail(self, trail_id: int) -> bool:
        return self._delete(f"/api/trails/{trail_id}")

    def list_trails(
        self,
        *,
        limit: int,
        offset: int,
        activity_type: str | None,
        only_hiked: bool | None,
        rated: bool | None,
        sort_by: str | None,
        search: str | None,
        date_from: str | None,
        date_to: str | None,
        min_length_km: float | None,
        max_length_km: float | None,
        min_hike_duration_min: float | None,
        max_hike_duration_min: float | None,
        min_ascend_m: int | None,
        max_ascend_m: int | None,
        min_drive_duration_min: float | None,
        max_drive_duration_min: float | None,
        trail_type: str | None,
    ) -> list[TrailRecord]:
        data = self._get(
            "/api/trails",
            limit=limit,
            offset=offset,
            activity_type=activity_type,
            hiked=only_hiked,
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
        return [self._trail(item) for item in data.get("items", [])]

    def record_execution(self, *, trail_name: str, executed_on: str, activity_type: str | None = None) -> ExecutionRecord:
        trail = self.get_trail_by_name(trail_name, activity_type)
        if not trail:
            raise ValueError(f"Trail not found: {trail_name}")
        d = self._post(f"/api/trails/{trail.id}/executions", {"executed_on": executed_on})
        return self._execution(d)

    def add_impression(self, *, execution_id: int, overall_rating: float | None, notes: str | None, weather: str | None, difficulty: str | None) -> ImpressionRecord:
        d = self._post(f"/api/executions/{execution_id}/impressions", {
            "overall_rating": overall_rating,
            "notes": notes,
            "weather": weather,
            "difficulty": difficulty,
        })
        return self._impression(d)

    def list_impressions(self, *, trail_name: str, limit: int, activity_type: str | None = None) -> list[ImpressionRecord]:
        trail = self.get_trail_by_name(trail_name, activity_type)
        if not trail:
            raise ValueError(f"Trail not found: {trail_name}")
        data = self._get(f"/api/trails/{trail.id}/impressions", limit=limit)
        return [self._impression(i) for i in data.get("items", [])]

    def list_executions(
        self,
        *,
        trail_name: str | None = None,
        limit: int,
        activity_type: str | None = None,
        sort_by: str | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> list[ExecutionRecord]:
        if trail_name is not None:
            trail = self.get_trail_by_name(trail_name, activity_type)
            if not trail:
                raise ValueError(f"Trail not found: {trail_name}")
            data = self._get(f"/api/trails/{trail.id}/executions", limit=limit)
        else:
            data = self._get(
                "/api/executions",
                limit=limit,
                activity_type=activity_type,
                sort_by=sort_by,
                after=after,
                before=before,
            )
        return [self._execution(e) for e in data.get("items", [])]

    def update_execution(self, *, execution_id: int, executed_on: str) -> ExecutionRecord:
        d = self._patch(f"/api/executions/{execution_id}", {"executed_on": executed_on})
        return self._execution(d)

    def delete_execution(self, *, execution_id: int) -> bool:
        return self._delete(f"/api/executions/{execution_id}")

    def update_impression(self, *, impression_id: int, updates: dict) -> ImpressionRecord:
        d = self._patch(f"/api/impressions/{impression_id}", updates)
        return self._impression(d)

    def delete_impression(self, *, impression_id: int) -> bool:
        return self._delete(f"/api/impressions/{impression_id}")

    def update_trail_garmin_course(self, *, trail_name: str, activity_type: str | None, garmin_course_url: str | None) -> TrailRecord:
        trail = self.get_trail_by_name(trail_name, activity_type)
        if not trail:
            raise ValueError(f"Trail not found: {trail_name}")
        d = self._patch(f"/api/trails/{trail.id}", {"garmin_course_url": garmin_course_url})
        return self._trail(d)

    def update_trail(self, *, trail_name: str, activity_type: str | None, updates: dict) -> TrailRecord:
        trail = self.get_trail_by_name(trail_name, activity_type)
        if not trail:
            raise ValueError(f"Trail not found: {trail_name}")
        patch_body = {}
        if "name" in updates:
            patch_body["new_name"] = updates.pop("name")
        patch_body.update(updates)
        d = self._patch(f"/api/trails/{trail.id}", patch_body)
        return self._trail(d)

    def get_stats(self) -> TrailStats:
        d = self._get("/api/stats")
        return TrailStats(
            total=d["total"],
            hiked=d["hiked"],
            distances_km=d.get("distances_km", []),
            drive_times_min=d.get("drive_times_min", []),
            ratings=d.get("ratings", []),
        )
