# Finland GNSS hypothesis test results

> **Public worked-example copy.** This report preserves the completed historical analysis. References to an accompanying Evidence bundle describe the original local deliverable; that full archive is not included here. See [example provenance](README.md). Rolling source links may have changed since collection.

**The cargo anomaly survives the completed tests and appears in a second publisher’s historical viewer. The ATR evidence supports time-varying navigation-quality deterioration, but the earlier claim of a closely synchronized regional event is weaker after filtering. None of the tests establishes spoofing, jamming, a transmitter location, or military attribution.**

The observations concern September 13, 2026, in UTC. The cargo window is 12:50–13:15; the ATR window is 21:45–22:15. Testing used the preserved God’s Eye View (GEV) histories, 14 additional aircraft histories, two refreshed histories, a second public tracking viewer, and official space-weather and satellite-service records. The latest history for each of 20 aircraft identifiers contains **73,310 position records across their full saved histories**, not just the study region or event windows. This is an exploratory convenience sample; it is neither a count of affected aircraft nor a basis for regional prevalence.[1]

| Hypothesis | Completed test result | Revised judgment |
|---|---|---|
| **H1. The cargo aircraft’s onboard GNSS was spoofed.** | The compact reported track survives several filters. Two timestamped ADS-B points in Airplanes.live agree with GEV’s coordinates and speed after display rounding. | **The reported anomaly is better corroborated. Spoofing remains unconfirmed.** Shared receivers, shared software, and onboard faults remain possible. |
| **H2. Intermittent regional external interference caused the ATR quality losses.** | One same-aircraft good/poor comparison survives strict position, altitude and direction matching. The apparent 1.363-second cross-aircraft coincidence disappears under a 30-second source-transition exclusion. | **Time dependence is supported; a common external cause remains plausible but unresolved.** Precise synchronized onset is not established. |
| **H3. Provider, source-switching, MLAT, or decoding artifacts explain the observations.** | Stale-only, immediate-switch-only, isolated-outlier-only and wholly frozen-state explanations fail to remove the cargo pattern. A second publisher shows it too. | **Several narrow artifact explanations are weakened.** Shared decoder/association errors and asynchronously retained fields remain untested. |
| **H4. Persistent or intermittent aircraft/avionics faults explain the ATR cases.** | OH-ATN reports good and poor quality at almost the same location, altitude and heading. The expanded sample supplies no tightly matched non-ATR quality control. | **A permanent fault is weakened. Intermittent or shared equipment behavior remains unresolved.** |
| **H5. Space weather or a satellite-service fault caused the anomalies.** | Planetary activity is low in both windows; three previously suspect GPS outage notices had already closed. Local Finnish event queries returned no observations. | **A large planetary storm and those specific old outages are weakened as explanations.** Local ionospheric effects and other service/geometry issues remain unresolved. |

The regional context supplied by Traficom is a reason to investigate external interference. Its April assessment is not event-time evidence for either September flight window.[9]

## Cargo anomaly: tests that it survived

The original B-6115 / CAO1159 cluster contains 136 ADS-B position records from **12:54:05.734 to 13:01:06.714**. It has a median reported ground speed of 66.15 knots, while the explicit state records include true airspeeds of 450–454 knots. These are reported quantities; asynchronous updates prevent treating their difference as a measured wind or proof of the aircraft’s physical motion.[1]

| Test executed on the preserved records | Result |
|---|---|
| Remove points carrying the documented stale-position flag. | **135 of 136** cargo points remain. |
| Also remove points within 30 seconds of either observed endpoint of a change in position source. | **63 points** remain, median ground speed **66.5 knots**. |
| Use a 60-second transition exclusion instead. | **35 points** remain, median **67.4 knots**. A 120-second exclusion removes the entire interval and is uninformative. |
| Independently flag extreme coordinate jumps: reject endpoints of adjacent non-stale ADS-B pairs, 1–30 seconds apart, implying over 600 knots. | **131 points** remain, median **66.1 knots**. |
| Combine that geometric screen with the 30-second transition exclusion. | **59 points** remain, median **66.2 knots**, spanning **283.63 seconds** from first to last retained record. This span is not continuous coverage. |
| Derive speed from truly adjacent non-stale ADS-B coordinates, without connecting across removed records. | Across **95 pairs**, median derived speed is **68.34 knots**; median absolute difference from midpoint reported ground speed is **6.50 knots**. |
| Check whether one complete metadata object was simply repeated. | None of the adjacent explicit objects is identical. Airspeed, heading, roll and quality fields vary. Individual fields may still be retained. |

