# Worked case chronology: Finland GNSS investigation

This is a retrospective account of work performed on **13–14 September 2026**, from the original worldwide GEV anomaly request through the final **Finland GNSS hypothesis test results**. Event observations concern **13 September 2026 UTC**. Source assessments retain their original dates; nothing here claims current conditions.

The phase IDs match the reusable workflow. Work revisited phases as evidence changed: independent audits ran alongside analysis, and an initial report was delivered before deeper hypotheses and tests were requested. This is a comprehensive register of material actions and corrections, not a UI transcript. It excludes private installation paths, account information and conversation logs.

## P01 — Establish scope and the evidence standard

**Performed**

- Interpreted the initial request as a short list of significant aerial or satellite traffic anomalies, anywhere on Earth, relevant to trade or broad military awareness.
- Set out to inspect the integrated God's Eye View (GEV) feeds and supplement them with dated public evidence. Read the GEV evidence skill and checked the available workspace.
- Treated a suspicious reported position, a navigation-quality problem, an operational consequence and an attributed military action as different claims.
- When the user selected Finland, narrowed the investigation to civilian navigation/tracking reliability there. Later requests explicitly expanded the work to deep analysis, realistic testable hypotheses, and then executing the available tests.
- Did not contact operators or other people, buy data, create accounts, schedule monitoring, transmit interference, or infer a transmitter location. These were outside the executed passive investigation.

**Material scope correction**

The first answer did **not** fulfill the strongest interpretation of “use GEV”: it presented externally researched leads after checking that GEV feeds worked. When challenged, the assistant acknowledged that it had not yet detected unusual GEV tracks or established historical comparisons. Subsequent work started from actual GEV records.

## P02 — Discover and verify GEV capabilities

**Performed**

- Queried the GEV source catalogue before selecting data sources.
- Probed aircraft, military-aircraft and active-satellite sources. Initial aircraft and military queries used `limit=500`, which the connector rejected; retried with the documented maximum `limit=100`.
- Queried a Gulf-area aircraft box, **18–32° N, 42–62° E**. The query established access, not a traffic decline or baseline.
- Audited the existing integration after the user questioned the workflow. Read the GEV setup/case references and relevant prior integration summaries; distinguished the functioning connection from the analysis that had actually been completed.
- For Finland, inspected the existing aircraft provider, fallback and trace-proxy code rather than inventing endpoints or modifying application logic.
- Used the Pinokio discovery/status workflow to locate and probe the running GEV installation. An initial sandbox network failure was retained and retried after the needed permission was granted.
- Rechecked capabilities during hypothesis testing. The later snapshot used OpenSky rather than the earlier adsb.lol fallback. Inspected the existing latest-track proxy and found its upstream time parameter fixed at `time=0`.

**Result**

GEV could provide current snapshots and aircraft histories through its existing interfaces. A current source response, a regional fallback and a historical trace were separate products with separate coverage and timing.

## P03 — Discover, date-check and triage candidate anomalies

**Performed**

The first shortlist contained three leads, with dated outside evidence:

| Initial lead | Historical source content used | What was and was not established |
|---|---|---|
| Gulf cargo corridors | An IATA release dated **31 August 2026** reported July Europe–Middle East cargo down **16.1%**, Middle East–Asia down **14.1%**, versus global growth of **3.9%**; both corridors had contracted for five months. | A trade/logistics lead from aggregate reporting. The GEV Gulf snapshot did not independently reproduce these changes. |
| Cosmos satellites and ICEYE-X36 | A **1 September 2026** published analysis described five Cosmos satellites changing orbital planes in May and remaining closely aligned with ICEYE-X36's orbit in an **August 16** assessment. The analyst said their purpose was unknown and might be unrelated to ICEYE. | An orbital-analysis lead, not a GEV-detected encounter, a demonstrated threat, or a satellite over one fixed location. |
| Finland aviation GNSS interference | Traficom's **21 April 2026** assessment described persistent aviation interference in southern and central Finland. | Dated regional context, not evidence that a September trace anomaly had already been verified. |

