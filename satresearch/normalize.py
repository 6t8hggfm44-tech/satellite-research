"""Normalize preserved GEV position products without upgrading their provenance."""

import hashlib
import json
import math
import re

VERSION = "aircraft-normalizer-1"


def number(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def identity(record):
    # A second download of the same position is not a new observation.
    excluded = {"observation_id", "raw_ref", "raw_refs", "snapshot_at", "position_age_s", "feed_timestamp"}
    data = {k: v for k, v in record.items() if k not in excluded}
    if "quality_flags" in data:
        data["quality_flags"] = [v for v in data["quality_flags"] if v not in {"stale_position", "stale_feed", "future_position"}]
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def inside(lat, lon, region):
    if lat is None or lon is None:
        return False
    west, south, east, north = region["bbox"]
    return south <= lat <= north and west <= lon <= east


def finish(record, snapshot_at, raw_ref, feed_stale=False):
    flags = record.setdefault("quality_flags", [])
    record.update(snapshot_at=snapshot_at, raw_ref=raw_ref)
    lat, lon = record.get("lat"), record.get("lon")
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        flags.append("invalid_position")
    ts = record.get("timestamp")
    if ts is None:
        flags.append("missing_position_time")
    elif ts > snapshot_at + 5:
        flags.append("future_position")
    if record.get("position_age_s") is not None and record["position_age_s"] > 30:
        flags.append("stale_position")
    if feed_stale:
        flags.append("stale_feed")
    if record.get("on_ground") is True:
        flags.append("on_ground")
    if record.get("position_source", "unknown") == "unknown":
        flags.append("unknown_position_source")
    flags.append("unknown_field_age")
    record["quality_flags"] = sorted(set(flags))
    record["normalizer_version"] = VERSION
    record["observation_id"] = identity(record)
    return record


def normalize_snapshot(payload, headers, region, snapshot_at, raw_ref=""):
    if not isinstance(payload, dict) or "states" not in payload or payload.get("error"):
        raise ValueError("Expected GEV OpenSky-compatible states product")
    states = payload["states"]
    if states is None:
        return [], ["null_states: no usable positions; not evidence of no traffic"]
    if not isinstance(states, list):
        raise ValueError("states must be a list or null")
    headers = {k.lower(): v for k, v in headers.items()}
    fallback = "adsblol-regional" in headers.get("x-opensky-auth-mode-used", "") or headers.get("x-flight-source") == "adsb.lol"
    source = "gev:adsb.lol:normalized" if fallback else "gev:opensky:states"
    feed_ts = number(payload.get("time"))
    stale = "STALE" in headers.get("x-opensky-cache", "").upper()
    stale = stale or feed_ts is None or snapshot_at - feed_ts > 120
    warnings = []
    if fallback:
        warnings.append("GEV fallback drops original position-source and quality fields; method remains unknown")
    if stale:
        warnings.append("stale_or_unknown_feed_time")
    records = []
    for row in states:
        if not isinstance(row, list) or len(row) < 17:
            warnings.append("malformed_state_vector")
            continue
        entity = str(row[0] or "").lower().strip()
        if not re.fullmatch(r"~?[0-9a-f]{6}", entity):
            warnings.append("invalid_identity")
            continue
        lat, lon, ts = number(row[6]), number(row[5]), number(row[3])
        if not inside(lat, lon, region):
            continue  # original complete response is retained separately
        # The GEV adsb.lol fallback writes source=0 even for other methods.
        method = "unknown" if fallback else {0: "adsb", 1: "asterix", 2: "mlat", 3: "flarm"}.get(row[16], "unknown")
        rec = dict(entity_id=entity, timestamp=ts, lat=lat, lon=lon,
                   altitude_m=number(row[7]), groundspeed_mps=number(row[9]),
                   track_deg=number(row[10]), on_ground=row[8] if isinstance(row[8], bool) else None,
                   position_source=method, region=region["id"], source_id=source,
                   altitude_type="barometric",
                   position_age_s=None if ts is None else snapshot_at-ts,
                   feed_timestamp=feed_ts, callsign=str(row[1] or "").strip(),
                   quality_flags=["upstream_normalized_source_unknown"] if fallback else [])
        records.append(finish(rec, snapshot_at, raw_ref, stale))
    return records, sorted(set(warnings))


def normalize_trace(payload, entity_id, regions, snapshot_at, raw_ref=""):
    entity_id = str(entity_id).lower().strip()
    if not re.fullmatch(r"~?[0-9a-f]{6}", entity_id):
        raise ValueError("Expected a six-hex aircraft identifier (optional ~ prefix)")
    if not isinstance(payload, dict) or not isinstance(payload.get("trace"), list):
        raise ValueError("Expected readsb trace array")
    supplied_id = str(payload.get("icao") or "").lower().strip()
    if supplied_id and supplied_id != entity_id.lower().strip():
        raise ValueError("Trace payload identity does not match requested aircraft")
    base = number(payload.get("timestamp"))
    if base is None:
        raise ValueError("Trace has no valid base timestamp")
    records, warnings = [], []
    provider_version = payload.get("version") if isinstance(payload.get("version"), str) else None
    warnings.append("trace_schema_interpretation_not_version_pinned")
    if provider_version is None:
        warnings.append("trace_provider_version_unknown")
    for row in payload["trace"]:
        if not isinstance(row, list) or len(row) < 8:
            warnings.append("malformed_trace_row")
            continue
        offset = number(row[0])
        lat, lon = number(row[1]), number(row[2])
        flags = row[6] if isinstance(row[6], int) and not isinstance(row[6], bool) and row[6] >= 0 else None
        # readsb JSON flags bit0 means stale position (not a measurement age).
        state = row[8] if len(row) > 8 and isinstance(row[8], dict) else {}
        method = row[9] if len(row) > 9 and isinstance(row[9], str) else "unknown"
        method = "mlat" if method == "mlat" else "adsb" if method in {"adsb_icao", "adsb_icao_nt", "adsb_other"} else method
        matches = [r["id"] for r in regions if inside(lat, lon, r)]
        # Retain full traces, but identify events outside the watched regions explicitly.
        rec = dict(entity_id=entity_id, timestamp=None if offset is None else base+offset,
                   lat=lat, lon=lon, altitude_m=None if number(row[3]) is None else float(row[3])*0.3048,
                   groundspeed_mps=None if number(row[4]) is None else float(row[4])*0.514444,
                   track_deg=number(row[5]), position_source=method,
                   region=matches[0] if matches else "outside_watch_regions",
                   source_id="gev:adsb.lol:trace", position_age_s=None,
                   quality_flags=["trace_stale"] if flags is not None and flags & 1 else [],
                   trace_flags=flags, state_metadata=state, provider_version=provider_version,
                   position_stale_flag=None if flags is None else bool(flags & 1),
                   altitude_type="unknown" if flags is None else "geometric" if flags & 8 else "barometric",
                   on_ground=row[3] == "ground")
        # Absence of the stale flag says only that the serializer did not flag it.
        # Do not invent a zero-second measurement age from that absence.
        records.append(finish(rec, snapshot_at, raw_ref))
    return records, sorted(set(warnings))
