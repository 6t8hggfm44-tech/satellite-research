"""Offline satellite *catalog* screening; no orbit propagation or intent inference.

Input formats: numeric-ID 2LE/3LE text and flat OMM-keyword JSON (including
CelesTrak's omitted EARTH/TEME/UTC/SGP4 metadata convention). The caller archives
the original response. Invalid entries are rejected with warnings, not repaired.

Format references:
https://celestrak.org/NORAD/documentation/tle-fmt.php
https://celestrak.org/columns/v04n03/ (epoch pivot and day-zero convention)
https://celestrak.org/NORAD/documentation/gp-data-formats.php

DEFAULTS are experimental attention thresholds, not calibrated anomaly rates or
physical limits. Record overrides and detector version in each run. Catalog
retrieval time selects the screening window; orbital epoch is a fitting time.
Neither is a measured maneuver time. All public times are Unix seconds in UTC.
"""

import calendar
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone


DETECTOR_VERSION = "0.1.0"
DEFAULTS = {
    "max_epoch_age_hours": 72.0,
    "max_baseline_gap_hours": 168.0,
    "mean_motion_change_rev_day": 0.1,
    "inclination_change_deg": 0.2,
    "raan_change_deg": 1.0,
}
_ELEMENTS = (
    "mean_motion_rev_day", "inclination_deg", "eccentricity", "raan_deg",
    "arg_pericenter_deg", "mean_anomaly_deg",
)
_OMM_FIELDS = dict(zip(_ELEMENTS, (
    "MEAN_MOTION", "INCLINATION", "ECCENTRICITY", "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER", "MEAN_ANOMALY",
)))
_CONVENTIONS = {
    "CENTER_NAME": "EARTH", "REF_FRAME": "TEME", "TIME_SYSTEM": "UTC",
    "MEAN_ELEMENT_THEORY": "SGP4",
}
_COMMON_LIMITS = [
    "Catalog mean elements are fitted estimates, not measured positions.",
    "Thresholds are experimental and uncalibrated; priority is not probability.",
    "No propagation, covariance, collision probability, rendezvous or intent test was performed.",
]


def _number(value, field):
    if value is None or isinstance(value, bool):
        raise ValueError("missing or invalid " + field)
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("invalid " + field)
    if not math.isfinite(result):
        raise ValueError("non-finite " + field)
    return result


def _time(value, allow_naive=False):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _number(value, "timestamp")
    if not isinstance(value, str):
        raise ValueError("timestamp must be Unix seconds or ISO 8601")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid ISO 8601 timestamp")
    if dt.tzinfo is None:
        if not allow_naive:
            raise ValueError("timestamp timezone missing")
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _identity(value):
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,9}", text) or int(text) == 0:
        raise ValueError("unsupported NORAD catalog ID (numeric 1-9 digits required)")
    return str(int(text))


def _validate_elements(record):
    for field in _ELEMENTS:
        record[field] = _number(record.get(field), field)
    if record["mean_motion_rev_day"] <= 0:
        raise ValueError("mean motion must be positive")
    if not 0 <= record["inclination_deg"] <= 180:
        raise ValueError("inclination outside [0, 180]")
    if not 0 <= record["eccentricity"] < 1:
        raise ValueError("eccentricity outside [0, 1)")
    for field in ("raan_deg", "arg_pericenter_deg", "mean_anomaly_deg"):
        if not 0 <= record[field] < 360:
            raise ValueError(field + " outside [0, 360)")


