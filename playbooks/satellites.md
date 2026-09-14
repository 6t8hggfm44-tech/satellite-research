# Satellite traffic adapter

**Status: recommended extension.** This adapter generalizes evidence-handling lessons from aircraft/GNSS work. The originating investigation did not perform quantitative orbital propagation, maneuver detection, conjunction assessment or rendezvous tests. None of the procedures below should be described as completed without a separate archived run.

Use public orbital and service records to identify reviewable anomalies in traffic or spacecraft behavior. A pass over a place, an orbital-plane alignment, a catalog update or two nearby map symbols is not evidence of surveillance, rendezvous, interception or hostile intent.

## Phase contract

| Phase | Adapter requirement |
|---|---|
| P01 scope | Define the object set, retrospective UTC window, orbit regime, observable behavior and decision question. Distinguish orbital behavior from mission or intent claims. |
| P02 GEV | Discover available satellite layers and their upstream catalogs, refresh rules and propagation implementation. Determine whether displayed positions are observations or predictions. |
| P03 triage | Flag persistent changes or unusual relationships relative to a documented baseline; check identity and stale elements first. |
| P04 case freeze | Freeze object IDs, epochs, windows, comparison objects, metrics, threshold rationale, model/version and amendment rules. |
| P05 archive | Preserve original element sets/ephemerides, metadata, notices, observation epochs, retrieval times and error results. |
| P06 normalize | Resolve identifiers, time scales, coordinate frames, units, element formats and modeled versus measured states. |
| P07 quantify | Propagate compatible inputs only with a documented model; measure residuals and sensitivity to epochs/models. Preserve uncertainty. |
| P08 map | Label the epoch and prediction horizon; distinguish ground tracks, three-dimensional separation and observed positions. |
| P09 hypotheses | Instantiate the catalog below; ordinary orbital mechanics and catalog artifacts must remain explicit alternatives. |
| P10 test | Execute declared comparisons and independent-data checks; record tests not possible with available inputs. |
| P11 audit | Check identity continuity, frame/time consistency, stale elements, uncertainty, shared data and selection effects. |
| P12 report | Separate catalog facts, model calculations, observed changes, possible explanations and mission-intent claims. |

## Inputs and model record

Preserve catalog identifier and designation, publisher, object type and identification confidence, full original orbit product, epoch, reference frame, time scale, units, validity span, retrieval time, quality flags and covariance/uncertainty when provided. For TLE data preserve the exact two lines and their parsing checks. Catalog identities can change or be mistaken after deployment, separation, fragmentation or reacquisition.

Record propagator name/version, compatible orbit-product assumptions, Earth/orientation data, frame transformations, evaluation times and software configuration. Do not feed one product into an incompatible propagator. Do not silently mix an inertial state, an Earth-fixed map coordinate and a ground-track projection. Resolve time-scale conversions explicitly rather than assuming every numeric timestamp is UTC.

Element sets are fitted orbit estimates, not direct observations at every displayed position. Prediction uncertainty depends on age, orbit regime, drag, maneuvers and fitting quality. TLEs do not generally provide the covariance needed to assign a defensible encounter probability; do not invent one. If no validated uncertainty model exists, report sensitivity across epochs/products and state that it is not a calibrated error bound.

## Baselines and thresholds

Compare each object with its own history, similar objects in the same orbit regime, documented operational cycles, and the catalog's normal update/reacquisition behavior. Include expected ordinary passes, stationkeeping, orbit maintenance, formation operations, deployment, disposal and environmental perturbations where applicable.

Choose screening distances, residual limits, persistence windows and epoch-age rules from the product, question, resolution and baseline. Freeze and version them before reviewing candidate outcomes; test alternatives. Do not reuse aircraft thresholds or invent universal separation/maneuver cutoffs. A proximity screen is not a collision-risk or rendezvous determination.

## Recommended hypothesis-test catalog

| ID / hypothesis | Prediction and test | Falsifier or weakening result | Confounders / limits |
|---|---|---|---|
| ST01 ordinary pass or orbital geometry | Propagate a baseline orbit over a comparison interval and compare pass frequency, ground track and viewing geometry. | A persistent deviation remains across compatible, fresh orbit products beyond the baseline/model sensitivity. | Map projection, Earth rotation, altitude and observation selection can make routine passes look unusual. |
| ST02 stale element, catalog or rendering artifact | Compare successive epochs, independently processed observations and rendered positions; test identity continuity. | The same physical change appears in separately sourced observations after frame/time/model checks. | Several catalogs may redistribute one orbit solution; agreement is not independent measurement. |
| ST03 environmental or modeling change | Evaluate whether residuals vary consistently with modeled drag/perturbations and orbit regime; compare appropriate controls. | A localized, persistent state change is inconsistent with those model sensitivities and independently observed. | Model error can resemble maneuver evidence; global space-weather context is not a local force estimate. |
| ST04 ordinary maneuver or mission operation | Compare pre/post behavior with operator notices and historical maintenance, deployment or disposal patterns. | Reliable observations establish behavior inconsistent with the proposed ordinary operation. | A maneuver can be detected without its purpose being known. Absence of a public notice is weak negative evidence. |
| ST05 coordinated proximity activity | Require sustained relative-motion behavior in a common frame, repeated observations and uncertainty-aware comparisons against coincidental alignment. | The apparent approach disappears with corrected epochs/frames or is compatible with ordinary relative motion. | Nearness alone does not establish interaction; conjunction is not rendezvous, and rendezvous does not establish hostile intent. |
| ST06 object separation, fragmentation or identity confusion | Check catalog additions, identity histories and independently observed multiple objects. | Stable identity and observations explain the apparent split as processing or selection error. | Sparse observations and delayed catalog updates can obscure both timing and object identity. |
| ST07 space-service anomaly | Compare operator/service advisories, restoration notices and measured service availability at the event time. | The specific outage closed before the interval or the proposed service consequence is absent in adequate observations. | Service failure can occur without an unusual orbit, and a maneuver need not interrupt service. |

## Audit and reporting rules

For a candidate maneuver, compare predictions and observations across the proposed change; an element-to-element difference alone can reflect refitting. State whether the evidence is an operator confirmation, a fitted change supported by observations, or a catalog-derived screening signal. Preserve all considered epochs, not just the pair producing the largest difference.

For apparent proximity, report the data/model limitations and distinguish shared orbital plane, overlapping ground track, predicted conjunction and sustained relative motion. Ordinary passes over military or commercial sites do not identify spacecraft tasking. Avoid inferring payload operation, collection targets or operational intent from location alone.

Mark every recommended test as `not_started`, `blocked`, `partial` or `completed` with its actual evidence. A successful propagation demonstrates a model calculation, not independent validation of the orbit. A changed hypothesis after seeing results requires a new version and an exploratory label.