- Checked publication dates against event dates; did not label April, May, July or August observations as live September discoveries.
- Considered public satellite maneuver/exercise reporting while checking for ordinary or disclosed explanations. Did not calculate a new orbital maneuver, close approach, collision probability or satellite trajectory anomaly.
- The user chose Finland. Gulf and satellite leads were not carried forward as completed investigations.

Historical references: [IATA](https://www.iata.org/en/pressroom/2026-releases/08-31-air-cargo-demand-grows-july/), [orbital analysis](https://isruniversity.com/2026/09/01/issue-152/), [Traficom](https://www.traficom.fi/en/news/interference-affecting-mobile-communications-and-satellite-navigation-services-continues-finland).

## P04 — Freeze the selected case and its limits

**Performed**

- Requested a Finland/Baltic snapshot in **55–65° N, 18–32° E**; preserved the response retrieved at **22:17:06 UTC**.
- Established that GEV had used an **adsb.lol 250-nautical-mile regional fallback**: 17 matching reports from 20 fallback records. Ground reports and fixed airport transmitters were present. This was not a complete regional aircraft census.
- Selected six aircraft identifiers from that snapshot: B-6115, OH-ATE, OH-ATI, OH-ATN, EI-GBL and YL-CSN. The initial selection was exploratory, not random.
- Separated B-6115's historical cargo flight **CAO1159** from the later **CAO1192** label in the current snapshot.
- Used **59–65° N, 20–32° E** as the subsequent analysis region, distinguishing it from the broader discovery box.
- Preserved the discovered event windows for later tests: cargo **12:50–13:15 UTC** and ATR **21:45–22:15 UTC**. These windows followed discovery; they were fixed before the additional histories were inspected, not preregistered before discovery.
- Kept cargo displaced positions and ATR quality deterioration as separate events that might have different causes.

**Regional context audit**

Checked EASA's **9 September 2026** 7/30-day tables and Traficom's older assessment. Helsinki, Tallinn, Riga and Vilnius were listed as affected; Helsinki's spoofing flag was blank, while the other three had a 30-day flag. Blank did not mean disproved. The April footprint and regional attribution did not locate or attribute the September events. Ambiguous Traficom reporting populations and changing reporting practice prevented an affected-flight denominator or trend inference.

## P05 — Acquire and preserve the source records

**Performed**

- Retrieved available full histories through GEV's existing adsb.lol trace proxy. Initial connector trace queries demonstrated availability; complete saved responses supported full-history analysis.
- Preserved all six responses, provider/ODbL attribution, retrieval time, response metadata, original snapshot and original trace arrays. Retrieval was around **22:18:14–22:18:15 UTC**.
- Retained the distinction between a response wrapper, a processed trace and original radio messages. The archive contained processed readsb histories, not raw ADS-B transmissions.
- Saved working and deliverable copies and later verified byte equality and SHA-256 hashes.
- Retained differing history start/end times. Two initial histories stopped before providing regional controls; their absence was not converted into normal navigation evidence.
- Preserved later refreshed versions separately rather than replacing the discovery evidence.

**Record**

The initial archive held **23,712 full-history position rows across six identifiers**. B-6115's base timestamp was on September 12; its September 13 rows required adding offsets. Rolling trace URLs were not treated as immutable evidence.

## P06 — Normalize time, source and quality; audit the schema

**Performed**

- Interpreted absolute event time as trace base timestamp plus row offset, in UTC.
- Distinguished retrieval time, snapshot time, last-message age, last-position age, trace time and optional detail-state time.
- Checked the recorded decoder version, **readsb 3.16.15, revision 05df27d**, against pinned JSON-format, serialization and trace-retention sources.
- Preserved ADS-B versus MLAT position-source labels, explicit zero, missing key and null. Counted quality only in explicit ADS-B detail objects, without filling missing objects forward.
- Excluded MLAT-tagged NIC zero from evidence of aircraft-reported ADS-B integrity loss. A later technical audit avoided assuming that every such zero came from one specific software “default.”
- Checked row order, duplicate timestamps and exact duplicate rows; no such duplicates/backward pairs were found in the original six histories.
- Distinguished all regional positions from airborne regional positions. The deeper airborne audit counted **8,257** rows; a larger earlier regional count included ground records.
- Found that saved details reconstruct an aircraft state with independently valid/retained fields. A row is not one synchronous measurement; displayed speed, attitude and quality can have different ages.
- Recorded unsuccessful retrievals of some exact-revision internals. Current-upstream code was labelled provisional; no precise historical maximum field age was asserted.
- Audited MLAT's clock-calibration dependence on reference ADS-B aircraft. A different positioning method was not assumed to be fully independent or correct.
- Kept source-specific paths separate and did not bridge missing intervals or source changes into a verified flight route.

Technical references used historically: [pinned readsb format](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/README-json.md), [serialization](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/json_out.c), [trace retention](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/globe_index.c), [MLAT documentation](https://github.com/adsblol/mlat-server).

## P07 — Quantify observations and compare plausible baselines

**Performed**

- Screened adjacent reported positions for large implied speeds; the initial screen used 2–60-second intervals, displacement over 2 km and implied speed over 1,500 km/h. Later clearly specified screens tested different questions.
- Measured the cargo MLAT→ADS-B jump: **315.933 km in 5.81 seconds**, at 12:53:59.924→12:54:05.734. It was source disagreement, not physical motion.
- Isolated **136 ADS-B points** during **420.98 seconds** in a compact **2.992 × 1.361 km** reported footprint, interspersed with six MLAT rows.
- Corrected the speed description to **median 66.15 knots, full range 5–900**. The archive did not show uniformly 9–70 knots.
- Compared the speed/position stream with explicit TAS, IAS, heading, roll and altitude fields, while retaining the asynchronous-state caveat.
- Fitted exploratory recurrent geometry: about a two-minute timescale, with a full-window sinusoidal/drift fit near 131.9 seconds and unstable short-window periods. Did not call it a precise transmitter signature.
- Checked ordinary-turn and wind interpretations as consistency counterexamples, not as observed wind or verified aircraft dynamics.
- Found a second large source-switch jump and an impossible **MLAT-only** jump of roughly **154 km in 43.66 seconds**. This invalidated treating the entire MLAT branch as truth.
- Measured the OH-ATE/OH-ATI joint-zero quality rows **1.363 seconds** and about **163 km** apart. Initially treated them as contemporaneous concern; later sensitivity tests downgraded the timing claim.
- Found OH-ATN's within-aircraft comparison: good quality at **12:22:09.654**, joint-zero quality at **22:08:17.024**, **1.5065 km** apart, both **9,000 ft**, direction difference **3°**. This was a matched comparison, not a normal-day regional baseline.
- Noted that all nine extreme ATR jumps in the initial regional screen involved MLAT. No affected-flight percentage or count of independent incidents was inferred from point counts.

## P08 — Build, publish and verify the GEV evidence view

**Performed**

- Built a case file, selected-observation records, a written report and an interactive source-separated analysis page.
- Prepared **seven evidence sources**, **four reported-position pins** and **16 source-specific path segments**. Explained that pins represented reported coordinates, not emitter locations.
- Read and preserved the existing case index. Validated the new case schema and retained all **three pre-existing maps**.
- Prepared the artifacts before requesting the filesystem access needed to publish into GEV's installation.
- Published through the existing case-publishing workflow. The first report copy exposed a missing parent directory beyond the granted case subdirectory; obtained the required parent-folder permission and completed the copy.
- Checked served report/data content types and exact bytes, rather than accepting an HTTP 200 that could be an application fallback page.
- Opened the case in GEV and verified title, source details, selected evidence and map focus. Re-read the UI after a locator mismatch instead of assuming the interaction succeeded.
- Tested evidence filtering with OH-ATI. Two sources matched because another source mentioned the aircraft; clearing the field alone did not establish full restoration. Refresh restored all seven sources and four pins.
- Tested the report's ADS-B checkbox: all **158 ADS-B circles** hid when unchecked and returned when checked.
- Inspected the final map/report screenshots, left the regional overview visible, and checked that the saved report and evidence links opened.
- Saved a verification record covering ten served report/data files, content types and hashes.

**Delivered at this stage**

An initial GEV investigation and report establishing a position-data anomaly and sampled quality degradation, while leaving mechanism, operational impact and attribution unproven.

## P09 — Develop competing, falsifiable hypotheses

**Performed**

After the user requested deep analysis, read the deep-research and PDF guidance and commissioned independent cargo, ATR and technical-source audits alongside local integrity checks.

| ID | Hypothesis framed for testing |
|---|---|
| H1 | The cargo aircraft accepted a false onboard GNSS position, potentially through spoofing. |
| H2 | Intermittent external regional interference caused the ATR quality deterioration. |
| H3 | Provider, decoding, source association, MLAT or field-retention artifacts explain some or all observations. |
| H4 | Persistent/intermittent aircraft faults or shared avionics susceptibility explain the ATR cases. |
| H5 | Natural ionospheric effects, satellite-service limitations or geometry explain the events. |

- For each, stated supporting observations, counterarguments, discriminating evidence and a result that would weaken it.
- Defined an evidence ladder: processed-data anomaly → independently confirmed transmitted-data anomaly → onboard navigation anomaly → mechanism and impact. More screenshots did not automatically advance a case up that ladder.
- Proposed raw-message replay, independent radar/WAM or reception-timing validation, MLAT diagnostics, operator records and equipment-diverse matched controls.
- Formulated a separate trade-impact test using actual delays/diversions and controls for weather, congestion and other causes. It was **proposed, not executed**.
- Initial H5 background checks found modest planetary Kp but no evening entry from that particular endpoint; preserved that coverage gap and did not use live page placeholders as measurements.
- Produced a deeper report and evidence package before the user asked to execute tests.

## P10 — Execute bounded tests, extend coverage and pursue outside evidence

**Performed: local robustness tests**

- Recorded the local test choices before calculating the extension, while acknowledging prior inspection of the discovery sample.
- Removed stale-position flags, applied 30/60/120-second buffers around both endpoints of position-source changes, and screened extreme adjacent ADS-B coordinate jumps.
- Combined stale, 30-second transition and 600-knot geometric screens: **59 cargo points** remained, median **66.2 knots**, first-to-last span **283.63 seconds**. The span was not continuous coverage.
- A 120-second source buffer removed the whole interval; labelled this uninformative rather than a clean result.
- Derived speed only from truly adjacent non-stale ADS-B pairs, without connecting across removed records: **95 pairs**, median **68.34 knots**, median absolute difference from midpoint reported speed **6.50 knots**.
- Checked explicit metadata equality and row/detail source labels: no wholly repeated adjacent object and **zero label mismatches across 5,928 objects**. Individual fields could still be retained.
- Tightened OH-ATN matching; the 2 km/equal-altitude/5° comparison survived. A 1 km threshold had no comparator.
- Rechecked the cross-aircraft timing: stale filtering retained the 1.363-second pair, but a 30-second source-transition exclusion left **no pair within 60 seconds**. This weakened synchronized onset, without proving an artifact.

**Performed: cohort extension**

- Captured a fresh GEV snapshot around 23:44 UTC; it now used OpenSky and yielded seven in-box records from a global feed.
- Retrieved six new aircraft histories, then documented a coverage-driven amendment **before** the next retrieval: take eight remaining eligible aircraft from the original snapshot, excluding already studied aircraft and three fixed transmitters.
- Raised the new-history cap from 12 to 14 and refreshed the original two histories that had failed to supply regional controls.
- Counted the latest version per identifier: **20 aircraft identifiers, 73,310 full-history rows**, comprising the original six, 14 new identifiers and two replacement versions. Did not count refreshes as extra aircraft.
- Found only EI-HGX with additional explicit ADS-B quality in the ATR window: 25 NIC-8 rows and one NIC-6/NACp-8 row at 1,600 ft. Other candidate records were MLAT-only or lacked qualifying metadata.
- Found **zero** non-ATR matches under ±5 minutes/50 km/3,000 ft and no new regional cargo-window control. Reported inadequate comparisons, not normal controls or a null regional effect.

**Performed: independent-provider access and UI evidence**

- Consulted published OpenSky, ADS-B Exchange, adsb.fi and tar1090 routes; checked current versus historical source paths and UTC-midnight behavior.
- Preserved network/DNS failures and web-tool proxy refusals separately from actual provider HTTP replies. Retried permitted read-only retrieval after network access became available.
- Repeatedly invalid `limit=500` latest-track calls were corrected to the connector's 100-record maximum.
- Queried four exact-time historical OpenSky tracks; all returned **404**. GEV's latest-track interface returned later flights for cargo/OH-ATE and no usable event track for the others. Did not substitute later flights for the original events.
- Direct Airplanes.live trace requests returned **403**. Sparse FR24 flight metadata was an identity/timing crosscheck, not anomaly corroboration. Other web/archive attempts did not yield event-level raw records.
- Opened the normal Airplanes.live public viewer despite API failure. Selected **September 13, leg 1**, verified the earlier cargo flight rather than the later leg, and inspected the displaced cluster.
- Export/retention attempts did not produce an independent raw trace archive. Captured visible observations instead, recording source label, date, time, integer epoch, coordinates, speed and displayed supporting fields.
- Compared two ADS-B samples at **12:55:50** and **12:59:53** against nearest saved GEV rows. Coordinates and ground speed agreed at displayed precision. Also retained a divergent MLAT sample without calling it ground truth.
- Preserved the viewer-clock versus epoch difference of up to one second and the absence of an explicit simultaneous detail object at one nearest GEV point.
- Called the result **two-publisher corroboration**, not proven independence of receivers, feeds, software or aircraft-origin messages.

**Performed: H5 event-matched checks**

- Retrieved NOAA planetary data: cargo Kp **1.33** for 12:00–15:00.
- Retrieved a separate minute-updated estimate covering all **31 expected timestamps** in 21:45–22:15; decimal estimated Kp **0.33–0.67**, **0.33** at 21:53. This closed the earlier evening planetary-product gap.
- Kept planetary estimates distinct from independent local GNSS/scintillation measurements.
- Audited FMI's documented query syntax and made two valid Nurmijärvi event requests. They returned **HTTP 200 but no observation data**. Did not call this quiet local conditions or proof that every FMI archive lacked records.
- Followed apparently ongoing GPS notices through their closure records. PRN 11, PRN 3 and PRN 25 interruptions had ended June 26, July 10 and September 3 respectively.
- Distinguished the September 11 operational file and future scheduled outages from event-time constellation health. Did not simulate satellite geometry or claim every natural/service cause was excluded.

## P11 — Independently audit calculations and revise claims

**Performed**

- Recomputed key findings from preserved inputs with separate scripts rather than relying on the lead analyst's tables.
- Checked source-version interpretation, sample totals, filters, match distances, retained-point adjacency, control eligibility and the latest-version counting rule.
- Incorporated the full-range cargo-speed correction, asynchronous-field caveat, MLAT-only impossible jump and the lack of precise loop-period evidence.
- Downgraded “simultaneous failure” to sampled near-time observations; after testing, prioritized the robust same-aircraft contrast over synchronized regional onset.
- Updated older access notes after the public viewer worked; did not leave “no independent evidence” as the final finding.
- Updated older H5 notes after evening NOAA coverage and GPS closure notices arrived.
- Separated arithmetic reproducibility from source authenticity, causation and raw-message validation.
- Retained unresolved alternatives rather than assigning unsupported causal probabilities or extrapolating to regional prevalence.

**Final revision**

Cargo remained the strongest follow-up candidate. Several narrow artifact explanations and a major planetary storm were weakened. Spoofing, external regional interference, shared processing and intermittent equipment explanations remained unresolved at the causal level.

## P12 — Report, verify deliverables and preserve reproduction

**Performed**

- Delivered three successive products: the initial GEV case/report; the deeper hypothesis report; and the final executed-test report. Later qualifications supersede earlier stronger language.
- Authored the deep report in Markdown and generated a **10-page PDF**. Used bundled dependencies and fonts.
- An initial PDF rasterization failed; configured a writable local font cache, rendered successfully, inspected page contact sheets, revised/rebuilt and re-inspected the result.
- Checked page count, extracted text, link annotations and missing-glyph indicators. The deep bundle verifier checked extraction, three analysis scripts, sample totals and PDF properties.
- Built the final evidence folder with original captures, refreshed versions, explicit test plans, calculations, qualified notes, external replies/errors and manual-viewer provenance.
- Ran a credential-pattern review before packaging. Omitted broad web-search/tool-response collections from the final evidence bundle; retained relevant primary-source notes and links.
- Generated SHA-256 manifests and byte counts. Clarified that hashes establish copy integrity, not truth or independence.
- Ran the final three deterministic analyses in a disposable copy, without network refetch or mutation of preserved evidence. Their JSON outputs matched both parsed values and exact bytes.
- Recomputed viewer-to-GEV nearest matches, display-rounding checks and the numerical NOAA supplement. Explicitly did not claim independent authentication of the manual viewer transcription or automatic re-derivation of interpretive prose.
- Verified archive CRC/readability, entry count and exact archived file bytes against staged files.
- Delivered **Finland GNSS hypothesis test results** and its verified evidence bundle. Reported unresolved mechanism, unproven commercial impact and unestablished military attribution.

## Executed versus still proposed at close

| Status | Work |
|---|---|
| Executed | GEV discovery/fallback verification; preserved histories; timing/source normalization; geometry and quality analysis; local sensitivity tests; convenience-cohort extension; bounded outside-provider retrieval; two historical viewer comparisons; planetary and satellite-status checks; map/UI/PDF validation; independent arithmetic audit; isolated reproduction and archive verification. |
| Attempted but unavailable | Independent raw event archives through the queried APIs; local FMI event observations through the two documented requests; some exact-version software internals. |
| Proposed, not executed | Raw radio/CPR replay; receiver-level independence proof; validated radar/WAM or MLAT diagnostics; onboard navigation/maintenance records; equipment inventory; representative multi-day/held-out study; local scintillation or aircraft satellite-geometry reconstruction; quantitative trade-impact study. |
| Reusable additions, not retrospective claims | The repository's generalized phase chart, parameterized templates and future-case gates formalize these lessons. Applying them to other regions or satellite traffic requires new data and domain-specific tests; the Finland case did not execute an orbital anomaly investigation. |

## Source record for this reconstruction

The reconstruction used the three saved case reports; map verification; original, cargo, ATR and technical-source audits; the extension protocol and tests; independent-provider observations; natural-cause supplements; manifests; deterministic reproduction results; and a filtered review of the original task's material user requests, actions and deliverable checks. Those records remain distinguishable from this retrospective synthesis.

Artifact roles include `Report.md`, `Report.pdf`, `verification.json`, `deep-integrity.json`, `deep-cargo-metrics.json`, `local-falsification-metrics.json`, `extension-results.json`, `review-tests-audit.json`, `independent-ui-observations.json`, `natural-tests.json`, `Evidence-manifest.json` and `Reproduction-results.json`. Names describe the historical case record; they are not assertions that every original file is redistributed in this repository.

