"""Deterministic, offline aircraft *reported-data* candidate screening.

These thresholds are uncalibrated prototype settings, not operational limits or
certified interference detectors. Outputs prioritize human review and leave all
causal hypotheses untested. Inputs are never mutated. The inclusive event window
uses Unix seconds; baseline observations must precede its start strictly.

Positions with stale/invalid flags or excessive known age cannot form pairs.
Unknown position age is allowed only for a qualified coordinate-jump candidate;
persistence and historical comparisons require an explicit fresh position age or
an explicitly clear serializer position-stale flag. The latter is not an age of
zero. Neither establishes the age of speed or altitude fields. Optional
``altitude_type`` must be known and match for an altitude-matched baseline.
"""

import hashlib
import json
import math
import statistics
from collections import defaultdict


DETECTOR_VERSION = "0.1.0"
DEFAULTS = {
    "max_position_age_s": 30.0,
    "max_gap_s": 120.0,
    "min_pair_interval_s": 1.0,
    "jump_speed_mps": 600.0,
    "jump_min_distance_m": 5000.0,
    "frozen_radius_m": 20.0,
    "frozen_min_speed_mps": 75.0,
    "frozen_min_duration_s": 180.0,
    "frozen_min_points": 4,
    "low_speed_max_mps": 35.0,
    "low_speed_min_altitude_m": 6000.0,
    "low_speed_min_duration_s": 180.0,
    "low_speed_min_points": 4,
    "baseline_min_samples": 30,
    "baseline_min_days": 3,
    "baseline_lookback_days": 30.0,
    "baseline_mad_multiplier": 6.0,
    "baseline_min_deviation_mps": 75.0,
    "baseline_altitude_tolerance_m": 1500.0,
}

_STALE = {"stale", "stale_position", "position_stale", "trace_stale", "stale_feed"}
_INVALID = {
    "invalid", "invalid_position", "position_invalid", "invalid_coordinates",
    "rejected", "bad_position", "conflicting_duplicate", "duplicate_conflict",
    "missing_position_time", "future_position", "invalid_position_age",
}
_GROUND = {"ground", "on_ground", "on_ground_true", "fixed_transmitter"}
_COMMON_LIMITS = [
    "Prototype thresholds are uncalibrated; priority is review order, not probability.",
    "Processed reported data do not establish physical motion, interference, intent or impact.",
    "Receiver and decoder independence are unknown; shared processing or equipment errors remain possible.",
]


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _text(value, default="unknown"):
    return value.strip() if isinstance(value, str) and value.strip() else default


def _settings(config):
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError("aircraft detector config must be a dictionary")
    settings = {key: config.get(key, default) for key, default in DEFAULTS.items()}
    integers = {"frozen_min_points", "low_speed_min_points", "baseline_min_samples", "baseline_min_days"}
    nonnegative = {"max_position_age_s", "frozen_radius_m", "baseline_altitude_tolerance_m"}
    for key, value in settings.items():
        number = _number(value)
        if number is None or number < 0 or (key not in nonnegative and number == 0):
            raise ValueError("invalid aircraft setting: " + key)
        if key in integers and (number != int(number) or number < (2 if key.endswith("min_points") else 1)):
            raise ValueError("invalid integer aircraft setting: " + key)
        settings[key] = int(number) if key in integers else number
    if settings["max_gap_s"] < settings["min_pair_interval_s"]:
        raise ValueError("max_gap_s must be at least min_pair_interval_s")
    return settings


