"""Local evidence persistence, with no acquisition or scientific verification.

Callers must remove secrets from request metadata before saving it. Response bodies
are preserved verbatim. All query bounds are inclusive Unix seconds; unknown times
are retained but excluded from bounded queries. No method deletes evidence.
"""

import gzip
import hashlib
import errno
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time


REVIEW_STATUSES = frozenset((
    "confirmed_data_anomaly", "explained", "needs_more_data", "dismissed",
))
_CONTEXT_FIELDS = frozenset(("snapshot_at", "first_snapshot_at", "position_age_s", "feed_timestamp", "quality_flags"))
_CONTEXT_FLAGS = frozenset(("stale_position", "stale_feed", "future_position"))
_LINK_FIELDS = frozenset(("raw_ref", "raw_refs", "revision_id"))


def _normalized(record):
    normalized = {key: value for key, value in record.items()
                  if key not in _CONTEXT_FIELDS and key not in _LINK_FIELDS}
    if "quality_flags" in record:
        flags = record["quality_flags"]
        normalized["quality_flags"] = ([flag for flag in flags if flag not in _CONTEXT_FLAGS]
                                       if isinstance(flags, list) else flags)
    return normalized


def _json_number(payload, field):
    """Numeric fallback for arbitrary time fields; primary times are indexed."""
    try:
        value = json.loads(payload).get(field)
        if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value):
            return value
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _number(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("{} must be Unix seconds or null".format(name))
    if not math.isfinite(value):
        raise ValueError("{} must be finite".format(name))
    return value


def _bounds(start, end):
    _number(start, "start")
    _number(end, "end")
    if start is not None and end is not None and start > end:
        raise ValueError("start must not be after end")


def _identifier(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError("{} must be a nonempty string".format(name))
    return value


def _capture_id(source_id, body_sha256, metadata):
    return _hash(_json([source_id, body_sha256, metadata]).encode("utf-8"))


def _sync_directory(path):
    if os.name != "posix":
        return
    descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            # Some filesystems do not implement directory fsync. The completed
            # compressed file itself has already been fsynced before publication.
            if error.errno not in (errno.EINVAL, errno.ENOTSUP):
                raise
    finally:
        os.close(descriptor)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
    capture_id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
    retrieved_at REAL, body_sha256 TEXT NOT NULL, byte_count INTEGER NOT NULL,
    stored_bytes INTEGER NOT NULL,
    metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS capture_time ON captures(retrieved_at);
CREATE TABLE IF NOT EXISTS observations (
    revision_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL, domain TEXT NOT NULL, timestamp REAL,
    entity_id TEXT, source_id TEXT, region_json TEXT,
    raw_ref TEXT NOT NULL REFERENCES captures(capture_id), record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observation_time ON observations(domain, timestamp);
CREATE INDEX IF NOT EXISTS observation_identity ON observations(domain, observation_id);
CREATE TABLE IF NOT EXISTS observation_captures (
    revision_id TEXT NOT NULL REFERENCES observations(revision_id),
    capture_id TEXT NOT NULL REFERENCES captures(capture_id),
    context_json TEXT NOT NULL,
    snapshot_at REAL,
    PRIMARY KEY(revision_id, capture_id)
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY, start_time REAL, end_time REAL,
    created_at REAL NOT NULL, updated_at REAL NOT NULL, record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS event_time ON events(start_time, end_time);
CREATE TABLE IF NOT EXISTS reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    status TEXT NOT NULL CHECK(status IN (
        'confirmed_data_anomaly', 'explained', 'needs_more_data', 'dismissed')),
    note TEXT, reviewed_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS review_event ON reviews(event_id, review_id);
PRAGMA user_version = 1;
"""


class Store:
    """One SQLite connection per Store; callers serialize service writers.

    Review labels are analyst judgments, not verified physical truth. Different
    payloads sharing an observation ID are retained as distinct revisions. The
    per-capture context remains separate from normalized measurements. Queries
    return a qualifying capture context and its associated ``raw_ref``;
    ``raw_refs`` exposes qualifying attempts without inflating the record count.
    """

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = self.data_dir / "raw"
        self.raw_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "store.sqlite3"
        self.connection = sqlite3.connect(str(self.db_path), timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.create_function("satresearch_number", 2, _json_number)
        self.connection.execute("PRAGMA busy_timeout = 30000")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = FULL")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.connection.close()
            raise ValueError("Unsupported evidence database schema: {}".format(version))
        self.connection.executescript(_SCHEMA)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(observation_captures)")}
        if "snapshot_at" not in columns:
            # Add the query index to earlier prototype stores without rewriting
            # measurements, capture bodies or review decisions.
            with self.connection:
                self.connection.execute("ALTER TABLE observation_captures ADD COLUMN snapshot_at REAL")
                self.connection.execute(
                    "UPDATE observation_captures SET snapshot_at=satresearch_number(context_json, 'snapshot_at')")
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS capture_snapshot_time ON observation_captures(snapshot_at, revision_id)")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.connection.close()

    def _blob_path(self, digest):
        return self.raw_dir / digest[:2] / (digest + ".bin.gz")

    def _save_blob(self, body, digest):
        path = self._blob_path(digest)
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            # Publish a completely written file without ever replacing an older
            # blob. A crash can leave an unreferenced blob, never a partial capture.
            fd, temporary = tempfile.mkstemp(prefix=".capture-", dir=str(path.parent))
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(gzip.compress(body, mtime=0))
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, str(path))
                except FileExistsError:
                    pass
                _sync_directory(path.parent)
                _sync_directory(self.raw_dir)
            finally:
                os.unlink(temporary)
        if (path.is_symlink() or not path.is_file() or
                _hash(gzip.decompress(path.read_bytes())) != digest):
            raise OSError("Existing raw evidence failed integrity check: {}".format(digest))
        return path.stat().st_size

    def save_capture(self, source_id, body, metadata):
        """Save one attempt; identical body bytes share an immutable raw blob.

        Re-saving the same source, metadata and body is idempotent. A distinct
        retrieval timestamp or attempt metadata produces a distinct capture ID.
        Missing retrieved_at is stamped now; explicit null remains unknown.
        """
        _identifier(source_id, "source_id")
        if not isinstance(body, bytes) or not isinstance(metadata, dict):
            raise TypeError("body must be bytes and metadata must be a dict")
        meta = json.loads(_json(metadata))
        if "retrieved_at" not in meta:
            meta["retrieved_at"] = time.time()
        retrieved_at = _number(meta["retrieved_at"], "retrieved_at")
        digest = _hash(body)
        capture_id = _capture_id(source_id, digest, meta)
        stored_bytes = self._save_blob(body, digest)
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO captures VALUES (?, ?, ?, ?, ?, ?, ?)",
                (capture_id, source_id, retrieved_at, digest, len(body), stored_bytes, _json(meta)),
            )
        return capture_id

    def read_capture(self, capture_id):
        """Return original response bytes, checking their saved hash and size."""
        row = self.connection.execute(
            "SELECT body_sha256, byte_count, stored_bytes FROM captures WHERE capture_id=?",
            (capture_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown capture: {}".format(capture_id))
        path = self._blob_path(row["body_sha256"])
        if path.is_symlink():
            raise OSError("Unsafe raw evidence path")
        compressed = path.read_bytes()
        body = gzip.decompress(compressed)
        if (_hash(body) != row["body_sha256"] or len(body) != row["byte_count"] or
                len(compressed) != row["stored_bytes"]):
            raise OSError("Raw evidence failed integrity check: {}".format(capture_id))
        return body

    def add_observations(self, domain, records):
        """Return new revision count; link duplicate observations to all captures.

        ``raw_ref`` must name a saved capture. Acquisition time and derived
        position age are capture context, not new measurements. They remain
        available per capture; measurements are never filled.
        """
        _identifier(domain, "domain")
        inserted = 0
        with self.connection:
            for original in records:
                if not isinstance(original, dict):
                    raise TypeError("observation must be a dict")
                record = json.loads(_json(original))
                raw_ref = _identifier(record.get("raw_ref"), "raw_ref")
                if not self.connection.execute(
                        "SELECT 1 FROM captures WHERE capture_id=?", (raw_ref,)).fetchone():
                    raise ValueError("Unknown capture: {}".format(raw_ref))
                timestamp = _number(record.get("timestamp"), "timestamp")
                normalized = _normalized(record)
                context = {key: value for key, value in record.items() if key in _CONTEXT_FIELDS}
                if normalized.get("observation_id") is None:
                    normalized.pop("observation_id", None)
                    normalized["observation_id"] = _hash(_json(normalized).encode("utf-8"))
                observation_id = _identifier(normalized["observation_id"], "observation_id")
                digest = _hash(_json(normalized).encode("utf-8"))
                revision_id = _hash(_json([domain, observation_id, digest]).encode("utf-8"))
                record = dict(normalized, raw_ref=raw_ref, **context)
                cursor = self.connection.execute(
                    "INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (revision_id, observation_id, digest, domain, timestamp,
                     record.get("entity_id"), record.get("source_id"),
                     _json(record.get("region")), raw_ref, _json(record)),
                )
                inserted += cursor.rowcount
                self.connection.execute(
                    "INSERT OR IGNORE INTO observation_captures(revision_id, capture_id, context_json, snapshot_at) "
                    "VALUES (?, ?, ?, ?)",
                    (revision_id, raw_ref, _json(context), _json_number(_json(context), "snapshot_at")),
                )
        return inserted

    def observations(self, domain, start, end, time_field="timestamp", limit=None):
        """Return distinct revisions with capture context inside the query.

        ``snapshot_at`` filters each acquisition, then chooses among qualifying
        acquisitions. A historical baseline never receives a later snapshot or
        its provenance links. The default ``timestamp`` filters measurement time;
        it selects the earliest capture, retaining its actual time and flags.
        ``limit`` is an exact positive cap; request cap+1 to detect truncation.
        SQL applies time eligibility before limiting loaded records. Timestamp
        and snapshot_at use indexed columns; other numeric fields use a JSON UDF.
        """
        _bounds(start, end)
        _identifier(time_field, "time_field")
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0):
            raise ValueError("limit must be a positive integer or null")
        args = [domain]
        query = "SELECT * FROM observations WHERE domain=?"
        if time_field in _CONTEXT_FIELDS:
            conditions = ["oc.revision_id=observations.revision_id"]
            for bound, operator in ((start, ">="), (end, "<=")):
                if bound is not None:
                    if time_field == "snapshot_at":
                        expression = "oc.snapshot_at"
                    else:
                        expression = "satresearch_number(oc.context_json, ?)"
                        args.append(time_field)
                    conditions.append(expression + operator + "?")
                    args.append(bound)
            query += " AND EXISTS (SELECT 1 FROM observation_captures oc WHERE " + " AND ".join(conditions) + ")"
        else:
            expression = "timestamp" if time_field == "timestamp" else "satresearch_number(record_json, ?)"
            if start is not None:
                query += " AND " + expression + ">=?"
                if time_field != "timestamp":
                    args.append(time_field)
                args.append(start)
            if end is not None:
                query += " AND " + expression + "<=?"
                if time_field != "timestamp":
                    args.append(time_field)
                args.append(end)
        query += " ORDER BY timestamp, entity_id, revision_id"
        if limit is not None:
            query += " LIMIT ?"
            args.append(limit)
        result = []
        for row in self.connection.execute(query, args):
            original = json.loads(row["record_json"])
            base = _normalized(original)
            candidates = []
            for link in self.connection.execute(
                "SELECT oc.capture_id, oc.context_json, c.retrieved_at "
                "FROM observation_captures oc JOIN captures c ON c.capture_id=oc.capture_id "
                "WHERE oc.revision_id=?",
                (row["revision_id"],),
            ):
                context = json.loads(link["context_json"])
                # Earlier stores hashed these flags as part of the measurement;
                # all links for that revision therefore shared the saved flags.
                if "quality_flags" not in context and "quality_flags" in original:
                    context["quality_flags"] = original["quality_flags"]
                record = dict(base, **context)
                value = record.get(time_field)
                if start is not None or end is not None:
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or not math.isfinite(value)):
                        continue
                    if (start is not None and value < start) or (end is not None and value > end):
                        continue
                snapshot = record.get("snapshot_at")
                if isinstance(snapshot, bool) or not isinstance(snapshot, (int, float)):
                    snapshot = link["retrieved_at"]
                order = snapshot if snapshot is not None else float("-inf")
                record["raw_ref"] = link["capture_id"]
                candidates.append((order, link["capture_id"], record))
            if not candidates:
                continue
            choose = min if time_field == "timestamp" else max
            record = choose(candidates, key=lambda item: item[:2])[2]
            if domain == "satellite" or "first_snapshot_at" in record:
                snapshots = [item[2]["snapshot_at"] for item in candidates
                             if isinstance(item[2].get("snapshot_at"), (int, float))
                             and not isinstance(item[2].get("snapshot_at"), bool)]
                if snapshots:
                    record["first_snapshot_at"] = min(snapshots)
            record["revision_id"] = row["revision_id"]
            record["raw_refs"] = sorted(item[1] for item in candidates)
            result.append(record)
        return result

    def captures(self, start, end):
        _bounds(start, end)
        query = "SELECT * FROM captures WHERE 1=1"
        args = []
        if start is not None:
            query += " AND retrieved_at>=?"
            args.append(start)
        if end is not None:
            query += " AND retrieved_at<=?"
            args.append(end)
        result = []
        for row in self.connection.execute(query + " ORDER BY retrieved_at, capture_id", args):
            record = json.loads(row["metadata_json"])
            record.update(capture_id=row["capture_id"], source_id=row["source_id"],
                          raw_ref=row["capture_id"],
                          retrieved_at=row["retrieved_at"], body_sha256=row["body_sha256"],
                          byte_count=row["byte_count"], body_bytes=row["byte_count"],
                          stored_bytes=row["stored_bytes"], compression="gzip",
                          raw_path=str(self._blob_path(row["body_sha256"]).relative_to(self.data_dir)))
            result.append(record)
        return result

    @staticmethod
    def _event_times(record):
        def first(keys):
            for key in keys:
                if record.get(key) is not None:
                    return _number(record[key], key)
            return None
        start = first(("start", "start_time", "start_ts", "timestamp"))
        end = first(("end", "end_time", "end_ts"))
        if end is None:
            end = start
        _bounds(start, end)
        return start, end

    def save_events(self, events):
        """Upsert machine findings, returning new IDs; never overwrite reviews."""
        inserted = 0
        with self.connection:
            for original in events:
                if not isinstance(original, dict):
                    raise TypeError("event must be a dict")
                record = json.loads(_json(original))
                for key in ("review_status", "review_note", "reviewed_at", "review_id"):
                    record.pop(key, None)
                event_id = record.get("event_id") or record.get("id")
                if not event_id:
                    event_id = _hash(_json(record).encode("utf-8"))
                _identifier(event_id, "event_id")
                record["event_id"] = event_id
                start, end = self._event_times(record)
                now = time.time()
                cursor = self.connection.execute(
                    "INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)",
                    (event_id, start, end, now, now, _json(record)),
                )
                inserted += cursor.rowcount
                if not cursor.rowcount:
                    self.connection.execute(
                        "UPDATE events SET start_time=?, end_time=?, updated_at=?, record_json=? WHERE event_id=?",
                        (start, end, now, _json(record), event_id),
                    )
        return inserted

    def events(self, start, end):
        """Return events overlapping the inclusive interval and latest review."""
        _bounds(start, end)
        query = "SELECT * FROM events WHERE 1=1"
        args = []
        if start is not None:
            query += " AND end_time>=?"
            args.append(start)
        if end is not None:
            query += " AND start_time<=?"
            args.append(end)
        result = []
        for row in self.connection.execute(query + " ORDER BY start_time, event_id", args):
            record = json.loads(row["record_json"])
            latest = self.connection.execute(
                "SELECT * FROM reviews WHERE event_id=? ORDER BY review_id DESC LIMIT 1",
                (row["event_id"],),
            ).fetchone()
            record["review_status"] = latest["status"] if latest else None
            record["review_note"] = latest["note"] if latest else None
            record["reviewed_at"] = latest["reviewed_at"] if latest else None
            result.append(record)
        return result

    def review(self, event_id, status, note):
        if status not in REVIEW_STATUSES:
            raise ValueError("Unsupported analyst review status: {}".format(status))
        if note is not None and not isinstance(note, str):
            raise TypeError("review note must be a string or null")
        with self.connection:
            if not self.connection.execute(
                    "SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
                raise ValueError("Unknown event: {}".format(event_id))
            self.connection.execute(
                "INSERT INTO reviews(event_id, status, note, reviewed_at) VALUES (?, ?, ?, ?)",
                (event_id, status, note, time.time()),
            )

    def reviews(self):
        return [dict(row) for row in self.connection.execute("SELECT * FROM reviews ORDER BY review_id")]

    def stats(self):
        result = {table: self.connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                  for table in ("captures", "observations", "observation_captures", "events", "reviews")}
        result["observations_by_domain"] = dict(self.connection.execute(
            "SELECT domain, COUNT(*) FROM observations GROUP BY domain"))
        blobs = self.connection.execute(
            "SELECT body_sha256, MAX(byte_count), MAX(stored_bytes) FROM captures GROUP BY body_sha256").fetchall()
        result["raw_blobs"] = len(blobs)
        result["body_bytes"] = sum(row[1] for row in blobs)
        result["stored_bytes"] = sum(row[2] for row in blobs)
        result["raw_bytes"] = result["stored_bytes"]
        return result

    def verify(self):
        """Audit saved bytes and relational integrity, never scientific truth."""
        errors = []
        checked = set()
        actual_sizes = {}
        try:
            for row in self.connection.execute("PRAGMA integrity_check"):
                if row[0] != "ok":
                    errors.append("database: " + row[0])
            for row in self.connection.execute("PRAGMA foreign_key_check"):
                errors.append("broken reference: " + repr(tuple(row)))
            for row in self.connection.execute("SELECT * FROM captures"):
                digest = row["body_sha256"]
                path = self._blob_path(digest)
                if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                    errors.append("invalid raw hash: " + row["capture_id"])
                    continue
                if digest not in checked:
                    checked.add(digest)
                    if path.is_symlink() or not path.is_file():
                        errors.append("missing or unsafe raw file: " + digest)
                    else:
                        compressed = path.read_bytes()
                        body = gzip.decompress(compressed)
                        actual_sizes[digest] = (len(body), len(compressed))
                        if _hash(body) != digest:
                            errors.append("raw hash mismatch: " + digest)
                if digest in actual_sizes and actual_sizes[digest] != (row["byte_count"], row["stored_bytes"]):
                    errors.append("raw size metadata mismatch: " + row["capture_id"])
                metadata = json.loads(row["metadata_json"])
                if _capture_id(row["source_id"], digest, metadata) != row["capture_id"]:
                    errors.append("capture metadata mismatch: " + row["capture_id"])
                if metadata.get("retrieved_at") != row["retrieved_at"]:
                    errors.append("capture time index mismatch: " + row["capture_id"])
            for row in self.connection.execute("SELECT * FROM observations"):
                record = json.loads(row["record_json"])
                normalized = _normalized(record)
                digest = _hash(_json(normalized).encode("utf-8"))
                if digest != row["content_sha256"]:
                    # Accept intact earlier prototype identity rules, without
                    # pretending an algorithm change indicates damaged evidence.
                    legacy = {k: v for k, v in record.items() if k not in
                              {"snapshot_at", "position_age_s", "feed_timestamp", "raw_ref", "raw_refs", "revision_id"}}
                    legacy_digest = _hash(_json(legacy).encode("utf-8"))
                    if legacy_digest == row["content_sha256"]:
                        digest = legacy_digest
                expected = _hash(_json([row["domain"], row["observation_id"], digest]).encode("utf-8"))
                if digest != row["content_sha256"] or expected != row["revision_id"]:
                    errors.append("observation content mismatch: " + row["revision_id"])
                if (record.get("timestamp") != row["timestamp"] or
                        record.get("raw_ref") != row["raw_ref"] or
                        record.get("observation_id") != row["observation_id"] or
                        record.get("entity_id") != row["entity_id"] or
                        record.get("source_id") != row["source_id"] or
                        _json(record.get("region")) != row["region_json"]):
                    errors.append("observation index mismatch: " + row["revision_id"])
                if not self.connection.execute(
                        "SELECT 1 FROM observation_captures WHERE revision_id=? AND capture_id=?",
                        (row["revision_id"], row["raw_ref"])).fetchone():
                    errors.append("missing observation capture link: " + row["revision_id"])
            for row in self.connection.execute("SELECT * FROM observation_captures"):
                context = json.loads(row["context_json"])
                if not isinstance(context, dict) or set(context) - _CONTEXT_FIELDS:
                    errors.append("invalid acquisition context: " + row["revision_id"])
                if _json_number(row["context_json"], "snapshot_at") != row["snapshot_at"]:
                    errors.append("capture context time index mismatch: " + row["revision_id"])
            for row in self.connection.execute("SELECT * FROM events"):
                record = json.loads(row["record_json"])
                if (record.get("event_id") != row["event_id"] or
                        self._event_times(record) != (row["start_time"], row["end_time"])):
                    errors.append("event index mismatch: " + row["event_id"])
        except (OSError, EOFError, ValueError, TypeError, sqlite3.DatabaseError) as error:
            errors.append("integrity audit error: " + str(error))
        return {"ok": not errors, "status": "passed" if not errors else "failed",
                "errors": errors, "raw_blobs_checked": len(checked), "counts": self.stats(),
                "scope": "Saved-byte and database integrity only; not authenticity or scientific verification."}