def _digest(prefix, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _signature(record):
    return tuple(record[field] for field in _ELEMENTS)


def _epoch_key(record):
    return record["source_id"], record["entity_id"], record["epoch"]


def _tle_record(name, line1, line2):
    for expected, line in (("1", line1), ("2", line2)):
        if len(line) != 69 or not line.startswith(expected + " "):
            raise ValueError("TLE line number/length invalid (69 columns required)")
        if not re.fullmatch(r"[0-9A-Z .+\-]+", line):
            raise ValueError("invalid TLE character")
        if not line[-1].isdigit():
            raise ValueError("TLE checksum missing")
        checksum = sum(int(c) if c.isdigit() else (1 if c == "-" else 0)
                       for c in line[:68]) % 10
        if checksum != int(line[-1]):
            raise ValueError("TLE checksum mismatch")
    if line1[2:7] != line2[2:7]:
        raise ValueError("TLE line identities disagree")
    if line1[62] != "0":
        raise ValueError("unsupported TLE ephemeris type (standard GP type 0 required)")
    entity = _identity(line1[2:7])
    if not re.fullmatch(r"\d{2}", line1[18:20]) or not re.fullmatch(r"\d{3}\.\d{8}", line1[20:32]):
        raise ValueError("invalid TLE epoch format")
    yy = int(line1[18:20])
    year = 1900 + yy if yy >= 57 else 2000 + yy
    day = float(line1[20:32])
    if not 0 <= day < (367 if calendar.isleap(year) else 366):
        raise ValueError("TLE epoch day outside year")
    epoch = (datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)).timestamp()
    if not re.fullmatch(r"\d{7}", line2[26:33]):
        raise ValueError("invalid TLE implied-decimal eccentricity")
    record = {
        "entity_id": entity, "name": name or None, "epoch": epoch,
        "mean_motion_rev_day": line2[52:63], "inclination_deg": line2[8:16],
        "eccentricity": "0." + line2[26:33], "raan_deg": line2[17:25],
        "arg_pericenter_deg": line2[34:42], "mean_anomaly_deg": line2[43:51],
        "input_format": "tle", "epoch_original": line1[18:32],
        "quality_flags": [], "format_assumptions": ["TLE epoch year uses the 1957-2056 convention."],
    }
    _validate_elements(record)
    return record


def _omm_record(item):
    if not isinstance(item, dict):
        raise ValueError("OMM entry must be an object")
    assumptions = []
    for field, expected in _CONVENTIONS.items():
        supplied = item.get(field)
        if supplied is None or supplied == "":
            assumptions.append(field + "=" + expected + " assumed under CelesTrak GP JSON convention")
        elif str(supplied).upper() != expected:
            raise ValueError("unsupported OMM " + field + "=" + str(supplied))
    if not isinstance(item.get("EPOCH"), str) or "T" not in item["EPOCH"]:
        raise ValueError("OMM EPOCH must be an ISO 8601 string")
    record = {field: item.get(key) for field, key in _OMM_FIELDS.items()}
    record.update({
        "entity_id": _identity(item.get("NORAD_CAT_ID")),
        "name": str(item["OBJECT_NAME"]) if item.get("OBJECT_NAME") is not None else None,
        "epoch": _time(item["EPOCH"], allow_naive=True),
        "epoch_original": item["EPOCH"], "input_format": "omm_json",
        "quality_flags": ["omm_metadata_assumed"] if assumptions else [],
        "format_assumptions": assumptions,
    })
    _validate_elements(record)
    return record