The first five tests show that a few stale points, extreme points or immediate source switches are insufficient to explain the cluster. The coordinate-speed test also weakens an explanation in which only the ground-speed label is wrong. These tests establish properties of the processed feed, not the true trajectory or the cause of the discrepancy. The filter definitions use the documented trace format, including its stale-position bit.[1][2]

### Second-publisher check

The public Airplanes.live viewer successfully loaded **September 13, leg 1**, for the original cargo flight. Two ADS-B samples inside the cluster were read directly from its historical interface and compared with the preserved GEV/adsb.lol records.[3]

| Airplanes.live visible historical observation | Nearest preserved GEV record | Comparison |
|---|---|---|
| **12:55:50 UTC:** 59.689° N, 29.240° E; ground speed **66 knots**, true airspeed **452 knots**; barometric altitude 36,000 ft, WGS84 altitude 32,850 ft. | **12:55:50.614:** 59.689140° N, 29.239639° E; ground speed **66.4 knots**, matching altitude values. | Position and ground speed agree at the viewer’s displayed precision. The nearest GEV row has no explicit details object, so the viewer’s airspeed is not treated as an independently timed simultaneous measurement. |
| **12:59:53 UTC:** 59.682° N, 29.260° E; ground speed **468 knots**, true airspeed **452 knots**. | **12:59:53.494:** 59.682343° N, 29.260285° E; ground speed **467.6 knots**. | Again agrees after rounding. This sample also preserves the cluster’s variable and sometimes extreme reported speed; the second viewer does not show uniformly slow motion. |

The viewer also exposes an MLAT point at about **12:55:19 UTC**, 60.871° N, 23.804° E, with reported ground speed 418 knots. It is preserved as evidence of a divergent published branch, without assuming that MLAT supplies the true aircraft position. The viewer’s displayed clock and integer position epoch differ by up to a second; both values are recorded rather than silently reconciled.[3]

This result weakens an explanation confined to GEV’s display or to adsb.lol’s publication alone. It is **two-publisher corroboration, not demonstrated receiver or decoder independence**. Only sparse viewer samples were verified; no second-provider raw archive was obtained. The sources may share feeder stations or software. No original radio messages, receiver IDs, field-acquisition times or onboard navigation logs were available to separate those possibilities.[2][3]

## ATR quality losses: stronger time dependence, weaker synchronization

OH-ATN supplies the most defensible comparison. Its good-quality observation at **12:22:09.654** and its joint-zero quality observation at **22:08:17.024** are **1.5065 km apart**, both at **9,000 ft**, with direction differing by just **3°**. Both pass the stale-position and source-consistency checks and lie more than an hour from source-transition endpoints. Ground speeds are 273.9 and 277.8 knots.[1]

The comparison survives a **2 km / equal altitude / within 5°** matching rule. At 1 km, no comparator exists; that is missing coverage, not evidence against deterioration. The other two ATRs do not provide equivalent matches at the strict setting. The result weakens a permanent aircraft-wide failure or a broad, static geographic blind spot as the whole explanation, but it cannot distinguish intermittent external interference, changing satellite geometry, intermittent equipment behavior or time-varying processing.[1]

The earlier apparently synchronized pair requires a downgrade. After removal of stale-marked positions, OH-ATE’s **21:53:50.297** and OH-ATI’s **21:53:51.660** joint-zero observations still differ by **1.363 seconds**, at reported positions approximately 163 km apart. However, **no pair remains within 60 seconds** when observations within 30 seconds of source-transition endpoints are excluded. The OH-ATE observation is only 13 seconds from the last ADS-B endpoint before a transition.[1]

This does not prove a provider artifact: genuine GNSS degradation can cause a change to MLAT, so excluding transitions can remove the phenomenon itself. It does mean the present evidence cannot establish synchronized failure onset. A quality-state timestamp is not an independently measured onset timestamp. The total joint-zero observations across the three ATRs falls from **24 to 21** after stale-position filtering; their exact per-field ages remain unknown.[1]

### Expanded control sample

