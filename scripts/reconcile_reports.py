#!/usr/bin/env python3
"""Audit versioned report inputs. No network, causal inference or market orders."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

DOMAINS = {"energy", "weather", "gev"}


def utc(value):
    if not isinstance(value, str):
        raise ValueError("A UTC timestamp is required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("Timestamp must have explicit UTC offset")
    return parsed


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def member(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Packet members must use relative paths")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError("Packet member escapes its directory")
    if not path.is_file():
        raise ValueError("Packet member missing: " + relative)
    return path


def read_packet(path):
    path = Path(path).resolve()
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Envelope exceeds 2 MiB")
    packet = json.loads(path.read_text(encoding="utf-8"))
    if packet.get("schema_version") != 1 or packet.get("domain") not in DOMAINS:
        raise ValueError("Unsupported packet schema/domain")
    if packet.get("report_kind") != "final_hypothesis_test":
        raise ValueError("Only declared final hypothesis reports qualify")
    if not isinstance(packet.get("run_id"), str) or not packet["run_id"]:
        raise ValueError("Missing run_id")
    version = packet.get("report_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("Invalid report version")
    generated = utc(packet.get("generated_at_utc"))
    available = utc(packet.get("available_at_utc"))
    if generated > available:
        raise ValueError("Availability precedes generation")
    window = packet.get("event_window_utc", {})
    if utc(window.get("start")) >= utc(window.get("end")):
        raise ValueError("Invalid half-open event window")
    if not isinstance(packet.get("workflow_commit"), str) or not packet["workflow_commit"]:
        raise ValueError("Missing workflow version")
    for name in ("report", "manifest"):
        expected = packet.get(name + "_sha256", "")
        if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
            raise ValueError("Invalid " + name + " hash")
        target = member(path.parent, packet.get(name + "_path"))
        if digest(target) != expected:
            raise ValueError(name + " hash mismatch")
    for field in ("sources", "claims", "supersedes", "geography", "limitations"):
        if not isinstance(packet.get(field), list):
            raise ValueError(field + " must be a list")
    if not isinstance(packet.get("actual_coverage"), dict):
        raise ValueError("actual_coverage must be an object")
    for source in packet["sources"]:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise ValueError("Sources need stable IDs")
        upstream = source.get("upstream_ids", [])
        if not isinstance(upstream, list) or not all(isinstance(x, str) for x in upstream):
            raise ValueError("Invalid source ancestry")
    if not all(isinstance(key, str) for key in packet["supersedes"]):
        raise ValueError("Supersedes entries must be delivery keys")
    packet["delivery_key"] = ":".join((packet["domain"], packet["run_id"], packet["report_sha256"]))
    if packet["delivery_key"] in packet["supersedes"]:
        raise ValueError("A packet cannot supersede itself")
    packet["envelope_sha256"] = digest(path)
    return packet


def lineage(packet):
    identifiers = set()
    for source in packet["sources"]:
        identifiers.add(source["id"])
        identifiers.update(source.get("upstream_ids", []))
    return identifiers


def reconcile(paths, cutoff):
    cutoff_time = utc(cutoff)
    if not 1 <= len(paths) <= 24:
        raise ValueError("Supply 1–24 explicit envelopes")
    packets, excluded, seen = [], [], {}
    for path in paths:
        p = read_packet(path)
        key = p["delivery_key"]
        if key in seen:
            if p["envelope_sha256"] != seen[key]:
                raise ValueError("Conflicting envelopes for one delivery key")
            excluded.append({"delivery_key": key, "reason": "duplicate"})
            continue
        seen[key] = p["envelope_sha256"]
        if utc(p["available_at_utc"]) > cutoff_time:
            excluded.append({"delivery_key": key, "reason": "not_available_at_cutoff"})
        else:
            packets.append(p)
    replacements = {key for p in packets for key in p["supersedes"]}
    selected = [p for p in packets if p["delivery_key"] not in replacements]
    excluded += [{"delivery_key": p["delivery_key"], "reason": "explicitly_superseded"}
                 for p in packets if p["delivery_key"] in replacements]
    if packets and not selected:
        raise ValueError("Supersession cycle leaves no active report")
    comparisons = []
    for i, left in enumerate(selected):
        for right in selected[i + 1:]:
            if left["domain"] == right["domain"]:
                continue
            start = max(utc(left["event_window_utc"]["start"]), utc(right["event_window_utc"]["start"]))
            end = min(utc(left["event_window_utc"]["end"]), utc(right["event_window_utc"]["end"]))
            shared = sorted(lineage(left) & lineage(right))
            comparisons.append({
                "left": left["delivery_key"], "right": right["delivery_key"],
                "event_overlap_utc": {"start": start.isoformat(), "end": end.isoformat()} if start < end else None,
                "shared_source_ids": shared,
                "independence": "shared_dependencies" if shared else "not_established",
                "causal_link": "not_tested",
                "required_review": "Align geography, exposure, units, lag, controls and source vintages before testing any link."
            })
    return {
        "schema_version": 1, "kind": "reconciliation_input_audit", "cutoff_utc": cutoff,
        "selected": selected, "excluded": excluded,
        "missing_domains": sorted(DOMAINS - {p["domain"] for p in selected}),
        "comparisons": comparisons,
        "limitations": ["Hash verification checks report and manifest bytes, not every evidence member or source truth.",
                        "Declared local availability is not a verified market receipt time.",
                        "This input audit executes no causal or economic test; complete RECONCILIATION.md separately.",
                        "Multiple unsuperseded reports remain visible; no silent latest-date or matching-week selection."]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("envelopes", nargs="+")
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = reconcile(args.envelopes, args.cutoff)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"status": "completed", "kind": result["kind"],
                      "selected_reports": len(result["selected"]), "missing_domains": result["missing_domains"]}))


if __name__ == "__main__":
    main()
