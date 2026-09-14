"""Bounded local GEV acquisition. No credentials or direct provider fallback."""

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime

from .normalize import normalize_snapshot, normalize_trace
from .satellites import normalize_satellites
from .storage import Store

ROOT = Path(__file__).resolve().parents[1]


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def load_config(path=None):
    data = read_json(ROOT / "config/pilot.json")
    if path:
        data.update(read_json(path))
    for key in ("aircraft_interval_s", "trace_interval_s", "satellite_interval_s"):
        if not isinstance(data.get(key), (float, int)) or data[key] < 60:
            raise ValueError(key + " must be at least 60 seconds")
    if data["satellite_interval_s"] < 7200:
        raise ValueError("Satellite polling must be at least two hours apart")
    for key in ("max_analysis_records", "max_response_bytes", "max_data_bytes", "minimum_free_bytes"):
        if type(data.get(key)) is not int or data[key] <= 0:
            raise ValueError(key + " must be a positive integer")
    if not 0 <= data["traces_per_region"] <= 10:
        raise ValueError("traces_per_region must be between 0 and 10")
    if not 1 <= len(data["regions"]) <= 10:
        raise ValueError("Use 1–10 bounded regions")
    for region in data["regions"]:
        w, s, e, n = region["bbox"]
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ValueError("Invalid region bounds")
        if not (-90 <= region["lat"] <= 90 and -180 <= region["lon"] <= 180):
            raise ValueError("Invalid regional anchor")
    import re
    if not all(re.fullmatch(r"[a-zA-Z0-9-]+", g) for g in data["satellite_groups"]):
        raise ValueError("Invalid satellite group")
    return data


