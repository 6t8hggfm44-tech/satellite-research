# Source access and evidence preservation

Apply this playbook across P01–P12. It defines reproducible, permission-aware source access without assuming a particular model, connector version, operating system or local installation.

## Discovery and access order

At **P01 scope**, identify the required observations, event interval, permitted sources and whether any action would create external state. At **P02 GEV**, discover the current integration's available sources and callable capabilities before inventing endpoints or using external substitutes. Read source descriptions, schema, query semantics, limits, timestamps and provenance. Recheck after capability/version changes.

Prefer an existing purpose-built connector or documented API. The originating session observed a connector result limit of **100**; that is a recorded implementation detail, **not a universal GEV or provider limit**. Discover present pagination/caps and record truncation. Never treat a capped response as a population denominator.

When an authorized connector cannot supply required detail, use a publisher's documented public API/archive through a script, or the publisher's normal website interface. Keep access within existing authorization and platform permissions. A different transport can repair a tool limitation, but must not bypass authentication, access restrictions or security warnings. Do not create accounts, purchase access, contact people or expand permissions without applicable authorization. Read-only access and any permission request are separate events.

At **P03 triage**, reject stale or wrong-date material as event evidence even when its URL says current/latest. At **P04 case freeze**, save the planned query set, date format, sample cap and fallback policy. Amendments must preserve the earlier plan and reason for change.

## Access-result record

At **P05 archive**, record at least:

| Field | Meaning |
|---|---|
| `source_id`, `publisher`, `upstream_dependencies` | Service identity and known shared feeds/receivers/processing. |
| `request` | Public endpoint or UI route, parameters, requested UTC interval, schema/version and intended data product. Redact secrets. |
| `retrieved_at`, `publisher_time`, `event_coverage` | Three distinct time roles; unknown remains unknown. |
| `transport`, `result_type`, `http_status` | Connector/API/script/UI and the layer that returned the outcome. No invented HTTP status for a pre-network tool failure. |
| `permission_status`, `blocked_by` | Existing authorization or required/granted/denied/pending permission; distinguish policy, network, authentication and data availability. |
| `payload_ref`, `content_type`, `checksum` | Immutable evidence reference, representation and checksum when raw content exists. |
| `pagination`, `cap`, `returned_count`, `completeness` | Whether all requested results were retrieved; unknown is not complete. |
| `validation`, `limitations`, `next_action` | Parsed schema/time checks, what remains untested, and a bounded authorized next step. |

Classify failures precisely:

- **Validation error:** request rejected by the connector/tool contract. Correct parameters from documentation; no provider-data conclusion follows.
- **Network/DNS or tool-proxy failure:** no reliable publisher response was obtained. Do not relabel it 403, 404 or missing event.
- **HTTP 401/403:** publisher response indicates authentication or access refusal. Do not infer that the requested data do not exist.
- **HTTP 404:** requested resource not found. Check documented path, date/UTC rollover and publication schedule before drawing any coverage conclusion.
- **HTTP 200 with empty/no-data/error body:** transport succeeded; requested observations were not supplied. Validate the query and body separately.
- **Valid payload with missing intervals:** partial coverage. Preserve explicit null/sentinel values; never substitute zeros or normal conditions.

Save raw bodies and response metadata where available. Tool-extracted pages and screenshots must be labeled as representations, not byte-identical HTTP captures. Preserve original versions alongside normalized derivatives; do not overwrite an earlier incomplete response with a later one. Public repository examples must contain no credentials, personal metadata, private file paths or unredacted sensitive requests.

## Event-time and archive validation

At **P06 normalize**, distinguish collection time, observation time, orbit epoch, prediction window, advisory issue time and restoration time. Snapshot freshness does not imply fresh aircraft positions or a valid past-event forecast. A current-day trace path may differ from a historical path around UTC rollover; confirm publisher semantics before interpreting a missing file. [Observed tar1090 implementation](https://raw.githubusercontent.com/wiedehopf/tar1090/master/html/script.js) is a version-dependent example, not a universal path guarantee.

Validate date and unit contracts from primary documentation. FMI's [documented command interface](https://space.fmi.fi/image/www/wget_instructions.php) accepts `starttime=YYYYMMDD[HH]`, duration in minutes, a supported output format, and optional sampling in seconds/station codes. A correctly formatted query returning no data is evidence about that request, not proof that every archive lacks the observation. Where useful and permitted, test a documented alternate route or a known-covered positive control before calling a source unavailable.

For service advisories, follow references from opening notices to summary/restoration notices. Match the actual start/stop interval to the case. A current advisory can retain superseded entries; explicit closures may resolve the conflict without proving full constellation health. Use the publisher's archive convention and record any unresolved inconsistency. [NAVCEN archive instructions](https://www.navcen.uscg.gov/sites/default/files/pdf/gps/Programmatically_Accessing_Archives.pdf), [GPS outage-history product](https://www.navcen.uscg.gov/sites/default/files/gps/sof/current_sof.sof).

For natural-cause checks, inspect payload timestamps and valid intervals in [NOAA three-hour Kp](https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json), [minute-updated estimates](https://services.swpc.noaa.gov/json/planetary_k_index_1m.json), [daily station indices](https://services.swpc.noaa.gov/text/daily-geomagnetic-indices.txt), and [FMI local products](https://rwc-finland.fmi.fi/index.php/data-download/). Distinguish estimates, local measurements and forecasts. A planetary index is not a local GNSS/scintillation observation; image-only data require readable axes, units and event-time coverage before interpretation.

## Independence and test status

At **P07 quantify** and **P08 map**, carry source, time and coverage flags into calculations and displays. At **P09 hypotheses** and **P10 test**, record whether each prediction received an adequate observation. Access failure is an unperformed test, not a failed hypothesis.

At **P11 audit**, distinguish independent publisher, feed, receiver hardware, timing reference, processing algorithm and physical measurement method. Different providers may share receivers or redistribute one solution. The [examined MLAT implementation](https://github.com/adsblol/mlat-server) uses ADS-B reference positions to calibrate receiver clocks; method diversity alone does not eliminate common dependencies. Unknown provenance remains unknown.

Use `not_started`, `blocked`, `partial` and `completed` test states with specific reasons and evidence references. A completed retrieval can yield an unresolved test. A successful calculation does not supply independent physical validation. Raw-message replay, when required, needs the original messages, receiver/timing metadata and historical decoder/configuration; a map or simplified trace cannot recreate missing raw inputs.

At **P12 report**, state what was obtained, which intervals it covers, what it supports, and what access/data limitations remain. If later evidence repairs a gap, explicitly supersede the earlier limitation while preserving its original record. Do not describe a recommendation, request attempt or blocked action as a completed test.
