"""Reproducible screening packages; these do not replace causal investigation."""

from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import html
import json
import gzip
from pathlib import Path
import subprocess
import time

from .aircraft import screen_aircraft, DEFAULTS as AIR_DEFAULTS
from .satellites import screen_satellites, DEFAULTS as SAT_DEFAULTS
from .collector import atomic_json, config_hash, read_json, ROOT
from .storage import Store


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def screen(store, config, start, end):
    baseline_start = start - config["baseline_days"]*86400
    limit = config.get("max_analysis_records", 250000)
    truncation = []
    def select(name, domain, lo, hi, field="timestamp"):
        rows = store.observations(domain, lo, hi, time_field=field, limit=limit+1)
        if len(rows) > limit:
            truncation.append(name)
        return rows[:limit]
    aircraft = select("aircraft_current", "aircraft", start, end)
    aircraft_baseline = select("aircraft_baseline", "aircraft", baseline_start, start-0.000001)
    satellites = select("satellite_current", "satellite", start, end, "snapshot_at")
    satellite_baseline = select("satellite_baseline", "satellite", baseline_start, start-0.000001, "snapshot_at")
    events = screen_aircraft(aircraft, aircraft_baseline, config["aircraft_detectors"], start, end)
    events += screen_satellites(satellites, satellite_baseline, config["satellite_detectors"], start, end)
    events.sort(key=lambda e: (-e["priority"], e["start"], e["event_id"]))
    if truncation:
        for event in events:
            event["limitations"].append("Analysis input cap reached: " + ", ".join(truncation) + "; screening is partial")
    store.save_events(events)
    reviews = {r["event_id"]: r for r in store.reviews()}
    for event in events:
        if event["event_id"] in reviews:
            review = reviews[event["event_id"]]
            event["review_status"] = review["status"]
            event["review_note"] = review.get("note")
    baseline = {"start": baseline_start, "end": start, "aircraft_records": len(aircraft_baseline),
                "satellite_records": len(satellite_baseline),
                "aircraft_days": len({utc(r["timestamp"])[:10] for r in aircraft_baseline}),
                "analysis_record_limit_per_set": limit, "truncated_input_sets": truncation,
                "status": "warming_up" if len({utc(r["timestamp"])[:10] for r in aircraft_baseline}) < AIR_DEFAULTS.get("baseline_min_days", 3) else "eligibility_checked_per_detector",
                "limitation": "Baseline sample size does not establish comparability or calibrated false-alarm rates."}
    inputs = {"aircraft": aircraft, "aircraft_baseline": aircraft_baseline, "satellites": satellites,
              "satellite_baseline": satellite_baseline, "window_start": start, "window_end": end,
              "aircraft_config": config["aircraft_detectors"], "satellite_config": config["satellite_detectors"],
              "truncated_input_sets": truncation}
    return events, baseline, aircraft, satellites, inputs


