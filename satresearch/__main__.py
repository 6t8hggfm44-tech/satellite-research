"""Dependency-free command-line entry point for collection and review."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
import time

from .collector import collect, load_config, discover_gev, atomic_json, ROOT, read_json
from .normalize import normalize_snapshot, normalize_trace
from .satellites import normalize_satellites
from .storage import Store, REVIEW_STATUSES
from .reporting import build_report, screen


def timestamp(value):
    try:
        return float(value)
    except ValueError:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Date must include a UTC offset or Z")
        return parsed.timestamp()


class WriterLock:
    """Only one collector/replayer writes measurement data in a directory."""
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "collector.lock"
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+")
        try:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                if not self.stream.read(1):
                    self.stream.write("0")
                    self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError("Another collector owns this data directory")
        return self

    def __exit__(self, *args):
        self.stream.close()


def print_json(value):
    print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preserve GEV data, screen candidates and build review reports.")
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--config", help="Local JSON overrides; keep machine paths out of shared config")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check runtime and storage; does not collect traffic")
    collect_p = sub.add_parser("collect", help="Collect one bounded cycle")
    collect_p.add_argument("--force", action="store_true", help="Bypass regular cadence, but not provider cooldowns")
    service_p = sub.add_parser("service", help="Run the lightweight local data collector until stopped")
    service_p.add_argument("--poll-seconds", type=int, default=60)
    report_p = sub.add_parser("report", help="Screen preserved data and create a new review package")
    report_p.add_argument("--days", type=float, default=7)
    report_p.add_argument("--end", type=timestamp)
    report_p.add_argument("--output", required=True)
    sub.add_parser("status", help="Show storage, service health and review counts")
    sub.add_parser("verify", help="Verify stored evidence integrity, not scientific truth")
    review_p = sub.add_parser("review", help="Record an analyst's decision without erasing history")
    review_p.add_argument("event_id")
    review_p.add_argument("status", choices=sorted(REVIEW_STATUSES))
    review_p.add_argument("--note", required=True)
    ingest = sub.add_parser("ingest", help="Import a preserved response into an isolated replay store")
    ingest.add_argument("--kind", choices=["opensky", "trace", "tle"], required=True)
    ingest.add_argument("--input", required=True)
    ingest.add_argument("--retrieved-at", type=timestamp, required=True)
    ingest.add_argument("--entity")
    ingest.add_argument("--region", default="baltic-nordic")
    ingest.add_argument("--source", default="offline-import")
    ingest.add_argument("--headers", help="JSON file of original HTTP headers, if available")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    data_dir = Path(args.data_dir).resolve()
    if args.command == "doctor":
        result = {"python": sys.version.split()[0], "profile": config["profile"], "data_dir": str(data_dir)}
        try:
            result.update(gev_ready=True, gev_url=discover_gev(config))
        except Exception as exc:
            result.update(gev_ready=False, error=str(exc))
        with Store(data_dir) as store:
            result["storage"] = store.stats()
        print_json(result)
        return 0 if result["gev_ready"] else 2
    if args.command == "collect":
        with WriterLock(data_dir):
            result = collect(data_dir, config, args.force)
        print_json(result)
        return 0 if result["status"] == "completed" else 2
    if args.command == "service":
        if args.poll_seconds < 30:
            parser.error("service polling must be at least 30 seconds")
        running = [True]
        def stop(signum, frame):
            running[0] = False
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        with WriterLock(data_dir):
            last_scan = 0
            while running[0]:
                start = time.time()
                try:
                    result = collect(data_dir, config)
                    if start-last_scan >= 3600:
                        with Store(data_dir) as store:
                            screen(store, config, start-86400, start)
                        last_scan = start
                    atomic_json(data_dir / "service-status.json", {"pid": os.getpid(), "updated_at": time.time(),
                                "last_cycle_status": result["status"], "last_screen_at": last_scan,
                                "status": "running", "sleep_behavior": "No observations while asleep; sample on resume; gaps remain."})
                except Exception as exc:
                    atomic_json(data_dir / "service-status.json", {"pid": os.getpid(), "updated_at": time.time(),
                                "status": "error", "error": type(exc).__name__ + ": " + str(exc)})
                deadline = time.monotonic() + args.poll_seconds
                while running[0] and time.monotonic() < deadline:
                    time.sleep(min(1, max(0, deadline-time.monotonic())))
            atomic_json(data_dir / "service-status.json", {"updated_at": time.time(), "status": "stopped"})
        return 0
    if args.command == "report":
        if not 0 < args.days <= 31:
            parser.error("report days must be >0 and <=31")
        end = args.end if args.end is not None else time.time()
        summary = build_report(data_dir, config, args.output, end-args.days*86400, end)
        print_json(summary)
        return 0
    with Store(data_dir) as store:
        if args.command == "status":
            print_json({"storage": store.stats(), "collector": read_json(data_dir / "health.json", {}),
                        "service": read_json(data_dir / "service-status.json", {}), "reviews": store.reviews()})
        elif args.command == "verify":
            result = store.verify()
            print_json(result)
            return 0 if result["ok"] else 2
        elif args.command == "review":
            store.review(args.event_id, args.status, args.note)
            print_json({"event_id": args.event_id, "status": args.status, "saved": True})
        elif args.command == "ingest":
            body = Path(args.input).read_bytes()
            headers = read_json(args.headers, {}) if args.headers else {}
            meta = {"retrieved_at": args.retrieved_at, "status": "offline_import", "headers": headers,
                    "representation": "user-supplied preserved response; original provenance must be checked"}
            with WriterLock(data_dir):
                ref = store.save_capture(args.source, body, meta)
                if args.kind == "trace":
                    if not args.entity:
                        parser.error("trace import requires --entity")
                    records, warnings = normalize_trace(json.loads(body), args.entity, config["regions"], args.retrieved_at, ref)
                    domain = "aircraft"
                elif args.kind == "opensky":
                    region = next(r for r in config["regions"] if r["id"] == args.region)
                    records, warnings = normalize_snapshot(json.loads(body), headers, region, args.retrieved_at, ref)
                    domain = "aircraft"
                else:
                    records, warnings = normalize_satellites(body.decode(), args.source, args.retrieved_at, ref)
                    domain = "satellite"
                added = store.add_observations(domain, records)
                print_json({"capture_id": ref, "records": len(records), "added": added, "warnings": warnings})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print_json({"status": "error", "error": str(exc)})
        sys.exit(2)