The additional histories were selected from two regional GEV snapshots, with event windows fixed before inspecting their histories. The analysis region was **59–65° N, 20–32° E**, excluding ground records. Fourteen new aircraft histories and two refreshed existing histories were assessed.[1]

Only **EI-HGX**, a Boeing 737 MAX 8, supplies additional explicit ADS-B quality records within the ATR window and region: 25 records have NIC 8, and one has NIC 6 with NACp 8 at 1,600 ft. This is **not another joint-zero case** and the low approach altitude is not a suitable comparison with the higher ATR cases. RA-73722 supplies 145 regional MLAT position records, with no explicit ADS-B quality observations; it is unclassifiable for this test. Refreshed YL-CSN contributes one regional, stale-marked MLAT point.[1]

The prespecified close comparison required another aircraft within **5 minutes, 50 km of reported position, and 3,000 ft altitude**, with explicit ADS-B quality and no stale-position marker. **Zero matched non-ATR controls were found.** None of the 14 new histories supplies a regional cargo-window control. An absent or unclassifiable record is not a healthy control, and the expanded sample does not resolve external interference versus shared equipment susceptibility.[1]

## Natural-cause and satellite-service tests

For the cargo interval, the retrieved NOAA three-hour planetary product reports **Kp 1.33 for 12:00–15:00 UTC**. For the ATR interval, a separate minute-updated planetary estimate supplies all **31 expected records from 21:45 through 22:15**, inclusive. Its decimal estimated Kp ranges from **0.33 to 0.67**; at 21:53 it is **0.33**. These products offer no positive support for a large planetary geomagnetic storm during either event.[4][5]

The minute product closes the earlier evening planetary-data gap. It does not provide 31 independent GNSS observations or measure local Finnish scintillation. Valid requests to FMI’s Nurmijärvi archive for the two event periods returned HTTP 200 with a “No data for specified date” response. That establishes the result of those queries, not the absence of all local observations or quiet local conditions.[5][6]

The official GPS records also correct a potentially misleading lead: three apparently ongoing notices had already been closed. PRN 11’s interruption ended **June 26**, PRN 3’s ended **July 10**, and PRN 25’s ended **September 3**. The two retrieved closure notices and the September 11 satellite operational file support those dates. These specific earlier outages do not overlap the September 13 observations.[7][8]

The results weaken a large-storm explanation and those particular old satellite outages. They do not rule out local ionospheric irregularities, event-time satellite geometry, other unobserved service issues or receiver-specific responses. The satellite operational file predates the event and cannot establish uninterrupted constellation health throughout September 13.

## Access limits and revised investigation priority

Four direct historical OpenSky track requests returned HTTP 404. GEV’s latest-track interface returned later flights for B-6115 and OH-ATE, outside the original windows, and no usable track for the other two ATRs. Those later flights were not substituted for the event histories. Direct Airplanes.live trace requests returned HTTP 403, but its normal public viewer subsequently supplied the historical cargo observations described above. The API failures therefore are not represented as total failure to obtain second-publisher evidence.[1][3]

Across the original six histories, **5,928 explicit metadata objects contain zero mismatches** between the row’s position-source label and the metadata’s source label. This weakens a simple labeling error. It does not show that each field was freshly measured. The absence of original odd/even CPR radio payloads, their timestamps, receiver identity and decoding diagnostics prevents a genuine independent decoding replay. A reconstruction from already-decoded coordinates would be circular.[1][2]

**The cargo flight remains the strongest follow-up candidate.** Its unusual published position branch persists under multiple filters and is visible through a second publisher. The most decisive missing evidence is original receiver messages and independently timed onboard navigation/air-data records for 12:54–13:01. These could distinguish transmitted false positions, receiver/decoder mistakes, retained data, and onboard GNSS error. No such records were obtained, and no party was contacted.

**For the ATRs, the sound conclusion is time-varying reported navigation quality.** A matched non-ATR observation or a documented crew/receiver event is still needed to discriminate regional external degradation from equipment susceptibility. The source-transition sensitivity makes exact cross-aircraft timing a weaker lead than the same-aircraft good/poor comparison.

For trade or defense analysis, these tests support further navigation-reliability investigation. They do not yet establish disruption costs, a cargo-flow change, a military operation, an emitter location or responsibility for the anomaly. No numerical causal probabilities are assigned: the convenience sample, shared provenance and unobserved alternatives would make them misleading.