def _normalize(records):
    """Keep invalid positions as barriers and collapse equal-time observations.

    Equivalent duplicate samples contribute one time slot, preserving all IDs.
    Conflicting equal-time samples, or a reused ID with different observations,
    become barriers instead of arbitrary winner selection or synthetic motion.
    """
    prepared = []
    fingerprints = defaultdict(set)
    for record in records or []:
        if not isinstance(record, dict):
            continue
        timestamp = _number(record.get("timestamp"))
        observation_id = _text(record.get("observation_id"), "")
        entity = _text(record.get("entity_id"), "").lower()
        if timestamp is None or not observation_id or not entity:
            continue
        flags = record.get("quality_flags") or []
        if not isinstance(flags, (list, tuple, set)):
            flags = ["invalid"]
        row = {
            "timestamp": timestamp, "entity_id": entity,
            "region": _text(record.get("region")),
            "source_id": _text(record.get("source_id")),
            "position_source": _text(record.get("position_source")).lower(),
            "altitude_type": _text(record.get("altitude_type")).lower(),
            "position_stale_flag": record.get("position_stale_flag") if isinstance(record.get("position_stale_flag"), bool) else None,
            "on_ground": record.get("on_ground") if isinstance(record.get("on_ground"), bool) else None,
            "flags": sorted({_text(flag, "").lower().replace("-", "_").replace(" ", "_") for flag in flags}),
            "evidence_ids": [observation_id],
            "raw_refs": [_text(record.get("raw_ref"), "")] if record.get("raw_ref") else [],
        }
        for field in ("lat", "lon", "altitude_m", "groundspeed_mps", "track_deg", "position_age_s"):
            row[field] = _number(record.get(field))
        if row["lat"] is None or not -90 <= row["lat"] <= 90:
            row["lat"] = None
        if row["lon"] is None or not -180 <= row["lon"] <= 180:
            row["lon"] = None
        if row["groundspeed_mps"] is not None and row["groundspeed_mps"] < 0:
            row["groundspeed_mps"] = None
        if record.get("position_age_s") is not None and row["position_age_s"] is None:
            row["flags"] = sorted(set(row["flags"]) | {"invalid_position_age"})
        signature = json.dumps({key: value for key, value in row.items() if key not in ("evidence_ids", "raw_refs")}, sort_keys=True)
        fingerprints[observation_id].add(signature)
        prepared.append(row)
    conflicted_ids = {key for key, values in fingerprints.items() if len(values) > 1}
    slots = defaultdict(list)
    for row in prepared:
        slots[(row["entity_id"], row["region"], row["timestamp"])].append(row)
    groups = defaultdict(list)
    for (entity, region, _), rows in sorted(slots.items()):
        signatures = {json.dumps({key: value for key, value in row.items() if key not in ("evidence_ids", "raw_refs")}, sort_keys=True) for row in rows}
        first = dict(rows[0])
        first["evidence_ids"] = sorted({item for row in rows for item in row["evidence_ids"]})
        first["raw_refs"] = sorted({item for row in rows for item in row["raw_refs"] if item})
        if len(signatures) != 1 or conflicted_ids.intersection(first["evidence_ids"]):
            first["flags"] = sorted(set(first["flags"]) | {"conflicting_duplicate"})
            first["lat"] = first["lon"] = None
        groups[(entity, region)].append(first)
    return groups


def _usable(row, settings, require_age=False):
    flags = set(row["flags"])
    age = row["position_age_s"]
    return (
        row["lat"] is not None and row["lon"] is not None
        and not flags.intersection(_STALE | _INVALID)
        and row["position_stale_flag"] is not True
        and (age is None and (not require_age or row["position_stale_flag"] is False) or age is not None and 0 <= age <= settings["max_position_age_s"])
    )


def _moving_fields(row, settings):
    return _usable(row, settings, require_age=True) and row.get("on_ground") is not True and not set(row["flags"]).intersection(_GROUND) and row["groundspeed_mps"] is not None


def _same_source(a, b):
    return all(a[key] != "unknown" and a[key] == b[key] for key in ("source_id", "position_source"))