def _merge_repeats(records, warnings=None):
    """Deduplicate identical epoch/elements; keep latest retrieval and all refs.

    Conflicting element signatures at the same source/object/epoch are retained
    and flagged. Names and raw artifact names do not determine orbital identity.
    """
    groups = {}
    for original in records:
        record = dict(original)
        record["quality_flags"] = list(original.get("quality_flags", []))
        record["first_snapshot_at"] = original.get("first_snapshot_at", record["snapshot_at"])
        record["raw_refs"] = sorted(set(original.get("raw_refs", []) + [original["raw_ref"]]))
        key = _epoch_key(record) + _signature(record)
        if key in groups:
            previous = groups[key]
            chosen = max((previous, record), key=lambda r: (r["snapshot_at"], r["raw_ref"], r.get("name") or ""))
            merged = dict(chosen)
            merged["first_snapshot_at"] = min(previous["first_snapshot_at"], record["first_snapshot_at"])
            merged["raw_refs"] = sorted(set(previous["raw_refs"] + record["raw_refs"]))
            merged["quality_flags"] = sorted(set(previous["quality_flags"] + record["quality_flags"] + ["duplicate_epoch_elements"]))
            groups[key] = merged
            if warnings is not None:
                warnings.append("duplicate epoch/elements collapsed for NORAD " + record["entity_id"])
        else:
            groups[key] = record
    by_epoch = defaultdict(list)
    for record in groups.values():
        by_epoch[_epoch_key(record)].append(record)
    for key, values in by_epoch.items():
        if len(values) > 1:
            for record in values:
                record["quality_flags"] = sorted(set(record["quality_flags"] + ["conflicting_elements_same_epoch"]))
            if warnings is not None:
                warnings.append("conflicting element records at the same epoch for NORAD " + key[1])
    return sorted(groups.values(), key=lambda r: (_epoch_key(r), _signature(r), r["snapshot_at"]))


def normalize_satellites(payload, source_id, snapshot_at, raw_ref):
    """Return (records, warnings[str]); no network, filesystem or propagation.

    Supports raw 2LE/3LE, JSON text/list/single flat OMM object, and data/body/tle/
    satellites wrappers. A caller-provided snapshot time must have known UTC
    interpretation. Unsupported metadata/invalid elements reject that entry.
    Six-plus-digit numeric NORAD IDs are supported in JSON; Alpha-5 TLE IDs are
    explicitly unsupported rather than silently mapped to another object.
    """
    warnings = []
    try:
        snapshot = _time(snapshot_at)
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id is required")
        if not isinstance(raw_ref, str) or not raw_ref.strip():
            raise ValueError("raw_ref is required")
        for _ in range(8):
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8-sig")
            if isinstance(payload, str) and payload.lstrip("\ufeff \r\n\t").startswith(("[", "{")):
                payload = json.loads(payload.lstrip("\ufeff"))
                continue
            if isinstance(payload, dict) and "NORAD_CAT_ID" not in payload:
                keys = [k for k in ("data", "body", "tle", "satellites") if k in payload]
                if len(keys) == 1:
                    payload = payload[keys[0]]
                    continue
            break
    except (ValueError, TypeError, UnicodeError) as exc:
        return [], ["satellite payload rejected: " + str(exc)]

    parsed = []
    if isinstance(payload, str):
        name, first = None, None
        for index, line in enumerate(payload.lstrip("\ufeff").splitlines(), 1):
            line = line.rstrip()
            if not line.strip():
                continue
            if line.startswith("1 "):
                if first is not None:
                    warnings.append("TLE line 1 without line 2 before line " + str(index))
                first = line
            elif line.startswith("2 "):
                if first is None:
                    warnings.append("orphan TLE line 2 at line " + str(index))
                else:
                    try:
                        parsed.append(_tle_record(name, first, line))
                    except ValueError as exc:
                        warnings.append("TLE ending at line {} rejected: {}".format(index, exc))
                name, first = None, None
            else:
                if first is not None:
                    warnings.append("TLE line 1 without adjacent line 2 before line " + str(index))
                    first = None
                name = line[2:].strip() if line.startswith("0 ") else line.strip()
        if first is not None:
            warnings.append("TLE line 1 without line 2 at end of payload")
        if not parsed and not warnings:
            warnings.append("no supported TLE records in payload")
    elif isinstance(payload, (list, dict)):
        for index, item in enumerate(payload if isinstance(payload, list) else [payload]):
            try:
                record = _omm_record(item)
                parsed.append(record)
                if record["format_assumptions"]:
                    warnings.append("OMM NORAD {}: {}".format(record["entity_id"], "; ".join(record["format_assumptions"])))
            except (ValueError, TypeError, OverflowError) as exc:
                warnings.append("OMM entry {} rejected: {}".format(index, exc))
    else:
        warnings.append("unsupported satellite payload type")

    for record in parsed:
        record.update({
            "timestamp": record["epoch"], "snapshot_at": snapshot,
            "source_id": source_id, "raw_ref": raw_ref, "raw_refs": [raw_ref],
            "reference_frame": "TEME", "time_system": "UTC",
            "center_name": "EARTH", "mean_element_theory": "SGP4",
        })
        if record["epoch"] > snapshot:
            record["quality_flags"].append("epoch_after_snapshot")
            warnings.append("future epoch relative to retrieval for NORAD " + record["entity_id"])
        record["observation_id"] = _digest("satobs_", [_epoch_key(record), _signature(record)])
    return _merge_repeats(parsed, warnings), warnings