## Sources and reproducibility

1. **GEV / adsb.lol aircraft histories and executed calculations.** Preserved original six histories, 14 additional histories, two refreshed versions, fixed-window protocol, filtering plan, calculations and independent arithmetic audit are in the accompanying Evidence bundle. Current upstream trace pattern: [adsb.lol B-6115 trace](https://adsb.lol/data/traces/4e/trace_full_78044e.json). This rolling URL may no longer reproduce the preserved event; use the bundled files. The 20-aircraft count uses the latest saved version per identifier, not all versions added together. Scripts use only the standard Python library.

2. **readsb, pinned revision 05df27d.** [Trace and JSON format](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/README-json.md) and [JSON serialization code](https://raw.githubusercontent.com/wiedehopf/readsb/05df27d/json_out.c). These document output interpretation; reading them is not a replay of the original decoder or proof of the providers’ exact deployed versions.

3. **Airplanes.live.** Public [B-6115 history at the 12:55:50 sample](https://globe.airplanes.live/?icao=78044e&lat=59.687&lon=29.236&zoom=12.0&showTrace=2026-09-13&leg=1&timestamp=1789304151), [12:59:53 sample](https://globe.airplanes.live/?icao=78044e&lat=59.687&lon=29.236&zoom=10.0&showTrace=2026-09-13&leg=1&timestamp=1789304394), and [provider FAQ](https://airplanes.live/faq/). Viewer values were transcribed during the testing session ending September 14 UTC; original date selections, displayed timestamps, integer epochs and nearest GEV rows are preserved in independent-ui-observations.json and independent-ui-comparison.json. This is sparse visible-page evidence, not a downloaded raw Airplanes.live dataset.

4. **NOAA Space Weather Prediction Center.** [Three-hour planetary K-index product](https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json) and [daily geomagnetic indices](https://services.swpc.noaa.gov/text/daily-geomagnetic-indices.txt), retrieved September 13. Historical response bodies are preserved because these endpoints roll forward.

5. **NOAA Space Weather Prediction Center.** [Minute-updated estimated planetary Kp](https://services.swpc.noaa.gov/json/planetary_k_index_1m.json), retrieved September 13 at 23:55 UTC, containing 357 consecutive records from 17:52 through 23:48. The test uses the decimal estimated_kp field, rather than its separate integer kp_index field. The unmodified data and the 31 selected event-window records are preserved.

6. **Finnish Meteorological Institute, IMAGE network.** [Download command documentation](https://space.fmi.fi/image/www/wget_instructions.php), [interactive data request](https://space.fmi.fi/image/www/index.php?page=user_defined) and [availability page](https://space.fmi.fi/image/www/index.php?page=availability). Both NUR requests use documented YYYYMMDD[HH] syntax, length 120 minutes and sample interval 60 seconds. Captured no-observation responses and query URLs are preserved.

7. **U.S. Coast Guard Navigation Center.** [NANU 2026054](https://www.navcen.uscg.gov/sites/default/files/gps/nanu/2026/2026054.nnu), closing PRN 3’s July interruption; [NANU 2026069](https://www.navcen.uscg.gov/sites/default/files/gps/nanu/2026/2026069.nnu), closing PRN 25’s September 2–3 interruption. Retrieved notices are preserved.

8. **U.S. Coast Guard Navigation Center.** [GPS satellite operational file](https://www.navcen.uscg.gov/sites/default/files/gps/sof/current_sof.sof), retrieved version created September 11, including PRN 11’s June 26 closure and the other outage histories. The preserved response, rather than the subsequently updated URL, is the tested record.

9. **Traficom.** [Interference affecting mobile communications and satellite navigation services continues in Finland](https://www.traficom.fi/en/news/interference-affecting-mobile-communications-and-satellite-navigation-services-continues-finland), regional assessment dated April 21, 2026. Context only; it is not a direct observation of the September events.

The Evidence manifest records SHA-256 hashes for preserved inputs, calculations and results. Local robustness thresholds were recorded before calculating this extension, but after the six discovery histories had already been inspected. They are exploratory sensitivity tests, not preregistration of unseen evidence. The extension’s selection amendment was recorded before retrieving the additional histories. No significance tests or population extrapolations were applied.
