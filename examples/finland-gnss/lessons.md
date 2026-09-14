# Lessons from the Finland GEV case

These lessons were derived from the **13–14 September 2026** investigation. Historical numbers are case evidence, not current alerts or universal detector thresholds. “Performed” below identifies work actually done; “future rule” identifies the reusable improvement. The phase IDs map to the repository workflow.

## P01–P03: Connection success is not anomaly discovery

**Performed:** GEV's aircraft, military and satellite feeds were queried, but the first shortlist's Gulf, ICEYE and Finland assessments came from dated external reporting. The user identified the mismatch, and the assistant acknowledged it.

**Future rule:** For each proposed lead, state the discovery source and comparison:

- GEV-observed deviation with a valid comparator;
- externally reported lead awaiting GEV examination;
- coverage or data-quality problem;
- ordinary activity whose significance is still unknown.

Do not let a successful feed probe imply that its results substantiate the accompanying narrative. A snapshot is not a trend. If no candidate can be demonstrated, say so and preserve the limitation.

The initial satellite lead concerned orbital-plane alignment. No independent orbital history, conjunction or maneuver calculation was performed in this case. A future satellite branch must validate element epochs, propagation, catalog identity, observation uncertainty and maneuver alternatives before using similar language.

## P02 and P05: Treat access failures as evidence about access

**Performed:** Oversized connector limits failed at 500 and worked at 100. Sandbox network access failed before an authorized retry. Some web-tool errors occurred before a provider response. OpenSky exact-time requests returned 404; direct Airplanes.live files returned 403; its normal viewer later worked.

**Future rule:** Preserve the stage of failure, exact request, time, status and response body:

| Result | Permitted inference |
|---|---|
| Schema/limit rejection | The request violated the tool contract; retry the documented form. |
| Sandbox/DNS/proxy failure | The provider result is unknown. |
| HTTP 401/403 | This access route was unavailable under the attempted authorization. |
| HTTP 404 | The requested resource was not returned; coverage/retention/selection remains uncertain. |
| HTTP 200 with no observations | The query reached an endpoint but supplied no usable measurements. |
| Working public viewer after API denial | Some evidence is available, with viewer-specific limits. |

Do not retry by bypassing an access restriction. Use documented routes or the normal public interface, and stop at actual authorization boundaries. Keep authentication mechanisms separate from data coverage; never package tokens, cookies or account details.

Today's trace path and historical archive path can differ. In the inspected tar1090 implementation, the current trace route remains in use until one hour after UTC midnight. A same-day historical 404 is not proof of absent traffic. A `time=0` track is not an arbitrary earlier flight.

## P03–P06: Preserve the several meanings of “time”

**Performed:** Publication dates differed from event dates; a September 12 trace base produced September 13 observations; current flight labels differed from historical labels; a fresh snapshot included differently aged positions.

**Future rule:** Retain, where available:

1. Event/sample time and timezone.
2. Field acquisition or age.
3. Provider state/snapshot time.
4. Retrieval time.
5. Publication/update date.
6. Original archive version and later refreshed version.

Resolve each before comparing providers or asserting simultaneous onset. If a value's age is unknown, keep that unknown explicit. Never turn a current source wrapper into a current measurement for every contained field.

The April Traficom assessment supported regional plausibility, not September event attribution. The September 11 GPS status file constrained certain earlier outages, not uninterrupted health across all of September 13.

## P04–P07: Count only the population the data actually represents

**Performed:** A 250-nautical-mile fallback yielded 17 in-box reports, including fixed/ground transmitters. The original six histories contained 23,712 points, only 8,257 qualifying airborne regional points. The extension contained 20 identifiers and 73,310 full-history points, not 22 aircraft or a regional traffic census.

**Future rule:** Publish a count ladder: retrieved records → unique identifiers → airborne regional coverage → event-window coverage → explicit usable quality → eligible comparisons. Preserve unobservable/unclassifiable categories.

Refreshed histories replace older versions for one designated analysis total while both versions remain archived. High-frequency rows are serially dependent samples, not independent aircraft or incidents. A convenience sample supports case investigation and sensitivity checks, not prevalence, significance tests or numerical causal probabilities.

Geographic selection itself can be biased when the suspected failure displaces reported coordinates outside the query box. Future representative sampling should include route/receiver-based eligibility and documented coverage, rather than only current reported positions.

## P06: A processed state is not a synchronous sensor packet

