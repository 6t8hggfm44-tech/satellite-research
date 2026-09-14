# Trade-impact adapter

Translate a verified traffic or service anomaly into a bounded commercial question. Treat disruption, traffic change, cargo movement and economic impact as separate claims. An aircraft label, callsign, orbital pass or missing track does not identify a shipment, payload, customer, cargo value or trade decision.

This is a recommended analytical extension. The originating traffic/GNSS investigation did not establish shipment contents, realized trade losses or investment outcomes.

## Phase contract

| Phase | Adapter requirement |
|---|---|
| P01 scope | Define the trade question, route/service, period, decision horizon and observable outcome. Distinguish exposure from realized disruption. |
| P02 GEV | Inspect available aircraft, vessel, satellite and event sources. Record which data actually support the commercial question. |
| P03 triage | Select anomalies with a plausible, stated connection to transport capacity, navigation reliability or a commercial service. |
| P04 case freeze | Freeze the route/service cohort, comparison periods, metrics, thresholds, alternative explanations and revision rules. |
| P05 archive | Save traffic evidence and relevant published operational/commercial records with their time and coverage limits. |
| P06 normalize | Align event times, reporting periods, currencies/units if relevant, route definitions and actual versus estimated statuses. |
| P07 quantify | Estimate observable delay, cancellation, detour, service unavailability or volume change; disclose missing coverage and assumptions. |
| P08 map | Show the affected corridor/service and evidence coverage. Do not imply known cargo contents from route or vehicle identity. |
| P09 hypotheses | Instantiate the catalog below; specify the mechanism connecting anomaly and commercial outcome. |
| P10 test | Compare matched baselines and realized outcomes, including evidence inconsistent with the proposed mechanism. |
| P11 audit | Check selection, reporting lag, confounders, source dependence, denominators and sensitivity. |
| P12 report | State the verified anomaly, supported commercial implication, magnitude if measurable, uncertainty and next decision-relevant evidence. |

## Inputs and baselines

Use a validated traffic/service finding from the aircraft or satellite adapter as the starting input. Add published schedule and actual-status records, route capacity, aggregate freight/port/airport statistics, service availability notices, weather and relevant operational announcements when available. Cite original publishers and identify revisions. Respect reporting lag: monthly aggregates cannot precisely locate a short event's consequence.

Preserve entity identifiers with valid dates, origin/destination, scheduled/actual/estimated times, service type, cancellations/diversions, observation coverage, capacity units, reporting period and source provenance. Keep an inferred route, estimated arrival and confirmed arrival separate. Cargo capacity is not load, and flight counts are not tonnage.

Build comparable baselines by route, time of day/week, season, aircraft/vessel class, service regime and known operational changes. Select controls before outcomes when possible. A convenience sample of visible traffic cannot establish total trade volume. Record denominator coverage and whether missing tracks could systematically remove affected vehicles.

Predeclare materiality and alert thresholds for the decision context; version the rationale and sensitivity ranges. Do not substitute a fixed geographic radius, speed cutoff or case-specific threshold for a commercial impact test. If no defensible magnitude exists, report exposure and evidence gaps rather than fabricate a loss estimate.

## Hypothesis-test catalog

| ID / hypothesis | Prediction and test | Falsifier or weakening result | Confounders / limits |
|---|---|---|---|
| TR01 navigation/service anomaly caused transport disruption | Event-matched actual delays, diversions or cancellations exceed a comparable baseline and fit a documented operational mechanism. | Normal realized operations despite adequate observation, or disruption preceding the anomaly. | Weather, ATC, strikes, maintenance and schedules can produce the same outcomes. Association is not sufficient causation. |
| TR02 apparent volume change is a coverage artifact | Counts move with receiver coverage, provider outages, stale records or geographic selection. | The change persists in independently measured aggregate throughput with stable definitions. | Separate websites may share feeds; aggregate reports may have lag or revisions. |
| TR03 routing or capacity shifted | Repeated observed route/capacity changes persist across periods and are supported by actual operations or operator statements. | A one-off deviation returns to baseline or is explained by a temporary operational event. | Scheduled capacity differs from utilization; flight type does not identify actual cargo. |
| TR04 satellite-service disruption affected a commercial activity | A timed service incident aligns with measured outages and user/service dependence. | Restoration predates the interval, or the relevant service remained available through adequate redundancy. | Orbital anomaly, service outage and customer impact are distinct links requiring separate evidence. |
| TR05 the anomaly is commercially immaterial | Operations, throughput and service performance stay within a declared materiality band despite adequate exposure and coverage. | Persistent measurable outcomes exceed that band and survive confounder checks. | Sparse data cannot support a finding of no impact; the wrong metric may miss relevant costs. |

## Causal chain and reporting

Make the chain explicit: observed data anomaly → validated physical/service event → operational consequence → commercial consequence. Mark the evidence supporting each arrow. If only the first link is established, report a monitoring question, not a disruption forecast. If several explanations fit, state what evidence would separate them.

Use scenario ranges only with explicit assumptions and units. Distinguish measured outcomes from modeled exposure, and sensitivity analysis from a calibrated probability. Do not infer a trade restriction, military purpose or illicit shipment from traffic patterns alone.

Source independence applies at the measurement level. An operator statement and a schedule website may derive from the same status feed; multiple satellite catalogs may reuse one orbit solution. Record shared dependencies. A genuinely different operational measure can add evidence without independently confirming the original position anomaly.

The report should answer: what changed; what commercial activity could be affected; what consequence was actually observed; what alternatives remain; and which bounded next observation would change the decision. Keep unsupported monetary values and specific investment recommendations out of the evidence finding.