def config_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def local_base(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("GEV collector accepts a local loopback URL only")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("GEV base must contain only scheme, local host and port")
    return url.rstrip("/")


def discover_gev(config):
    if config.get("gev_base_url"):
        return local_base(config["gev_base_url"])
    command = config.get("pterm_command")
    if not command:
        executable = shutil.which("pterm")
        if not executable:
            settings = read_json(Path.home() / ".pinokio/config.json", {})
            home = settings.get("home")
            candidates = [Path(home) / "bin/npm/bin/pterm", Path(home) / "bin/pterm"] if home else []
            executable = next((str(p) for p in candidates if p.is_file()), None)
        if not executable:
            raise RuntimeError("pterm unavailable: configure pterm_command using the installed runtime")
        command = [executable]
    env = os.environ.copy()
    if len(command) > 1:
        env["PATH"] = str(Path(command[0]).parent) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(command + ["status", config.get("gev_app", "gods-eye-view.git"), "--probe"],
                            capture_output=True, text=True, timeout=30, env=env)
    if result.returncode:
        raise RuntimeError("GEV runtime discovery failed; verify Pinokio and pterm")
    status = json.loads(result.stdout)
    if not status.get("ready") or status.get("source", {}).get("local") is False:
        raise RuntimeError("Local GEV is not ready; no traffic data retrieved")
    return local_base(status["ready_url"])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected redirect from local GEV")


def fetch(url, config):
    parsed = urllib.parse.urlsplit(url)
    local_base(urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")))
    if parsed.fragment:
        raise ValueError("GEV requests must not contain URL fragments")
    started = time.time()
    request = urllib.request.Request(url, headers={"User-Agent": "satellite-research-local/0.1", "Accept": "application/json,text/plain"})
    metadata = {"retrieved_at": started, "url": url, "request": {"method": "GET"}, "headers": {}}
    body = b""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            response = opener.open(request, timeout=config["request_timeout_s"])
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read(config["max_response_bytes"] + 1)
            metadata["http_status"] = response.code
            metadata["headers"] = {k.lower(): v for k, v in response.headers.items()
                                   if k.lower().startswith("x-") or k.lower() in {"content-type", "date", "retry-after"}}
        metadata["status"] = "available" if metadata["http_status"] == 200 else "request_failed"
        if len(body) > config["max_response_bytes"]:
            body = body[:config["max_response_bytes"]]
            metadata.update(status="truncated", error="response exceeds local byte cap; saved prefix only")
    except Exception as exc:
        metadata.update(status="request_failed", error=type(exc).__name__ + ": " + str(exc))
    metadata["duration_s"] = round(time.time()-started, 3)
    metadata["retrieved_at"] = time.time()
    return body, metadata


def directory_size(path):
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file() and not p.is_symlink())


def collect(data_dir, config, force=False):
    """One due acquisition cycle, including persisted per-source cooldowns."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    state_path = data_dir / "collector-state.json"
    state = read_json(state_path, {"sources": {}, "trace_rotation": {}})
    now = time.time()
    report = {"started_at": now, "requests": [], "status": "completed", "profile": config["profile"]}
    if directory_size(data_dir) >= config["max_data_bytes"] or shutil.disk_usage(data_dir).free < config["minimum_free_bytes"]:
        report.update(status="capacity_blocked", error="Collection paused at storage limit; existing evidence retained")
        atomic_json(data_dir / "health.json", report)
        return report
    try:
        base = discover_gev(config)
    except Exception as exc:
        report.update(status="runtime_unavailable", error=str(exc))
        atomic_json(data_dir / "health.json", report)
        return report
    version = config_hash(config)
    config_archive = data_dir / "config-history" / (version + ".json")
    if not config_archive.exists():
        atomic_json(config_archive, config)
    store = Store(data_dir)
    try:
        def due(key):
            previous = state["sources"].get(key, {})
            # --force bypasses regular cadence only, never a provider cooldown.
            return now >= previous.get("retry_after", 0) and (force or now >= previous.get("next_due", 0))

        def obtain(key, endpoint, domain, interval, parser, region=None):
            body, meta = fetch(base + endpoint, config)
            meta.update(config_sha256=version, region=region, source_key=key, parser_version="0.1.0",
                        representation="original GEV HTTP response; processed provider product, not raw radio observations")
            records, warnings = [], []
            if meta["status"] == "available":
                try:
                    records, warnings = parser(body, meta)
                    missing_time = sum(r.get("timestamp") is None for r in records)
                    records = [r for r in records if r.get("timestamp") is not None]
                    if missing_time:
                        warnings.append("missing event timestamp: %d records preserved only in original response" % missing_time)
                    if not records:
                        meta["status"] = "empty_response"
                except Exception as exc:
                    meta.update(status="parse_failed", error=str(exc))
            meta["warnings"] = warnings
            meta["normalized_count"] = len(records)
            times = [r["timestamp"] for r in records]
            meta["coverage"] = {"first_event": min(times) if times else None, "last_event": max(times) if times else None,
                                "continuous": False, "selection": "bounded region or selected entity/group; not a census"}
            capture_id = store.save_capture(key, body, meta)
            for r in records:
                r["raw_ref"] = capture_id
                r["raw_refs"] = [capture_id]
            added = store.add_observations(domain, records)
            retry = 0
            for header in ("retry-after", "x-opensky-retry-after-seconds", "x-ads-b-retry-after-seconds"):
                value = meta["headers"].get(header, 0)
                try:
                    seconds = float(value)
                    if math.isfinite(seconds):
                        retry = max(retry, seconds)
                except (ValueError, TypeError):
                    if header == "retry-after" and value:
                        try:
                            retry = max(retry, parsedate_to_datetime(str(value)).timestamp()-meta["retrieved_at"])
                        except (ValueError, TypeError, OverflowError):
                            pass
            if meta.get("http_status") in {401, 403}:
                retry = max(retry, 21600)
            state["sources"][key] = {"next_due": meta["retrieved_at"] + max(interval, retry),
                                      "retry_after": meta["retrieved_at"] + retry,
                                      "last_status": meta["status"], "last_capture": capture_id}
            report["requests"].append({"source": key, "status": meta["status"], "records": len(records),
                                       "added": added, "capture_id": capture_id, "bytes": len(body), "warnings": warnings})
            atomic_json(state_path, state)  # restart-safe after each request
            return records

        for region in config["regions"]:
            key = "aircraft:" + region["id"]
            if due(key):
                query = urllib.parse.urlencode({"lat": region["lat"], "lon": region["lon"]})
                obtain(key, "/api/opensky?" + query, "aircraft", config["aircraft_interval_s"],
                       lambda body, meta: normalize_snapshot(json.loads(body), meta["headers"], region, meta["retrieved_at"]), region["id"])

        # Select a rotating, reproducible cohort from recent actual regional observations.
        trace_key = "trace-cohort"
        if due(trace_key) and config["traces_per_region"]:
            latest = store.observations("aircraft", now-1800, time.time())
            selected = set()
            for region in config["regions"]:
                ids = sorted({r["entity_id"] for r in latest if r.get("region") == region["id"]
                              and r.get("source_id", "").endswith((":states", ":normalized"))})
                offset = state["trace_rotation"].get(region["id"], 0)
                subset = [ids[(offset+i) % len(ids)] for i in range(min(len(ids), config["traces_per_region"]))] if ids else []
                selected.update(subset)
                state["trace_rotation"][region["id"]] = offset + len(subset)
            for entity in sorted(selected):
                key = "trace:" + entity
                if due(key):
                    obtain(key, "/api/adsblol/trace?" + urllib.parse.urlencode({"hex": entity}), "aircraft", config["trace_interval_s"],
                           lambda body, meta, entity=entity: normalize_trace(json.loads(body), entity, config["regions"], meta["retrieved_at"]), "selected-cohort")
            state["sources"][trace_key] = {"next_due": time.time() + config["trace_interval_s"]}
            atomic_json(state_path, state)
        for group in config["satellite_groups"]:
            key = "satellites:" + group
            if due(key):
                obtain(key, "/api/celestrak/" + group, "satellite", config["satellite_interval_s"],
                       lambda body, meta, key=key: normalize_satellites(body.decode("utf-8"), key, meta["retrieved_at"], "pending-capture"), "orbital_catalog")
    finally:
        store.close()
    report["finished_at"] = time.time()
    report["config_sha256"] = version
    if any(r["status"] not in {"available", "empty_response"} for r in report["requests"]):
        report["status"] = "partial"
    atomic_json(data_dir / "health.json", report)
    return report