**Performed:** Pinned readsb serialization showed state reconstruction and separate field-validity checks. The cargo trace changed velocity before changing position source. Missing detail objects were not filled forward.

**Future rule:** Source labels usually characterize a specific position/state product, not the origin or freshness of every field. Preserve the distinction between explicit zero, absent and null, and do not invent measurement times.

A TAS–ground-speed discrepancy may flag inconsistency. It does not itself measure wind or prove physical movement when the fields may be asynchronously retained. Derived heading, wind, temperature and database identity are not additional independent sensors.

Version pinning improves interpretation but does not prove a provider's exact build, configuration or local patches. Reading decoder code is not replaying original radio messages. If exact-version internals cannot be retrieved, label current-version reasoning provisional.

## P06–P08: Separate positional branches before interpreting motion

**Performed:** The first 316 km cargo jump coincided with an MLAT→ADS-B change. All nine extreme ATR jumps involved MLAT. A later impossible MLAT-only cargo jump showed that even the alternative branch was unreliable.

**Future rule:** Show source-specific segments, preserve gaps, and never connect discrepant sources as a verified flight leg. Calculate same-source behavior as well as cross-source discontinuities.

MLAT is a different positioning method, but its label alone is not ground truth. The inspected implementation uses reference ADS-B aircraft to calibrate receiver clocks. Independent validation requires receiver geometry, clock/solver quality, residuals and shared-dependency checks.

Exclude MLAT-tagged quality zero from aircraft-broadcast GNSS loss counts without claiming an unverified internal default explains every zero.

## P07 and P11: Replace memorable descriptions with measured distributions

**Performed:** “9–70 knots” was too narrow for the cargo cluster: its median was 66.15 knots, but the full range was 5–900. A roughly two-minute recurrent pattern had unstable subwindow fits.

**Future rule:** Report the number of points, duration/span, median/range, units, sample restrictions and exceptions. Keep geometric fitting exploratory when performed after inspection and supported by only a few cycles. Do not turn a period estimate into a transmitter fingerprint.

Apparently good NIC values can coexist with false-looking positions; NIC zero denotes a category/unknown limitation, not a measured error radius or confirmed jammer. Compare explicit deterioration from preceding good observations and independent context, rather than trusting a single flag either way.

## P08: A published map needs functional and content verification

**Performed:** Case schema validation, preservation of three existing maps, seven-source/four-pin restoration, a 158-point chart toggle, browser inspection and exact served-byte checks all occurred. Publication exposed a missing parent folder; UI selection/filter assumptions also needed correction.

**Future rule:** Prepare the case and report before requesting the final access needed to publish. Request only the actual missing directory/network scope, including a required parent folder. Preserve an existing index before updating it.

Verify title, selected evidence, source links, content type, map focus, filtering, toggles and restored overview. A successful file write or HTTP 200 does not prove the user sees the correct artifact; a server can return an application shell instead of the requested report. A cleared search field does not prove all evidence returned.

Label coordinates as reported observations and explain source disagreements in the UI. Do not turn the attractive map into stronger evidence than its underlying records.

## P09–P10: Test narrow mechanisms and state what each test can decide

**Performed:** Local tests addressed stale-only, immediate-switch-only, isolated-outlier-only, speed-label-only and wholly frozen-state explanations. They left 59 anomalous cargo points under a combined screen.

**Future rule:** For every hypothesis record its prediction, needed evidence, comparison, exact test, weakening outcome, observed result and residual alternatives. Distinguish “a narrow explanation weakened” from “the preferred cause confirmed.”

Keep controls and alternative causes realistic. Raw-message replay needs original odd/even CPR payloads, velocity/status frames, reception times, receiver identity and decoding/CRC diagnostics. Reconstructing “raw” frames from decoded coordinates would be circular and was not done.

External interference and processing artifacts may coexist. Filters cannot assume they are mutually exclusive.

## P10–P11: Sensitivity can legitimately downgrade a headline result

**Performed:** The 1.363-second ATR pair survived stale filtering but disappeared with a 30-second source-transition buffer. The within-aircraft OH-ATN contrast survived 2 km/equal-altitude/5° matching; a 1 km rule had no comparator.

**Future rule:** Present threshold sensitivity and revise the headline when a claim depends on it. Do not select only the filter that preserves the preferred narrative.

