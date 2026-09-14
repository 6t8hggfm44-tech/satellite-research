# Aircraft and GNSS adapter

Use this adapter for passive investigation of unusual public aircraft tracks or reported navigation-quality changes. It turns a map observation into reproducible tests of the data and possible causes. It does not convert an unusual track into proof of jamming, spoofing, a mission, or intent.

## Phase contract

| Phase | Adapter requirement |
|---|---|
| P01 scope | Specify the question, UTC interval, region, civil-aircraft scope, candidate selection rule, and what would change the decision. Separate traffic behavior from navigation/reporting reliability. |
| P02 GEV | Discover the current GEV sources, capabilities, schema, bounds and freshness. Capture source identity and record ages, not just map time. |
| P03 triage | Flag source conflicts, gaps, quality changes and unusual geometry as candidates. Exclude fixed transmitters and ground records where inappropriate; record every exclusion. |
| P04 case freeze | Freeze candidate IDs, event windows, controls, metrics, threshold versions, and stopping rules before extending the sample. Keep later amendments with reasons. |
| P05 archive | Save original payloads, request parameters, retrieval time, publisher time, permissions and errors. Preserve successive versions. |
| P06 normalize | Apply the exact provider/version schema; retain original fields and missingness. Separate sources, time roles and altitude datums. |
| P07 quantify | Compute geometry only across eligible consecutive observations. Quantify coverage, sample selection and sensitivity to gaps/source changes. |
| P08 map | Show reported coordinates, source category, age, uncertainty and gaps. Do not draw a continuous physical path through unresolved conflicts. |
| P09 hypotheses | Instantiate the catalog below with case-specific predictions and evidence requirements. Allow several causes to coexist. |
| P10 test | Execute the frozen tests, record positive and negative results, and distinguish unavailable tests from negative evidence. |
| P11 audit | Check raw-message provenance, source dependence, asynchronous fields, thresholds and alternative explanations. |
| P12 report | State observations, calculations, causal inferences and unresolved alternatives separately. Link each finding to archived evidence and its limits. |

## Inputs and normalized fields

Require a candidate identifier plus its validity interval; callsigns and registrations can change and are not enough alone. Preserve provider, upstream feed, position source, decoder/build version, query geometry, archive date and any sample cap.

Retain event time, receive time if supplied, retrieval time, position age, metadata age if known, latitude/longitude, barometric/geometric altitude and units, ground speed/track, airspeed/heading, vertical rate, airborne/ground state, message counts, explicit NIC/NACp/NACv/SIL values, and stale/invalid flags. Save source and quality separately for every observation. Do not synthesize field timestamps when the source only provides a state snapshot.

For readsb traces, inspect the version-matched schema before interpreting array positions. In the previously examined revision, point time is the file base timestamp plus `row[0]`; `row[8]` is an optional details object and `row[9]` is position source. These are **documented revision semantics, not universal defaults**. The saved state can contain fields updated by different messages. A row showing ground speed beside retained true airspeed does not establish simultaneous measurements or exact fault onset. [Pinned format](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/README-json.md), [serialization](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/json_out.c), [trace retention](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/globe_index.c).

Keep absent key, null, explicit zero, stale value and rejected observation distinct. Quality zero can mean unknown; it is not a measured position error. An MLAT point's NIC value is not a new onboard ADS-B integrity observation. [Quality-category definitions](https://tc.canada.ca/en/aviation/reference-centre/advisory-circulars/advisory-circular-ac-no-500-029).

## Baselines and thresholds

Build baselines from the same aircraft across other passes, other aircraft over comparable routes/altitudes/times, unaffected periods, and receiver/ingest health. Include denominators: observable aircraft, eligible observations and coverage duration. A convenience sample is not regional prevalence; many rows from one flight are not independent trials. A current geographic query can miss aircraft whose reported coordinates were displaced outside its boundary.

Predeclare freshness, gap, matching, quality and geometric screening rules. Derive them from the question, product documentation, resolution and baseline distribution. Record units, rationale, sensitivity alternatives and version. The original case's thresholds are examples of a protocol, not reusable defaults. If selection changes after viewing results, label the extension exploratory and retain the original result.

## Hypothesis-test catalog

| ID / hypothesis | Prediction and discriminating test | Falsifier or weakening result | Main confounders / residual limit |
|---|---|---|---|
| AG01 display, aggregation or stale-state artifact | Recompute paths from archived payloads, split by source and freshness; compare map rendering against those records. | The same anomaly persists in eligible single-source observations and independently decoded raw messages. | A provider can preserve an upstream fault; transmitted false positions are still possible. |
| AG02 receiver, CPR decoder or MLAT processing fault | Check receiver-wide effects, error counters, CPR pairing/reference choices and MLAT solution health; replay identical archived messages through version-pinned independent decoders. | Several receiver paths recover identical coordinates from valid frames while independent timing/radar supports a different physical position. | CRC is consistency, not authentication. Shared receivers or reference beacons can couple apparently separate systems. |
| AG03 aircraft navigation/avionics fault | Seek existing receiver/inertial disagreements and fault records; test recurrence on the same aircraft outside the region. | Independent airframes with distinct equipment show event-matched degradation while controls recover outside the interval. | Common equipment can fail similarly; an external disruption can leave persistent receiver effects. |
| AG04 external GNSS disruption, including jamming or spoofing | Compare explicit raw no-position messages, quality changes, false-coordinate behavior, continued non-position reception and independent physical-position evidence across aircraft. | The effect disappears with corrected processing, is confined to one reception chain, or is explained by a documented onboard fault. | ADS-B alone rarely separates jamming, spoofing and avionics failure. Nominal integrity categories do not exclude false positions. |
| AG05 natural propagation or satellite-service event | Test timestamp-matched local scintillation/receiver observations, planetary/local magnetic context, satellite advisories and event-time availability/geometry. | Specific advisories close before the event, or required propagation/availability predictions fail against adequate local observations. | Quiet planetary Kp does not exclude local scintillation. Missing local observations cannot falsify this hypothesis. |
| AG06 unusual but real flight behavior | Compare independent position methods, coherent source-specific kinematics, route history and operational records. | Extreme movement occurs only between conflicting sources, stale points or interpolation gaps. | Weather, ATC, diversions, holding and incomplete routes can explain real deviations without unusual intent. |

Treat these as competing and potentially overlapping explanations, not a mandatory single winner. Vendor research supports using explicit raw no-position messages and independent reception timing as discriminators, but does not validate any particular case. [Primary ADS-B research](https://aireon.com/wp-content/uploads/2026/04/White-Paper-GNSS-Spoofing-Detection-in-Aviation-1.0-1-1.pdf), [EASA population-screening method](https://www.easa.europa.eu/en/domains/air-operations/global-navigation-satellite-system-outages-and-alterations).

## Minimum evidence for stronger claims

Raw-message replay needs original frames, receive timestamps and their time basis, receiver IDs, CRC/error-correction status, pairing/reference state, decoder version/configuration and relevant rejection counters. Keep replay inputs immutable and document differences from the historical build. A current upstream implementation does not prove what an older or patched deployment did.

An MLAT label supplies a different positioning method, not certified ground truth. Check receiver geometry, clock calibration, residuals, uncertainty, solver version and reference dependencies. The examined implementation uses known ADS-B positions for clock calibration. [MLAT implementation description](https://github.com/adsblol/mlat-server). A second website can share the same receivers, feed or algorithm; record independence at each layer.

Stop at source disagreement or broadcast degradation when raw evidence and independent physical positions are unavailable. Report the finding that survives the checks, rather than promoting the most consequential explanation.