def _event(detector, record, involved, config, summary, metrics, limitations, priority=20, at=None):
    evidence = sorted(set(r["observation_id"] for r in involved))
    refs = sorted(set(ref for r in involved for ref in r.get("raw_refs", [r["raw_ref"]])))
    metrics = dict(metrics, threshold_config=dict(config), threshold_status="experimental_uncalibrated",
                   time_basis="catalog retrieval time; orbital epochs are fit reference times")
    return {
        "event_id": _digest("satevent_", [detector, DETECTOR_VERSION, record["entity_id"],
                                         record["source_id"], evidence, config]),
        "domain": "satellite", "detector_id": detector, "detector_version": DETECTOR_VERSION,
        "entity_id": record["entity_id"], "region": "orbital_catalog",
        "start": record["snapshot_at"] if at is None else at,
        "end": record["snapshot_at"] if at is None else at,
        "priority": priority, "summary": summary, "metrics": metrics,
        "evidence_ids": evidence, "raw_refs": refs,
        "limitations": _COMMON_LIMITS + limitations,
        "review_status": "unreviewed", "hypothesis_status": "not_tested",
    }


def screen_satellites(records, baseline_records, config, window_start, window_end):
    """Screen catalogs retrieved in inclusive [window_start, window_end].

    Baseline entries must have been retrieved strictly before window_start, with
    epoch no later than their retrieval. Comparisons use only the same object
    AND source, strictly earlier epochs, and no later retrieval than the current
    record. Earlier in-window current records can be predecessors; baseline
    arguments cannot leak in-window/future data into that history. Multiple
    historical epochs in one capture may be compared in epoch order. The closest
    eligible epoch is used, subject to max_baseline_gap_hours. Repeated elements
    at a repeated epoch are not a new update. Conflicted epochs are never used
    to assert a discontinuity. Missing usable history produces no change event.

    Staleness and conflicts concern catalog availability at retrieval, never
    physical flight/orbit events. No interpolation or secular-motion correction
    is attempted; even an element discontinuity can be an ordinary refit.
    """
    start, end = _time(window_start), _time(window_end)
    if end < start:
        raise ValueError("window_end precedes window_start")
    settings = dict(DEFAULTS)
    if config is not None:
        unknown = set(config) - set(settings)
        if unknown:
            raise ValueError("unknown satellite settings: " + ", ".join(sorted(unknown)))
        settings.update(config)
    for key, value in settings.items():
        settings[key] = _number(value, key)
        if settings[key] < 0:
            raise ValueError(key + " must be nonnegative")

    current = _merge_repeats([r for r in records if start <= r["snapshot_at"] <= end])
    baseline = _merge_repeats([r for r in baseline_records
                               if r["snapshot_at"] < start and r["epoch"] <= r["snapshot_at"]])
    all_records = baseline + current
    conflicts = defaultdict(list)
    for record in all_records:
        conflicts[_epoch_key(record)].append(record)
    conflict_keys = {k for k, values in conflicts.items()
                     if len({_signature(r) for r in values}) > 1 or
                     any("conflicting_elements_same_epoch" in r.get("quality_flags", []) for r in values)}
    events, reported_conflicts = [], set()
    history = defaultdict(list)
    for record in baseline:
        history[(record["source_id"], record["entity_id"])].append(record)
    for record in sorted(current, key=lambda r: (r["first_snapshot_at"], _epoch_key(r), _signature(r))):
        key = _epoch_key(record)
        if key in conflict_keys:
            if key not in reported_conflicts:
                involved = conflicts[key]
                events.append(_event("satellite_catalog_conflict", record, involved, settings,
                                     "Conflicting catalog elements share one object and epoch.",
                                     {"epoch": record["epoch"], "distinct_element_sets": len({_signature(r) for r in involved})},
                                     ["The conflicting epoch is excluded from element-change comparisons."],
                                     at=max(r["first_snapshot_at"] for r in involved)))
                reported_conflicts.add(key)
        age_hours = (record["snapshot_at"] - record["epoch"]) / 3600.0
        first_age_hours = (record["first_snapshot_at"] - record["epoch"]) / 3600.0
        if first_age_hours < 0:
            events.append(_event("satellite_catalog_future_epoch", record, [record], settings,
                                 "Catalog epoch is later than its recorded retrieval.",
                                 {"epoch": record["epoch"], "epoch_age_hours": first_age_hours},
                                 ["Future epochs are excluded from historical change screening; check time/provenance."],
                                 at=record["first_snapshot_at"]))
            continue
        if age_hours > settings["max_epoch_age_hours"]:
            events.append(_event("satellite_catalog_stale", record, [record], settings,
                                 "Retrieved catalog elements exceed the configured age screen.",
                                 {"epoch": record["epoch"], "epoch_age_hours": age_hours},
                                 ["Age is not a measured position error or evidence of a physical anomaly."]))
        bucket = history[(record["source_id"], record["entity_id"])]
        earlier = [r for r in bucket if r["epoch"] < record["epoch"]
                   and r["first_snapshot_at"] <= record["first_snapshot_at"] and _epoch_key(r) not in conflict_keys]
        # A repeated epoch is not a new update, even if another older epoch is available.
        repeated = any(r["epoch"] == record["epoch"] for r in bucket)
        if earlier and not repeated and key not in conflict_keys:
            previous = max(earlier, key=lambda r: (r["epoch"], r["snapshot_at"], r["observation_id"]))
            gap_hours = (record["epoch"] - previous["epoch"]) / 3600.0
            if gap_hours <= settings["max_baseline_gap_hours"]:
                deltas = {
                    "mean_motion_change_rev_day": record["mean_motion_rev_day"] - previous["mean_motion_rev_day"],
                    "inclination_change_deg": record["inclination_deg"] - previous["inclination_deg"],
                    "raan_change_deg": (record["raan_deg"] - previous["raan_deg"] + 180.0) % 360.0 - 180.0,
                }
                exceeded = sorted(k for k, value in deltas.items() if abs(value) > settings[k])
                if exceeded:
                    metrics = dict(deltas, exceeded_thresholds=exceeded, previous_epoch=previous["epoch"],
                                   epoch=record["epoch"], epoch_gap_hours=gap_hours,
                                   previous_snapshot_at=previous["first_snapshot_at"],
                                   previous_latest_snapshot_at=previous["snapshot_at"], source_id=record["source_id"])
                    events.append(_event("satellite_element_discontinuity", record, [previous, record], settings,
                                         "Successive catalog mean elements exceed configured change screens.", metrics,
                                         ["Element differences can reflect refitting, ordinary drift, drag or maintenance; they do not confirm a maneuver.",
                                          "RAAN uses the shortest wrapped angular difference; no propagation or epoch alignment was performed.",
                                          "RAAN changes can be ill-conditioned near equatorial orbits and are not a plane-change measurement.",
                                          "Same-source history avoids a provider switch but is not independent physical validation."], 50,
                                         at=record["first_snapshot_at"]))
        bucket.append(record)
    return sorted(events, key=lambda event: (event["start"], event["entity_id"], event["detector_id"], event["event_id"]))