def _distance(a, b):
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(b["lon"] - a["lon"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def _adjacent(a, b, settings):
    dt = b["timestamp"] - a["timestamp"]
    return settings["min_pair_interval_s"] <= dt <= settings["max_gap_s"]


def _event(detector, rows, priority, summary, metrics, limitations, settings, extra_rows=()):
    start, end = rows[0]["timestamp"], rows[-1]["timestamp"]
    entity, region = rows[0]["entity_id"], rows[0]["region"]
    identity = json.dumps([DETECTOR_VERSION, detector, entity, region, start, end], separators=(",", ":"))
    evidence = sorted({item for row in list(rows) + list(extra_rows) for item in row["evidence_ids"]})
    raw_refs = sorted({item for row in list(rows) + list(extra_rows) for item in row["raw_refs"]})
    metrics = dict(metrics)
    unflagged_unknown_age = sum(row["position_age_s"] is None and row["position_stale_flag"] is False for row in rows)
    metrics.update({"observation_count": len(rows), "evidence_count": len(evidence), "span_s": end - start, "serializer_unflagged_unknown_age_count": unflagged_unknown_age, "settings": dict(settings)})
    limitations = list(limitations)
    if unflagged_unknown_age:
        limitations.append("Serializer did not flag some positions stale; actual position and other field ages remain unknown, not zero.")
    return {
        "event_id": "air-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20],
        "domain": "aircraft", "detector_id": "aircraft." + detector,
        "detector_version": DETECTOR_VERSION, "entity_id": entity, "region": region,
        "start": start, "end": end, "priority": priority, "summary": summary,
        "metrics": metrics, "evidence_ids": evidence, "raw_refs": raw_refs,
        "limitations": list(_COMMON_LIMITS) + list(limitations),
        "review_status": "unreviewed", "hypothesis_status": "not_tested",
    }


def _jumps(rows, settings):
    groups, current = [], []
    for index, (a, b) in enumerate(zip(rows, rows[1:])):
        if not (_usable(a, settings) and _usable(b, settings) and _adjacent(a, b, settings)):
            if current:
                groups.append(current)
                current = []
            continue
        distance = _distance(a, b)
        speed = distance / (b["timestamp"] - a["timestamp"])
        if distance >= settings["jump_min_distance_m"] and speed > settings["jump_speed_mps"]:
            current.append((index, a, b, distance, speed))
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    events = []
    for pairs in groups:
        points = [pairs[0][1]] + [pair[2] for pair in pairs]
        switches = sum(a["position_source"] != b["position_source"] for _, a, b, _, _ in pairs)
        provider_switches = sum(a["source_id"] != b["source_id"] for _, a, b, _, _ in pairs)
        age_unknown = sum(row["position_age_s"] is None for row in points)
        source_unknown = any(row["position_source"] == "unknown" or row["source_id"] == "unknown" for row in points)
        limits = ["Coordinates imply a discontinuity; they are not independently verified aircraft motion.", "Stale/invalid positions and gaps outside the configured pair interval are excluded; unknown speed-field age remains unresolved."]
        if switches or provider_switches:
            limits.append("The event includes a position-source or publisher change; disagreement/association is an alternative to motion.")
        if age_unknown:
            limits.append("Some position ages are unknown; freshness has not been established for those observations.")
        if source_unknown:
            limits.append("Some position-source or publisher identities are unknown.")
        events.append(_event("coordinate_jump", points, 45 if switches or provider_switches or age_unknown or source_unknown else 70,
                             "Consecutive reported coordinates imply speeds above the configured screening threshold.",
                             {"pair_count": len(pairs), "max_implied_speed_mps": max(pair[4] for pair in pairs), "max_displacement_m": max(pair[3] for pair in pairs), "source_switch_count": switches, "publisher_switch_count": provider_switches, "unknown_position_age_count": age_unknown, "stale_position_count": 0}, limits, settings))
    return events


def _runs(rows, settings, predicate, anchor_test=None):
    runs, current = [], []
    for row in rows:
        if not predicate(row):
            if current:
                runs.append(current)
                current = []
            continue
        linked = not current or (_adjacent(current[-1], row, settings) and _same_source(current[-1], row) and (anchor_test is None or anchor_test(current[0], row)))
        if current and not linked:
            runs.append(current)
            current = []
        current.append(row)
    if current:
        runs.append(current)
    return runs


def _persistent(rows, settings):
    events = []
    frozen = _runs(rows, settings, lambda r: _moving_fields(r, settings) and r["groundspeed_mps"] >= settings["frozen_min_speed_mps"], lambda a, b: _distance(a, b) <= settings["frozen_radius_m"])
    for points in frozen:
        if len(points) < settings["frozen_min_points"] or points[-1]["timestamp"] - points[0]["timestamp"] < settings["frozen_min_duration_s"]:
            continue
        events.append(_event("frozen_position", points, 60,
                             "Repeated reported positions remain in a small radius while reported speed indicates movement.",
                             {"max_radius_from_first_m": max(_distance(points[0], row) for row in points), "median_reported_speed_mps": statistics.median(row["groundspeed_mps"] for row in points)},
                             ["Distinct fresh position timestamps do not prove the speed field was refreshed.", "Coordinate quantization, retained fields, source processing and aircraft equipment errors are alternative explanations.", "Span describes discrete samples with bounded gaps, not continuous sensor coverage."], settings))
    slow = _runs(rows, settings, lambda r: _moving_fields(r, settings) and r["altitude_m"] is not None and r["altitude_m"] >= settings["low_speed_min_altitude_m"] and r["groundspeed_mps"] <= settings["low_speed_max_mps"])
    for points in slow:
        if len(points) < settings["low_speed_min_points"] or points[-1]["timestamp"] - points[0]["timestamp"] < settings["low_speed_min_duration_s"]:
            continue
        events.append(_event("low_speed_aloft", points, 40,
                             "Persistently low reported ground speed appears alongside high reported altitude.",
                             {"median_reported_speed_mps": statistics.median(row["groundspeed_mps"] for row in points), "minimum_reported_altitude_m": min(row["altitude_m"] for row in points)},
                             ["Airspeed, aircraft class, wind and field-acquisition times are unavailable; slow flight or a slow platform may be ordinary.", "Altitude/speed may be asynchronously retained; this screen does not establish a navigation failure.", "Span describes discrete samples with bounded gaps, not continuous sensor coverage."], settings))
    return events


def _baseline_outliers(rows, baseline, settings):
    classified = {}
    for row in rows:
        if not _moving_fields(row, settings) or row["altitude_m"] is None or row["altitude_type"] not in ("barometric", "geometric"):
            continue
        controls = [control for control in baseline if _moving_fields(control, settings) and _same_source(control, row) and control["altitude_type"] == row["altitude_type"] and control["altitude_m"] is not None and abs(control["altitude_m"] - row["altitude_m"]) <= settings["baseline_altitude_tolerance_m"]]
        days = len({math.floor(control["timestamp"] / 86400) for control in controls})
        if len(controls) < settings["baseline_min_samples"] or days < settings["baseline_min_days"]:
            continue
        median = statistics.median(control["groundspeed_mps"] for control in controls)
        mad = statistics.median(abs(control["groundspeed_mps"] - median) for control in controls)
        threshold = max(settings["baseline_min_deviation_mps"], settings["baseline_mad_multiplier"] * 1.4826 * mad)
        deviation = abs(row["groundspeed_mps"] - median)
        if deviation > threshold:
            classified[row["timestamp"]] = {"controls": controls, "days": days, "median": median, "mad": mad, "threshold": threshold, "deviation": deviation}
    events = []
    for points in _runs(rows, settings, lambda r: r["timestamp"] in classified):
        matches = [classified[row["timestamp"]] for row in points]
        controls = {control["timestamp"]: control for match in matches for control in match["controls"]}
        events.append(_event("baseline_speed_outlier", points, 50,
                             "Reported speed differs from an eligible earlier same-aircraft regional baseline.",
                             {"baseline_samples_min": min(len(match["controls"]) for match in matches), "baseline_distinct_days_min": min(match["days"] for match in matches), "baseline_unique_observations": len(controls), "baseline_median_speed_mps_min": min(match["median"] for match in matches), "baseline_median_speed_mps_max": max(match["median"] for match in matches), "max_absolute_deviation_mps": max(match["deviation"] for match in matches), "deviation_threshold_mps_min": min(match["threshold"] for match in matches), "baseline_mad_mps_min": min(match["mad"] for match in matches)},
                             ["Baseline matches entity, region, publisher, position method and altitude tolerance; route, flight phase, weather and equipment comparability remain unverified.", "Median/MAD thresholds and minimum samples/days are exploratory, not statistical significance or causal probabilities.", "Only earlier records are used; missing eligible controls produce no baseline candidate, not evidence of normality."], settings, controls.values()))
    return events


def screen_aircraft(records, baseline_records, config, window_start, window_end):
    """Return grouped review candidates without changing source records.

    Event endpoints are Unix seconds and inclusive. Invalid/ambiguous observations
    break adjacency. Persistent candidates require distinct times, fresh known
    ages or explicit clear position-stale flags, and one known publisher/method.
    A clear serializer flag does not supply an age. Jump candidates keep
    source-switch disagreements explicitly flagged and assign them lower priority.
    Historical evidence IDs are included when a baseline contributes to a result.
    An empty list means no candidate passed these screens, not a healthy airspace.
    """
    start, end = _number(window_start), _number(window_end)
    if start is None or end is None or end < start:
        raise ValueError("aircraft window must contain finite ordered Unix seconds")
    settings = _settings(config)
    cutoff = start - settings["baseline_lookback_days"] * 86400
    # Filter time before normalization so out-of-window or future records cannot
    # alter duplicate handling or contaminate the baseline's statistics.
    def in_interval(record, low, high, include_end):
        timestamp = _number(record.get("timestamp")) if isinstance(record, dict) else None
        return timestamp is not None and low <= timestamp and (timestamp <= high if include_end else timestamp < high)
    groups = _normalize([row for row in records or [] if in_interval(row, start, end, True)])
    baseline_groups = _normalize([row for row in baseline_records or [] if in_interval(row, cutoff, start, False)])
    all_event_ids = {item for rows in groups.values() for row in rows for item in row["evidence_ids"] if start <= row["timestamp"] <= end}
    events = []
    for key, all_rows in sorted(groups.items()):
        rows = [row for row in all_rows if start <= row["timestamp"] <= end]
        baseline = [row for row in baseline_groups.get(key, []) if cutoff <= row["timestamp"] < start and not all_event_ids.intersection(row["evidence_ids"])]
        events.extend(_jumps(rows, settings))
        events.extend(_persistent(rows, settings))
        events.extend(_baseline_outliers(rows, baseline, settings))
    return sorted(events, key=lambda event: (-event["priority"], event["start"], event["entity_id"], event["detector_id"], event["event_id"]))