Source-switch exclusion can also remove true GNSS deterioration because degradation may trigger MLAT use. A disappearing result therefore weakens precise timing inference, not necessarily every external-interference explanation. Similarly, a 120-second buffer that removes an entire event is uninformative.

Specify whether a reported duration means continuous observations, summed eligible time or first-to-last span. The retained cargo span of 283.63 seconds was not continuous coverage.

## P10: Empty controls are an evidence gap, not a negative experiment

**Performed:** Fourteen new histories and two refreshes supplied no closely matched non-ATR controls and no additional regional cargo-window control. One non-ATR's low-altitude NIC-6 observation was not a joint-zero case or a high-altitude comparator.

**Future rule:** Define control eligibility before looking at new outcomes, including time, reported distance, altitude, phase, source and usable quality. Record equipment configuration where available; common aircraft type does not establish identical avionics.

Document coverage-driven sampling amendments before the amended retrieval. The extension was prospectively specified relative to new histories, but its thresholds followed discovery inspection; call it exploratory sensitivity analysis, not preregistration of unseen evidence.

## P10–P11: Separate publisher agreement from independent measurement

**Performed:** Two historical Airplanes.live ADS-B samples matched GEV after rounding; an MLAT sample showed the other branch. API files were unavailable, and viewer values were transcribed rather than extracted as a raw independent dataset.

**Future rule:** Report an independence ladder:

1. Same data copied to another display.
2. Separate publisher with unknown shared feeders/software.
3. Independently identified receivers and independent decoding.
4. Different validated surveillance/measurement method.
5. Onboard corroboration tied to the event.

State which level was actually achieved. In this case, two-publisher agreement weakened GEV-only and adsb.lol-publication-only explanations. It did not prove independent receivers, authentic aircraft-origin transmissions or spoofing.

Preserve the selected date/leg, displayed clock, integer epoch, rounding precision and field/source labels. Arithmetic replay can reproduce the comparison without authenticating a manual transcription.

## P10–P11: Follow natural and satellite-service alternatives to their relevant records

**Performed:** An initial NOAA product lacked evening coverage; a second product closed that gap. Two documented FMI queries returned no data. Three apparently open GPS interruptions were found to have closed before the events.

**Future rule:** Check event overlap, record completeness, field definitions and closure/supersession chains. Retain rolling products as captured bodies. An outdated outage listing, future scheduled maintenance or cached availability page is insufficient.

Planetary Kp and local ionospheric scintillation are different measurements. Thirty-one minute-updated estimates are not 31 independent GNSS tests. Low planetary values weaken a major storm explanation but do not exclude local effects or receiver/satellite geometry.

An HTTP 200 response without observations must not be described as quiet conditions. A missing archive result may reflect coverage, retention, parsing or publication, and remains bounded to the exact query.

## P11–P12: Revision and reproducibility are deliverables

**Performed:** Independent scripts rechecked arithmetic, and later findings superseded earlier claims about synchronization, access and evening weather coverage. The deep PDF was rendered, reviewed, revised and checked again. The final three deterministic outputs reproduced exactly in an isolated copy.

**Future rule:** Preserve both discovery evidence and later revisions. Maintain a correction register showing the earlier statement, new evidence, revised statement and affected artifacts. Do not leave a superseded working note as the final authoritative conclusion.

Separate:

- copy integrity: hashes, byte counts, archive checks;
- computational reproduction: fixed inputs and deterministic calculations;
- presentation verification: map/report/PDF inspection;
- source authenticity: whether observations were genuinely obtained and accurately transcribed;
- causal validity: whether the evidence distinguishes the mechanism.

Passing one does not imply the others. Offline verification must not refetch rolling sources or overwrite preserved captures. Retrieval scripts are methods, not deterministic reproduction; warn that rerunning them may change data.

Use relative portable artifact layouts, documented dependencies, test definitions, licences and clear exclusions. Sanitize private paths and credentials before redistribution. Keep manually observed evidence labelled as such.

## Closing rule for future cases

Deliver the strongest warranted conclusion even if it is narrower than the original lead. The Finland result was a persistent, better-corroborated cargo **reported-data anomaly** and robust **time-varying ATR quality**, with weakened synchronization and unresolved cause. It was not a confirmed spoofing operation, military attribution or trading opportunity.

A future case should end with completed tests, revised hypotheses, explicit missing evidence and a reproducible report. Raw radio validation, operator records, representative held-out sampling, satellite-geometry reconstruction and impact estimation remain additional work unless actually performed and recorded.

