from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class TrailRecord:
    id: int
    name: str
    activity_type: str
    trail_type: str | None
    url: str | None
    description: str | None
    distance_km: float | None
    hike_duration_min: float | None
    elevation_gain_m: int | None
    elevation_loss_m: int | None
    drive_distance_km: float | None
    drive_time_min: float | None
    avg_overall_rating: float | None
    gpx_url: str | None
    garmin_course_url: str | None
    last_executed_on: str | None = None


@dataclass
class ExecutionRecord:
    id: int
    trail_id: int
    executed_on: str
    trail_name: str | None = None


@dataclass
class ImpressionRecord:
    id: int
    execution_id: int
    trail_id: int
    overall_rating: float | None
    notes: str | None
    weather: str | None
    difficulty: str | None


@dataclass
class TrailStats:
    total: int
    hiked: int
    distances_km: list[float]
    drive_times_min: list[float]
    ratings: list[float]


class TrailsRepository(Protocol):
    def init_schema(self) -> None: ...

    def upsert_trail(self, payload: dict) -> int: ...

    def add_trail(self, payload: dict) -> TrailRecord: ...

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
    ) -> list[TrailRecord]: ...

    def get_trail_by_name(self, name: str, activity_type: str | None = None) -> TrailRecord | None: ...

    def get_trail_by_id(self, trail_id: int) -> TrailRecord | None: ...

    def delete_trail(self, trail_id: int) -> bool: ...

    def record_execution(self, *, trail_name: str, executed_on: str, activity_type: str | None = None) -> ExecutionRecord: ...

    def add_impression(
        self,
        *,
        execution_id: int,
        overall_rating: float | None,
        notes: str | None,
        weather: str | None,
        difficulty: str | None,
    ) -> ImpressionRecord: ...

    def list_impressions(self, *, trail_name: str, limit: int, activity_type: str | None = None) -> list[ImpressionRecord]: ...

    def list_executions(
        self,
        *,
        trail_name: str | None = None,
        limit: int,
        activity_type: str | None = None,
        sort_by: str | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> list[ExecutionRecord]: ...

    def update_execution(self, *, execution_id: int, executed_on: str) -> ExecutionRecord: ...

    def delete_execution(self, *, execution_id: int) -> bool: ...

    def update_impression(
        self,
        *,
        impression_id: int,
        updates: dict[str, float | str | None],
    ) -> ImpressionRecord: ...

    def delete_impression(self, *, impression_id: int) -> bool: ...

    def update_trail_garmin_course(
        self,
        *,
        trail_name: str,
        activity_type: str | None,
        garmin_course_url: str | None,
    ) -> TrailRecord: ...

    def update_trail(
        self,
        *,
        trail_name: str,
        activity_type: str | None,
        updates: dict[str, float | int | str | None],
    ) -> TrailRecord: ...

    def get_stats(self) -> TrailStats: ...


class SQLiteTrailsRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS trails (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  activity_type TEXT NOT NULL,
                  trail_type TEXT,
                  url TEXT,
                  description TEXT,
                  distance_km REAL,
                  hike_duration_min REAL,
                  elevation_gain_m INTEGER,
                  elevation_loss_m INTEGER,
                  drive_distance_km REAL,
                  drive_time_min REAL,
                  gpx_url TEXT,
                  garmin_course_url TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(name, activity_type)
                );

                CREATE TABLE IF NOT EXISTS executions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  trail_id INTEGER NOT NULL,
                  executed_on TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(trail_id) REFERENCES trails(id) ON DELETE CASCADE,
                  UNIQUE(trail_id, executed_on)
                );

                CREATE TABLE IF NOT EXISTS impressions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  execution_id INTEGER NOT NULL,
                  trail_id INTEGER NOT NULL,
                  overall_rating REAL,
                  notes TEXT,
                  weather TEXT,
                  difficulty TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE CASCADE,
                  FOREIGN KEY(trail_id) REFERENCES trails(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_executions_trail_id
                  ON executions(trail_id);
                CREATE INDEX IF NOT EXISTS idx_impressions_execution_id
                  ON impressions(execution_id);
                CREATE INDEX IF NOT EXISTS idx_trails_activity_type
                  ON trails(activity_type);
                CREATE INDEX IF NOT EXISTS idx_trails_trail_type
                  ON trails(trail_type);
                """
            )
            existing_columns = {
                str(r[1])
                for r in conn.execute("PRAGMA table_info(trails)").fetchall()
            }
            table_list = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "hike_executions" in table_list:
                try:
                    conn.executescript(
                        """
                        INSERT OR IGNORE INTO executions SELECT id, trail_id, executed_on, created_at FROM hike_executions;
                        INSERT OR IGNORE INTO impressions SELECT id, execution_id, trail_id, overall_rating, notes, weather, difficulty, created_at FROM hike_impressions;
                        DROP TABLE hike_impressions;
                        DROP TABLE hike_executions;
                        """
                    )
                except Exception:
                    pass

            if "activity_type" not in existing_columns:
                conn.execute("ALTER TABLE trails ADD COLUMN activity_type TEXT DEFAULT 'hiking'")
            if "garmin_course_url" not in existing_columns:
                conn.execute("ALTER TABLE trails ADD COLUMN garmin_course_url TEXT")

            impression_columns = {
                str(r[1]): str(r[2]).upper()
                for r in conn.execute("PRAGMA table_info(impressions)").fetchall()
            }
            overall_rating_type = impression_columns.get("overall_rating", "")
            if overall_rating_type in {"INTEGER", "INT"}:
                conn.execute("PRAGMA foreign_keys=OFF")
                try:
                    conn.executescript(
                        """
                        ALTER TABLE impressions RENAME TO impressions_legacy_rating_int;

                        CREATE TABLE impressions (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          execution_id INTEGER NOT NULL,
                          trail_id INTEGER NOT NULL,
                  overall_rating REAL,
                          notes TEXT,
                          weather TEXT,
                          difficulty TEXT,
                          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                          FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE CASCADE,
                          FOREIGN KEY(trail_id) REFERENCES trails(id) ON DELETE CASCADE
                        );

                        INSERT INTO impressions (id, execution_id, trail_id, overall_rating, notes, weather, difficulty, created_at)
                        SELECT id, execution_id, trail_id, CAST(overall_rating AS REAL), notes, weather, difficulty, created_at
                        FROM impressions_legacy_rating_int;

                        DROP TABLE impressions_legacy_rating_int;
                        """
                    )
                finally:
                    conn.execute("PRAGMA foreign_keys=ON")

            try:
                conn.execute("DROP INDEX IF EXISTS sqlite_autoindex_trails_1")
            except Exception:
                pass
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trails_unique ON trails(name, activity_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_executions_trail_id ON executions(trail_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_impressions_execution_id ON impressions(execution_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trails_activity_type ON trails(activity_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trails_trail_type ON trails(trail_type)")

    def upsert_trail(self, payload: dict) -> int:
        with self._connect() as conn:
            activity_type = payload.get("activity_type", "hiking")
            conn.execute(
                """
                INSERT INTO trails (
                  name, activity_type, trail_type, url, description, distance_km,
                  hike_duration_min,
                  elevation_gain_m, elevation_loss_m,
                  drive_distance_km, drive_time_min,
                  gpx_url, garmin_course_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, activity_type) DO UPDATE SET
                  trail_type=excluded.trail_type,
                  url=excluded.url,
                  description=excluded.description,
                  distance_km=excluded.distance_km,
                  hike_duration_min=excluded.hike_duration_min,
                  elevation_gain_m=excluded.elevation_gain_m,
                  elevation_loss_m=excluded.elevation_loss_m,
                  drive_distance_km=excluded.drive_distance_km,
                  drive_time_min=excluded.drive_time_min,
                  gpx_url=excluded.gpx_url,
                  garmin_course_url=excluded.garmin_course_url,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload["name"],
                    activity_type,
                    payload.get("trail_type"),
                    payload.get("url"),
                    payload.get("description"),
                    payload.get("distance_km"),
                    payload.get("hike_duration_min"),
                    payload.get("elevation_gain_m"),
                    payload.get("elevation_loss_m"),
                    payload.get("drive_distance_km"),
                    payload.get("drive_time_min"),
                    payload.get("gpx_url"),
                    payload.get("garmin_course_url"),
                ),
            )
            row = conn.execute(
                "SELECT id FROM trails WHERE name = ? AND activity_type = ?",
                (payload["name"], activity_type),
            ).fetchone()
            if not row:
                raise RuntimeError(f"Failed to upsert trail: {payload['name']}")

            trail_id = int(row["id"])
            for date_str in payload.get("source_hike_dates", []):
                conn.execute(
                    "INSERT OR IGNORE INTO executions (trail_id, executed_on) VALUES (?, ?)",
                    (trail_id, date_str),
                )

            return trail_id

    def add_trail(self, payload: dict) -> TrailRecord:
        with self._connect() as conn:
            activity_type = payload.get("activity_type", "hiking")
            try:
                conn.execute(
                    """
                    INSERT INTO trails (
                      name, activity_type, trail_type, url, description, distance_km,
                      hike_duration_min,
                      elevation_gain_m, elevation_loss_m,
                      drive_distance_km, drive_time_min,
                      gpx_url, garmin_course_url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["name"],
                        activity_type,
                        payload.get("trail_type"),
                        payload.get("url"),
                        payload.get("description"),
                        payload.get("distance_km"),
                        payload.get("hike_duration_min"),
                        payload.get("elevation_gain_m"),
                        payload.get("elevation_loss_m"),
                        payload.get("drive_distance_km"),
                        payload.get("drive_time_min"),
                        payload.get("gpx_url"),
                        payload.get("garmin_course_url"),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("A trail with this name and activity_type already exists") from exc

            row = conn.execute(
                "SELECT * FROM trails WHERE name = ? AND activity_type = ?",
                (payload["name"], activity_type),
            ).fetchone()

        if not row:
            raise RuntimeError(f"Failed to add trail: {payload['name']}")
        return self._trail_from_row(row)

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
        clauses: list[str] = []
        params: list[object] = []

        if activity_type:
            clauses.append("LOWER(trails.activity_type) = ?")
            params.append(activity_type.lower())

        if search:
            clauses.append("LOWER(trails.name) LIKE ?")
            params.append(f"%{search.lower()}%")
        if trail_type:
            clauses.append("LOWER(COALESCE(trails.trail_type, '')) = ?")
            params.append(trail_type.lower())
        if min_length_km is not None:
            clauses.append("trails.distance_km >= ?")
            params.append(min_length_km)
        if max_length_km is not None:
            clauses.append("trails.distance_km <= ?")
            params.append(max_length_km)
        if min_hike_duration_min is not None:
            clauses.append("trails.hike_duration_min >= ?")
            params.append(min_hike_duration_min)
        if max_hike_duration_min is not None:
            clauses.append("trails.hike_duration_min <= ?")
            params.append(max_hike_duration_min)
        if min_ascend_m is not None:
            clauses.append("trails.elevation_gain_m >= ?")
            params.append(min_ascend_m)
        if max_ascend_m is not None:
            clauses.append("trails.elevation_gain_m <= ?")
            params.append(max_ascend_m)
        if min_drive_duration_min is not None:
            clauses.append("trails.drive_time_min >= ?")
            params.append(min_drive_duration_min)
        if max_drive_duration_min is not None:
            clauses.append("trails.drive_time_min <= ?")
            params.append(max_drive_duration_min)

        if only_hiked is not None:
            if only_hiked:
                clauses.append("EXISTS (SELECT 1 FROM executions WHERE executions.trail_id = trails.id)")
            else:
                clauses.append("NOT EXISTS (SELECT 1 FROM executions WHERE executions.trail_id = trails.id)")

        if rated is not None:
            if rated:
                clauses.append("COALESCE(rating_stats.rated_count, 0) > 0")
            else:
                clauses.append("COALESCE(rating_stats.rated_count, 0) = 0")

        if date_from or date_to:
            date_clauses: list[str] = []
            if date_from:
                date_clauses.append("date(executions.executed_on) >= date(?)")
                params.append(date_from)
            if date_to:
                date_clauses.append("date(executions.executed_on) <= date(?)")
                params.append(date_to)
            clauses.append(
                f"EXISTS (SELECT 1 FROM executions WHERE executions.trail_id = trails.id AND {' AND '.join(date_clauses)})"
            )

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        order_sql = "trails.name ASC"
        if sort_by == "rating":
            order_sql = "rating_stats.avg_overall_rating IS NULL ASC, rating_stats.avg_overall_rating DESC, trails.name ASC"
        elif sort_by == "distance_km":
            order_sql = "trails.distance_km IS NULL ASC, trails.distance_km ASC, trails.name ASC"
        elif sort_by == "elevation_gain_m":
            order_sql = "trails.elevation_gain_m IS NULL ASC, trails.elevation_gain_m ASC, trails.name ASC"
        elif sort_by == "drive_time_min":
            order_sql = "trails.drive_time_min IS NULL ASC, trails.drive_time_min ASC, trails.name ASC"
        elif sort_by == "last_executed_on":
            order_sql = "exec_stats.last_executed_on IS NULL ASC, exec_stats.last_executed_on DESC, trails.name ASC"

        sql = (
            "SELECT trails.*, rating_stats.avg_overall_rating, exec_stats.last_executed_on FROM trails "
            "LEFT JOIN ("
            "  SELECT trail_id, AVG(overall_rating) AS avg_overall_rating, COUNT(overall_rating) AS rated_count "
            "  FROM impressions "
            "  WHERE overall_rating IS NOT NULL "
            "  GROUP BY trail_id"
            ") AS rating_stats ON rating_stats.trail_id = trails.id "
            "LEFT JOIN ("
            "  SELECT trail_id, MAX(executed_on) AS last_executed_on "
            "  FROM executions "
            "  GROUP BY trail_id"
            ") AS exec_stats ON exec_stats.trail_id = trails.id "
            f"{where_sql} "
            f"ORDER BY {order_sql} "
            "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [self._trail_from_row(r) for r in rows]

    def get_trail_by_name(self, name: str, activity_type: str | None = None) -> TrailRecord | None:
        with self._connect() as conn:
            if activity_type:
                row = conn.execute(
                    "SELECT * FROM trails WHERE name = ? AND LOWER(activity_type) = LOWER(?)",
                    (name, activity_type),
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM trails WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return self._trail_from_row(row)

    def get_trail_by_id(self, trail_id: int) -> TrailRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT trails.*, NULL AS avg_overall_rating FROM trails WHERE id = ?", (trail_id,)
            ).fetchone()
        if not row:
            return None
        return self._trail_from_row(row)

    def delete_trail(self, trail_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM trails WHERE id = ?", (trail_id,))
            return cursor.rowcount > 0

    def record_execution(self, *, trail_name: str, executed_on: str, activity_type: str | None = None) -> ExecutionRecord:
        with self._connect() as conn:
            if activity_type:
                trail_row = conn.execute(
                    "SELECT id FROM trails WHERE name = ? AND LOWER(activity_type) = LOWER(?)",
                    (trail_name, activity_type),
                ).fetchone()
            else:
                trail_row = conn.execute("SELECT id FROM trails WHERE name = ?", (trail_name,)).fetchone()
            if not trail_row:
                raise ValueError(f"Trail not found: {trail_name}")

            conn.execute(
                "INSERT OR IGNORE INTO executions (trail_id, executed_on) VALUES (?, ?)",
                (int(trail_row["id"]), executed_on),
            )
            exec_row = conn.execute(
                "SELECT id FROM executions WHERE trail_id = ? AND executed_on = ?",
                (int(trail_row["id"]), executed_on),
            ).fetchone()

        if not exec_row:
            raise RuntimeError(f"Failed to record execution for {trail_name} on {executed_on}")

        return ExecutionRecord(
            id=int(exec_row["id"]),
            trail_id=int(trail_row["id"]),
            executed_on=executed_on,
        )

    def add_impression(
        self,
        *,
        execution_id: int,
        overall_rating: float | None,
        notes: str | None,
        weather: str | None,
        difficulty: str | None,
    ) -> ImpressionRecord:
        with self._connect() as conn:
            exec_row = conn.execute(
                "SELECT trail_id FROM executions WHERE id = ?", (execution_id,)
            ).fetchone()
            if not exec_row:
                raise ValueError(f"Execution not found: {execution_id}")

            cursor = conn.execute(
                """
                INSERT INTO impressions (execution_id, trail_id, overall_rating, notes, weather, difficulty)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    int(exec_row["trail_id"]),
                    overall_rating,
                    notes,
                    weather,
                    difficulty,
                ),
            )
            inserted_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM impressions WHERE id = ?", (inserted_id,)).fetchone()

        if not row:
            raise RuntimeError("Failed to insert impression")
        return self._impression_from_row(row)

    def list_impressions(self, *, trail_name: str, limit: int, activity_type: str | None = None) -> list[ImpressionRecord]:
        with self._connect() as conn:
            if activity_type:
                trail_row = conn.execute(
                    "SELECT id FROM trails WHERE name = ? AND LOWER(activity_type) = LOWER(?)",
                    (trail_name, activity_type),
                ).fetchone()
            else:
                trail_row = conn.execute("SELECT id FROM trails WHERE name = ?", (trail_name,)).fetchone()
            if not trail_row:
                raise ValueError(f"Trail not found: {trail_name}")

            rows = conn.execute(
                """
                SELECT * FROM impressions
                WHERE trail_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(trail_row["id"]), limit),
            ).fetchall()
        return [self._impression_from_row(r) for r in rows]

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
        clauses: list[str] = []
        params: list[object] = []

        with self._connect() as conn:
            if trail_name is not None:
                if activity_type:
                    trail_row = conn.execute(
                        "SELECT id FROM trails WHERE name = ? AND LOWER(activity_type) = LOWER(?)",
                        (trail_name, activity_type),
                    ).fetchone()
                else:
                    trail_row = conn.execute("SELECT id FROM trails WHERE name = ?", (trail_name,)).fetchone()
                if not trail_row:
                    raise ValueError(f"Trail not found: {trail_name}")
                clauses.append("executions.trail_id = ?")
                params.append(int(trail_row["id"]))
            elif activity_type:
                clauses.append("LOWER(trails.activity_type) = ?")
                params.append(activity_type.lower())

            if after:
                clauses.append("date(executions.executed_on) >= date(?)")
                params.append(after)
            if before:
                clauses.append("date(executions.executed_on) <= date(?)")
                params.append(before)

            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            order_sql = "executions.executed_on ASC" if sort_by == "executed_on_asc" else "executions.executed_on DESC"

            rows = conn.execute(
                f"""
                SELECT executions.*, trails.name AS trail_name
                FROM executions
                JOIN trails ON trails.id = executions.trail_id
                {where_sql}
                ORDER BY {order_sql}
                LIMIT ?
                """,
                tuple(params) + (limit,),
            ).fetchall()

        return [
            ExecutionRecord(
                id=int(r["id"]),
                trail_id=int(r["trail_id"]),
                executed_on=r["executed_on"],
                trail_name=r["trail_name"],
            )
            for r in rows
        ]

    def update_execution(self, *, execution_id: int, executed_on: str) -> ExecutionRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
            if not row:
                raise ValueError(f"Execution not found: {execution_id}")

            try:
                conn.execute(
                    "UPDATE executions SET executed_on = ? WHERE id = ?",
                    (executed_on, execution_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("An execution already exists for this trail on that date") from exc

            updated = conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()

        if not updated:
            raise RuntimeError(f"Failed to update execution: {execution_id}")
        return ExecutionRecord(
            id=int(updated["id"]),
            trail_id=int(updated["trail_id"]),
            executed_on=updated["executed_on"],
        )

    def delete_execution(self, *, execution_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM executions WHERE id = ?", (execution_id,))
            return cursor.rowcount > 0

    def update_impression(
        self,
        *,
        impression_id: int,
        updates: dict[str, float | str | None],
    ) -> ImpressionRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM impressions WHERE id = ?", (impression_id,)).fetchone()
            if not row:
                raise ValueError(f"Impression not found: {impression_id}")

            allowed_fields = ("overall_rating", "notes", "weather", "difficulty")
            invalid_fields = [field for field in updates if field not in allowed_fields]
            if invalid_fields:
                raise ValueError(f"Unsupported impression fields: {', '.join(invalid_fields)}")

            if updates:
                set_clauses: list[str] = []
                values: list[float | str | None] = []
                for field in allowed_fields:
                    if field in updates:
                        set_clauses.append(f"{field} = ?")
                        values.append(updates[field])

                conn.execute(
                    f"UPDATE impressions SET {', '.join(set_clauses)} WHERE id = ?",
                    tuple(values + [impression_id]),
                )
                updated = conn.execute("SELECT * FROM impressions WHERE id = ?", (impression_id,)).fetchone()
            else:
                updated = row

        if not updated:
            raise RuntimeError(f"Failed to update impression: {impression_id}")
        return self._impression_from_row(updated)

    def delete_impression(self, *, impression_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM impressions WHERE id = ?", (impression_id,))
            return cursor.rowcount > 0

    def update_trail_garmin_course(
        self,
        *,
        trail_name: str,
        activity_type: str | None,
        garmin_course_url: str | None,
    ) -> TrailRecord:
        with self._connect() as conn:
            if activity_type:
                conn.execute(
                    """
                    UPDATE trails
                    SET garmin_course_url = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ? AND LOWER(activity_type) = LOWER(?)
                    """,
                    (garmin_course_url, trail_name, activity_type),
                )
                row = conn.execute(
                    "SELECT * FROM trails WHERE name = ? AND LOWER(activity_type) = LOWER(?)",
                    (trail_name, activity_type),
                ).fetchone()
            else:
                conn.execute(
                    """
                    UPDATE trails
                    SET garmin_course_url = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                    """,
                    (garmin_course_url, trail_name),
                )
                row = conn.execute("SELECT * FROM trails WHERE name = ?", (trail_name,)).fetchone()
        if not row:
            raise ValueError(f"Trail not found: {trail_name}")
        return self._trail_from_row(row)

    def update_trail(
        self,
        *,
        trail_name: str,
        activity_type: str | None,
        updates: dict[str, float | int | str | None],
    ) -> TrailRecord:
        allowed_fields = (
            "name",
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
        invalid_fields = [field for field in updates if field not in allowed_fields]
        if invalid_fields:
            raise ValueError(f"Unsupported trail fields: {', '.join(invalid_fields)}")

        with self._connect() as conn:
            if activity_type:
                row = conn.execute(
                    "SELECT * FROM trails WHERE name = ? AND LOWER(activity_type) = LOWER(?)",
                    (trail_name, activity_type),
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM trails WHERE name = ?", (trail_name,)).fetchone()

            if not row:
                raise ValueError(f"Trail not found: {trail_name}")

            if updates:
                set_clauses: list[str] = []
                values: list[float | int | str | None] = []
                for field in allowed_fields:
                    if field in updates:
                        set_clauses.append(f"{field} = ?")
                        values.append(updates[field])
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")

                try:
                    conn.execute(
                        f"UPDATE trails SET {', '.join(set_clauses)} WHERE id = ?",
                        tuple(values + [int(row["id"])]),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError("A trail with this name and activity_type already exists") from exc

            updated = conn.execute("SELECT * FROM trails WHERE id = ?", (int(row["id"]),)).fetchone()

        if not updated:
            raise RuntimeError(f"Failed to update trail: {trail_name}")
        return self._trail_from_row(updated)

    def get_stats(self) -> TrailStats:
        with self._connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM trails").fetchone()[0])
            hiked = int(conn.execute(
                "SELECT COUNT(DISTINCT trail_id) FROM executions"
            ).fetchone()[0])
            distances_km = [
                float(r[0])
                for r in conn.execute(
                    "SELECT distance_km FROM trails WHERE distance_km IS NOT NULL"
                ).fetchall()
            ]
            drive_times_min = [
                float(r[0])
                for r in conn.execute(
                    "SELECT drive_time_min FROM trails WHERE drive_time_min IS NOT NULL"
                ).fetchall()
            ]
            ratings = [
                float(r[0])
                for r in conn.execute(
                    "SELECT overall_rating FROM impressions WHERE overall_rating IS NOT NULL"
                ).fetchall()
            ]
        return TrailStats(
            total=total,
            hiked=hiked,
            distances_km=distances_km,
            drive_times_min=drive_times_min,
            ratings=ratings,
        )

    def _trail_from_row(self, row: sqlite3.Row) -> TrailRecord:
        keys = row.keys()
        avg_overall_rating = row["avg_overall_rating"] if "avg_overall_rating" in keys else None
        last_executed_on = row["last_executed_on"] if "last_executed_on" in keys else None
        return TrailRecord(
            id=int(row["id"]),
            name=str(row["name"]),
            activity_type=str(row["activity_type"]),
            trail_type=row["trail_type"],
            url=row["url"],
            description=row["description"],
            distance_km=row["distance_km"],
            hike_duration_min=row["hike_duration_min"],
            elevation_gain_m=row["elevation_gain_m"],
            elevation_loss_m=row["elevation_loss_m"],
            drive_distance_km=row["drive_distance_km"],
            drive_time_min=row["drive_time_min"],
            avg_overall_rating=float(avg_overall_rating) if avg_overall_rating is not None else None,
            gpx_url=row["gpx_url"],
            garmin_course_url=row["garmin_course_url"],
            last_executed_on=str(last_executed_on) if last_executed_on is not None else None,
        )

    def _impression_from_row(self, row: sqlite3.Row) -> ImpressionRecord:
        rating = row["overall_rating"]
        return ImpressionRecord(
            id=int(row["id"]),
            execution_id=int(row["execution_id"]),
            trail_id=int(row["trail_id"]),
            overall_rating=float(rating) if rating is not None else None,
            notes=row["notes"],
            weather=row["weather"],
            difficulty=row["difficulty"],
        )


def make_repository(db_url: str) -> TrailsRepository:
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.removeprefix("sqlite:///"))
        return SQLiteTrailsRepository(db_path=db_path)

    if db_url.startswith("http://") or db_url.startswith("https://"):
        from .http_repository import HttpTrailsRepository
        return HttpTrailsRepository(base_url=db_url)

    raise ValueError(
        "Unsupported DB URL. Supports sqlite:/// or http(s)://. "
        "Set TRAILS_DB_URL=http://your-server:8080 to use the REST API."
    )