def coverage_rows(captures, config, start, end):
    rows = []
    day = datetime.fromtimestamp(start, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    while day.timestamp() <= end:
        lo, hi = max(start, day.timestamp()), min(end, (day+timedelta(days=1)).timestamp())
        for region in config["regions"]:
            key = "aircraft:" + region["id"]
            subset = [c for c in captures if c["source_id"] == key and
                      (lo <= c["retrieved_at"] < hi or (hi == end and c["retrieved_at"] == end and
                       day.timestamp() <= end < (day+timedelta(days=1)).timestamp()))]
            if lo == hi and not subset:
                continue
            good = [c for c in subset if c.get("status") == "available"]
            fresh = [c for c in good if "stale_or_unknown_feed_time" not in c.get("warnings", [])]
            rows.append({"day_utc": day.date().isoformat(), "region": region["id"], "attempts": len(subset),
                         "usable_snapshots": len(good), "fresh_snapshots": len(fresh),
                         "expected_poll_slots": max(0, int((hi-lo)/config["aircraft_interval_s"])),
                         "scope": "collection slots, not aircraft detection coverage",
                         "status": "no_saved_data" if not subset else "partial_sampling"})
        day += timedelta(days=1)
    return rows


def code_version():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unversioned"


def code_state():
    result = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True)
    return {"working_tree_dirty": bool(result.stdout.strip()) if result.returncode == 0 else None,
            "module_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((ROOT / "satresearch").glob("*.py"))}}


def build_report(data_dir, config, output_dir, start, end):
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Choose a new report directory; previous runs are immutable")
    output_dir.mkdir(parents=True)
    started = time.time()
    with Store(data_dir) as store:
        events, baseline, aircraft, satellites, inputs = screen(store, config, start, end)
        captures = store.captures(start, end)
        coverage = coverage_rows(captures, config, start, end)
        stats, reviews = store.stats(), store.reviews()
        raw_refs = sorted({ref for e in events for ref in e.get("raw_refs", [])})
        evidence_ids = sorted({eid for e in events for eid in e.get("evidence_ids", [])})
        evidence_set = set(evidence_ids)
        cited_rows = [row for rows in (aircraft, satellites, inputs["aircraft_baseline"], inputs["satellite_baseline"])
                      for row in rows if row["observation_id"] in evidence_set]
        raw_refs = sorted(set(raw_refs) | {ref for r in cited_rows for ref in r.get("raw_refs", [r["raw_ref"]])})
        all_captures = {c["capture_id"]: c for c in store.captures(None, None)}
        evidence_dir = output_dir / "evidence"
        evidence_dir.mkdir()
        evidence_register = []
        for ref in raw_refs:
            body = store.read_capture(ref)
            meta = all_captures[ref]
            dest = evidence_dir / (meta["body_sha256"] + ".bin")
            if not dest.exists():
                dest.write_bytes(body)
            evidence_register.append(dict(meta, exported_path="evidence/" + dest.name))
    detector_config = {"aircraft": dict(AIR_DEFAULTS, **config["aircraft_detectors"]),
                       "satellite": dict(SAT_DEFAULTS, **config["satellite_detectors"])}
    summary = {"schema_version": 1, "report_kind": "screening_candidates", "generated_at": time.time(),
               "window": {"start": start, "end": end, "timezone": "UTC", "bounds": "inclusive"},
               "code_commit": code_version(), "code_state": code_state(), "config_sha256": config_hash(config), "baseline": baseline,
               "input_records": {"aircraft": len(aircraft), "satellite": len(satellites)},
               "candidate_events": len(events), "detector_counts": dict(Counter(e["detector_id"] for e in events)),
               "collection_requests": len(captures), "storage": stats,
               "review_counts": dict(Counter(e.get("review_status", "unreviewed") for e in events)),
               "screening_elapsed_s": round(time.time()-started, 3),
               "calibration": "Not calibrated. Synthetic tests and data replay do not measure field precision or recall.",
               "source_attribution": ["OpenSky Network via GEV", "adsb.lol (ODbL) via GEV", "CelesTrak via GEV"]}
    files = {"summary.json": summary, "events.json": events, "coverage.json": coverage,
             "captures.json": captures, "baseline.json": baseline, "detector-config.json": detector_config,
             "config.json": config, "observations.json": cited_rows, "evidence-register.json": evidence_register,
             "reviews.json": reviews}
    for name, content in files.items():
        atomic_json(output_dir / name, content)
    _replay_package(output_dir, inputs, events)
    lines = ["# Weekly traffic screening", "", "**Screening candidates for investigation; causes and operational significance are not established.**", "",
             "Window: %s through %s (UTC)." % (utc(start), utc(end)), "",
             "%s aircraft observations, %s satellite catalog records and %s grouped candidates." % (len(aircraft), len(satellites), len(events)), "",
             "Historical baseline: **%s**. %s prior aircraft days; %s prior aircraft records and %s prior satellite records." %
             (baseline["status"], baseline["aircraft_days"], baseline["aircraft_records"], baseline["satellite_records"]), "",
             "Thresholds are provisional. A candidate is an unusual data pattern, not a confirmed maneuver, interference source, military operation or trade impact.", "",
             "Analysis cap: %s records per input set; capped sets: %s. These are deterministic bounded selections, not a random global sample." %
             (baseline["analysis_record_limit_per_set"], ", ".join(baseline["truncated_input_sets"]) or "none"), "",
             "## Daily acquisition coverage", "", "Saved snapshots do not establish continuous observation. A zero below means no saved data, not no traffic. Expected slots include time before installation and while the Mac or GEV was unavailable.", "",
             "| UTC date | Region | Attempts | Fresh snapshots | Expected slots |", "|---|---|---:|---:|---:|"]
    lines += ["| {day_utc} | {region} | {attempts} | {fresh_snapshots} | {expected_poll_slots} |".format(**r) for r in coverage]
    lines += ["", "Trace acquisition samples a rotating cohort. Full selected traces can include positions outside the watched regions. Five-minute snapshots exceed the 120-second default continuity limit: jump and persistence checks depend on usable dense traces. Satellite collection samples named catalog groups every six hours; these are fitted elements, not continuous position observations.", "", "## Candidate review queue", ""]
    if not events:
        lines += ["No candidate met the enabled rules in the available records. Missing coverage and an immature baseline prevent interpreting this as normal global traffic.", ""]
    for index, event in enumerate(events, 1):
        lines += ["### %s. %s" % (index, event["summary"]), "",
                  "ID: `%s` · %s · %s · review priority %s/100 (not probability)" % (event["event_id"], event["entity_id"], event["region"], event["priority"]), "",
                  "%s — %s; %s." % (utc(event["start"]), utc(event["end"]), event.get("review_status", "unreviewed")), "",
                  "Metrics: `" + json.dumps(event["metrics"], sort_keys=True) + "`", "",
                  "Limitations: " + "; ".join(event.get("limitations", [])), ""]
    lines += ["## Next investigation", "", "Select a candidate with usable event-time evidence and execute the repository's P04–P12 hypothesis workflow. Prioritize corroboration and ordinary explanations. Review decisions are retained as analyst labels; no classification here establishes a physical cause.", "",
              "## Reproduction and evidence", "", "[Structured results](events.json), [acquisition register](captures.json), [detector settings](detector-config.json), [evidence register](evidence-register.json), [integrity manifest](manifest.json).", "",
              "Code commit: `%s`. Config SHA-256: `%s`. Source credits: OpenSky Network, adsb.lol (ODbL), CelesTrak, through GEV. Original GEV responses are processed products, not original radio messages.", ""]
    lines[-2] = lines[-2] % (summary["code_commit"], summary["config_sha256"])
    (output_dir / "Report.md").write_text("\n".join(lines))
    _html_report(output_dir, summary, events, coverage)
    manifest = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            manifest.append({"path": str(path.relative_to(output_dir)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    atomic_json(output_dir / "manifest.json", {"files": manifest, "scope": "file integrity, not source authenticity or scientific validation"})
    return summary


def _replay_package(output_dir, inputs, events):
    """Freeze exact screening inputs and executable detector versions."""
    folder = output_dir / "replay"
    folder.mkdir()
    (folder / "inputs.json.gz").write_bytes(gzip.compress(json.dumps(inputs, sort_keys=True, allow_nan=False).encode(), mtime=0))
    for name in ("aircraft.py", "satellites.py"):
        (folder / name).write_bytes((ROOT / "satresearch" / name).read_bytes())
    (folder / "replay.py").write_text('''"""Reproduce candidate calculations, not raw-source normalization or causal tests."""
from pathlib import Path
import gzip, json, sys
from aircraft import screen_aircraft
from satellites import screen_satellites
p=Path(__file__).resolve().parent
d=json.loads(gzip.decompress((p/'inputs.json.gz').read_bytes()))
actual=screen_aircraft(d['aircraft'],d['aircraft_baseline'],d['aircraft_config'],d['window_start'],d['window_end'])
actual+=screen_satellites(d['satellites'],d['satellite_baseline'],d['satellite_config'],d['window_start'],d['window_end'])
if d['truncated_input_sets']:
 for e in actual:e['limitations'].append('Analysis input cap reached: '+', '.join(d['truncated_input_sets'])+'; screening is partial')
expected=json.loads((p.parent/'events.json').read_text())
def canonical(rows):
 return sorted([{k:v for k,v in e.items() if k not in {'review_status','review_note'}} for e in rows],key=lambda e:e['event_id'])
ok=canonical(actual)==canonical(expected)
print(json.dumps({'passed':ok,'events':len(actual),'scope':'Exact saved detector inputs and code; not source authenticity or cause'}))
sys.exit(0 if ok else 1)
''')


def _html_report(output_dir, summary, events, coverage):
    cards = []
    for e in events:
        cards.append('<article data-domain="%s"><span class="tag">%s · priority %s</span><h2>%s</h2><p>%s · %s</p><p>%s</p><details><summary>Measurements and evidence</summary><pre>%s</pre><p>Event ID: %s</p></details></article>' %
                     (html.escape(e["domain"]), html.escape(e["domain"]), e["priority"], html.escape(e["summary"]), html.escape(e["entity_id"]), html.escape(e["region"]),
                      html.escape("; ".join(e.get("limitations", []))), html.escape(json.dumps(e["metrics"], indent=2)), html.escape(e["event_id"])))
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Traffic research screening</title>
<style>body{margin:0;background:#101922;color:#e4edf3;font:16px/1.6 system-ui}main{max-width:1000px;margin:auto;padding:38px 24px}h1{font-size:40px;margin:0}h2{font-size:22px}.lead{color:#9dc7d3}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px}.stat,article{background:#1b2b38;border:1px solid #334855;border-radius:10px;padding:20px;margin:14px 0}.stat b{display:block;font-size:32px}.tag{color:#f0ce86;font-size:13px}input,select{font:inherit;padding:10px;background:#243847;color:white;border:1px solid #577284;border-radius:5px}a{color:#8bd8ed}pre{white-space:pre-wrap;overflow-wrap:anywhere}footer{color:#a2b6c3}</style>
<main><p class="lead">SATELLITE RESEARCH · LOCAL SCREENING</p><h1>Traffic research review</h1><p>Measured patterns worth checking. Causes and operational significance remain untested.</p>
<div class="grid"><div class="stat"><b>%(air)s</b>Aircraft observations</div><div class="stat"><b>%(sat)s</b>Catalog records</div><div class="stat"><b>%(events)s</b>Candidate events</div></div>
<p>Baseline: <strong>%(baseline)s</strong>. These detectors are provisional and have no measured field false-alarm rate.</p>
<p><a href="Report.md">Full report and daily coverage</a> · <a href="events.json">Structured candidates</a> · <a href="manifest.json">Evidence manifest</a></p>
<label>Search <input id="search" placeholder="Object, region or pattern"></label> <label>Domain <select id="domain"><option value="">All</option value="aircraft">Aircraft</option><option value="satellite">Satellites</option></select></label><section id="events">%(cards)s</section>
<footer>Ask the research assistant to review an event by its ID. Confirmed data anomaly, explained, needs more data and dismissed are saved review judgments, not proof of a physical cause. Sources: OpenSky Network, adsb.lol (ODbL), CelesTrak via GEV.</footer></main>
<script>function filter(){let q=document.querySelector('#search').value.toLowerCase(),d=document.querySelector('#domain').value;document.querySelectorAll('article').forEach(e=>{e.hidden=!(e.textContent.toLowerCase().includes(q)&&(!d||e.dataset.domain===d))})}document.querySelector('#search').addEventListener('input',filter);document.querySelector('#domain').addEventListener('change',filter);</script></html>'''
    (output_dir / "report.html").write_text(page % {"air": summary["input_records"]["aircraft"], "sat": summary["input_records"]["satellite"], "events": len(events),
                                                  "baseline": html.escape(summary["baseline"]["status"]), "cards": "".join(cards) or "<p>No candidates in the available sample. See coverage gaps in the full report.</p>"})
