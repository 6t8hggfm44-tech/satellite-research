# Run format, version 1

These templates are portable records, not an executable workflow. Copy them into a new run directory, preserve their filenames, and fill only fields supported by the work actually performed. They make no requests, schedule no work, and do not assert that a workflow stage or test has run. Stage identifiers **P01–P12** refer to the root workflow; this format does not redefine their names or require all stages to execute.

All JSON files use `schemaVersion: 1`. Blank templates are intentionally incomplete: `null` means unknown or not supplied, an empty array means no entries have been recorded, and an empty object supplies no recorded parameters. Neither means zero, absent in the world, healthy, passed, or not applicable. Do not convert unknowns into invented defaults. Markdown `{{placeholders}}` must be replaced or explicitly identified as unavailable before delivering a report.

## Common conventions and minimum run data

- Use stable, case-local identifiers for sources, evidence, observations, hypotheses, tests, plans, and runs. Identifiers are strings; references must resolve within the case. They do not have to encode dates, people, or a particular domain.
- Before substantive execution, the case needs an ID, the actual user request, domain, objective, an explicitly bounded scope or documented scope uncertainty, and the root workflow version. `parameters` contains only actual run settings. Do not treat an unfilled template as an active case.
- For every result claimed in a report, retain a test or observation ID, its evidence IDs, applicable selection/plan versions, acquisition method, event coverage, and limitations. Every completed test needs an actual execution record; a plan alone is insufficient.
- Use ISO 8601 UTC strings ending in `Z` or `+00:00`. Preserve original source time strings and their timezone/precision separately when needed. Never relabel local or unknown-zone times as UTC without a recorded conversion basis.
- Keep event time, retrieval time, publisher update time, and individual field time distinct. A recent retrieval does not make an old position or measurement current. A state-object timestamp does not establish simultaneous field acquisition or the onset of a failure.
- Preserve numerical zero separately from null and missing fields. Metrics require units and a defined denominator where one is meaningful. A sample count is not exposure duration or an independent-event count.
- Paths inside run records are repository-relative or bundle-relative. Use public source URLs when available. Do not place private absolute paths, credentials, session cookies, personal configuration, or model-specific tool tokens in the templates or shared records.
- A SHA-256 string must be 64 lowercase hexadecimal characters calculated from actual preserved bytes. State what was hashed. A response wrapper hash is not the hash of original radio data, sensor data, or an HTTP body that was never retained. Integrity is not authenticity.

## Status values

| Field | Allowed values | Meaning |
|---|---|---|
| `case.status` | `draft`, `active`, `blocked`, `complete`, `cancelled` | Overall work state. `complete` means the agreed deliverable is finished, not that every mechanism is proven. |
| `case.stages[].status` | `not_started`, `in_progress`, `completed`, `partial`, `blocked`, `failed`, `skipped`, `not_applicable` | Actual stage state. A skipped or inapplicable stage is not completed execution. |
| `test-plan.status` | `draft`, `ready`, `superseded`, `closed` | Whether the specific plan version is ready, replaced, or finished. |
| `test-plan.planTiming` | `not_recorded`, `prospective`, `amended_before_execution`, `retrospective`, `mixed` | Relation of planning to the actual execution/data inspection. The last two are legitimate when disclosed. |
| `test-results.status`, result `executionStatus` | `not_started`, `in_progress`, `completed`, `partial`, `blocked`, `failed`, `skipped`, `not_applicable` | Execution state, separate from scientific or analytical judgment. |
| Hypothesis `status`, conclusion `status` | `supported`, `weakened`, `inconclusive`, `not_tested`, `not_applicable` | `supported`/`weakened` are relative to the exact claim and evidence; neither automatically means proved/disproved. |
| Result `resultStatus` | `not_tested`, `available`, `inconclusive`, `not_applicable` | Whether the specified test produced an interpretable result. Claim-specific verdicts belong in `conclusions`. |
| Source `accessStatus` | `not_requested`, `available`, `partial`, `empty_response`, `access_denied`, `request_failed`, `unavailable`, `unknown` | Actual access outcome. An empty response is not a healthy control. |
| Coverage `assessmentStatus` | `not_assessed`, `partial`, `assessed` | Whether coverage and missingness were examined. |
| Provenance `independenceStatus` | `not_assessed`, `shared_dependencies`, `partially_independent`, `independently_verified`, `unknown` | Independence must state its layer and evidence. Two domains alone do not establish independent receivers or processing. |
| Implication `status` | `unknown`, `not_assessed`, `hypothesis`, `supported`, `not_applicable` | Distinguish a proposed consequence from observed impact. |
| Reproducibility `status` | `not_checked`, `partial`, `passed`, `failed`, `blocked`, `not_applicable` | A successful calculation replay validates only what was replayed. |

`executed: false` is the default. Set it true only when at least one step of that stage/test itself ran, and describe partial execution. An attempted prerequisite retrieval is not execution of an analysis requiring the unavailable data. Such a test can have `executionStatus: blocked`, `executed: false`, and `resultStatus: not_tested`, with its retrieval attempt retained as evidence. If a test actually runs but cannot distinguish hypotheses, use `inconclusive`, not `not_tested`. If a test is irrelevant by design, use `not_applicable` with a reason. A failed command is not scientific evidence that a hypothesis is false.

## Case scope

`scope.timeUTC` is the requested event window, not the retrieval window. Specify endpoint inclusion. Region `type` can be `global`, `bbox`, `geometry`, `named`, `orbital`, `not_applicable`, or a documented domain-specific value. A WGS84 bbox is `[west, south, east, north]` in degrees. Do not put an orbital frame or inferred receiver location into a geographic bbox. Use `referenceFrame` for the applicable terrestrial/orbital reference; describe any coordinate conversion in evidence records. Null scope values require an explicit uncertainty statement before interpreting coverage.

Stage records retain actual start/end times, linked evidence and output paths, and a reason for blocking, skipping, failure, or inapplicability. `execution.externalRequestsMade` records an action that occurred; it is not permission to make a request. Completion booleans and stage statuses must reflect the actual run.

## Source register entry shapes

The arrays start empty. Add one real record per selection version, source, or preserved evidence item; do not insert dummy records just to satisfy a count.

A `selectionPlans` entry has:

```json
{
  "version": null,
  "recordedAtUTC": null,
  "recordedBeforeRetrieval": null,
  "basis": null,
  "inclusionCriteria": [],
  "exclusionCriteria": [],
  "queryParameters": {},
  "samplingLimit": null,
  "previousVersion": null,
  "amendmentReason": null,
  "alreadyInspectedEvidenceIds": []
}
```

The version is a positive integer in a populated record. Preserve each version when selection changes. Record what was already inspected before an amendment; a change after seeing coverage is not an untouched initial plan.

A `sources` entry has:

```json
{
  "id": null,
  "name": null,
  "publisher": null,
  "kind": null,
  "url": null,
  "accessStatus": "not_requested",
  "accessReason": null,
  "license": null,
  "provenance": {
    "upstreamSourceIds": [],
    "collectionMethod": null,
    "processingDescription": null,
    "independenceStatus": "not_assessed",
    "independenceLayer": null,
    "independenceEvidenceIds": [],
    "knownDependencies": [],
    "unknownDependencies": []
  }
}
```

Source `kind` describes the actual source, such as API, file, document, repository, sensor archive, or rendered viewer. `independenceLayer` can distinguish publisher, processing, decoder, receiver, instrument, or another relevant layer. Unknown upstream dependencies stay unknown.

An `evidence` entry has:

```json
{
  "id": null,
  "sourceId": null,
  "selectionVersion": null,
  "description": null,
  "captureMethod": null,
  "evidenceKind": null,
  "url": null,
  "retrievedAtUTC": null,
  "publishedAtUTC": null,
  "sourceUpdatedAtUTC": null,
  "eventCoverageUTC": { "start": null, "end": null },
  "originalTimeRepresentation": null,
  "timeConversionBasis": null,
  "fieldTimeAvailability": "unknown",
  "requestParameters": {},
  "responseStatus": null,
  "artifactPath": null,
  "artifactSha256": null,
  "artifactBytes": null,
  "rawArtifactPath": null,
  "rawSha256": null,
  "rawCaptureAvailable": false,
  "derivedFromEvidenceIds": [],
  "transformations": [],
  "precisionAndRounding": null,
  "missingnessReasons": [],
  "limitations": []
}
```

`evidenceKind` identifies original measurements, a processed dataset, a source response, a rendered-view observation, manual transcription, documentation, an error capture, or an analysis artifact. A manual transcription must say so; do not label it a downloaded raw archive. Retain timestamp/rounding discrepancies instead of silently correcting them. `fieldTimeAvailability` is `available`, `partial`, `unavailable`, `unknown`, or `not_applicable`.

Use `artifactSha256` for the preserved artifact bytes. Populate `rawSha256` only when the separately identified raw artifact actually exists. A processed response can be the original captured response while still not being the underlying instrument or transmission data; describe both layers precisely. Error captures and empty responses also receive evidence IDs.

Coverage/missingness entries identify the unit or stratum, reason, relevant window, and evidence IDs. Reasons can include `no_observation`, `outside_scope`, `missing_quality`, `stale_position`, `unknown_field_age`, `unavailable_source`, `access_denied`, `request_failed`, `provenance_unverified`, or a documented domain-specific code. Never silently drop unclassifiable units from a denominator.

## Observations and hypotheses

An `observations` entry records a measured or directly inspected statement without upgrading it to a causal judgment:

```json
{
  "id": null,
  "statement": null,
  "evidenceIds": [],
  "eventTimeUTC": null,
  "eventTimeRangeUTC": { "start": null, "end": null },
  "eventTimeBasis": null,
  "timeUncertaintySeconds": null,
  "fieldTimesUTC": {},
  "fieldAgesSeconds": {},
  "location": null,
  "referenceFrame": null,
  "measurements": {},
  "units": {},
  "missingnessReasons": [],
  "limitations": []
}
```

Retrieval time is linked through evidence IDs. `fieldTimesUTC`/`fieldAgesSeconds` are populated only for fields whose timing is actually known. Do not derive a supposed acquisition time from a rendering timestamp. An event-time range can represent uncertainty or a sampled interval, but is not continuous duration by default.

A `hypotheses` entry has:

```json
{
  "id": null,
  "claim": null,
  "mechanism": null,
  "predictions": [],
  "falsifiers": [],
  "alternatives": [],
  "canCoexistWith": [],
  "status": "not_tested",
  "judgment": null,
  "confidence": "unassessed",
  "supportingObservationIds": [],
  "contradictingObservationIds": [],
  "testIds": [],
  "evidenceIds": [],
  "assumptions": [],
  "limitations": [],
  "updatedAtUTC": null
}
```

Confidence is `unassessed`, `low`, `moderate`, or `high`, with reasoning in `judgment`; it is not a numerical posterior. A data inconsistency, an underlying physical cause, and an operational consequence are different claims and may need separate hypotheses. Business and military implication records remain unknown until evidence or a clearly labelled testable implication exists. Do not infer actor intent or economic impact from the mere presence of an anomaly.

## Test plan entries and amendments

A populated plan requires `planId`, positive-integer `version`, a real recording time, timing classification, applicable selection version, and at least one test before a claim of planned testing. `recordedBeforeExecution` is true only when verifiable chronology supports it. Leave it null when unknown; use false for retrospective planning. Amendments retain previous version, timestamp, changed fields, reason, and evidence already inspected. Do not rewrite an executed plan to make its thresholds look prospective.

A `tests` entry has:

```json
{
  "id": null,
  "stageId": null,
  "hypothesisIds": [],
  "question": null,
  "prediction": null,
  "decisionRules": [],
  "inputEvidenceIds": [],
  "requiredData": [],
  "method": null,
  "parameters": {},
  "units": {},
  "controlCriteria": [],
  "missingnessRules": [],
  "exclusionRules": [],
  "sensitivityGrid": {},
  "independenceRequirements": [],
  "implementationArtifactPath": null,
  "implementationSha256": null,
  "expectedOutputs": [],
  "feasibility": "not_assessed",
  "blockers": []
}
```

`stageId` references the applicable P01–P12 stage when known. Feasibility is `not_assessed`, `feasible`, `partially_feasible`, `blocked`, or `not_applicable`. A control is usable only when the specified timing, location/reference frame, measurement quality, comparability, and independence criteria were actually met. A sensitivity filter can remove the true phenomenon as well as an artifact; document that confound before interpreting a disappearing signal.

## Test result entries

A `results` entry has:

```json
{
  "testId": null,
  "planId": null,
  "planVersion": null,
  "selectionVersion": null,
  "stageId": null,
  "executionStatus": "not_started",
  "executed": false,
  "startedAtUTC": null,
  "endedAtUTC": null,
  "resultStatus": "not_tested",
  "actualMethod": null,
  "actualParameters": {},
  "inputEvidenceIds": [],
  "inputSha256": {},
  "implementationArtifactPath": null,
  "implementationSha256": null,
  "outputEvidenceIds": [],
  "attemptEvidenceIds": [],
  "observations": [],
  "metrics": {},
  "units": {},
  "controlAssessment": {
    "criteriaMet": [],
    "criteriaNotMet": [],
    "usableControls": null,
    "unobservableControls": null,
    "evidenceIds": []
  },
  "missingness": [],
  "deviationsFromPlan": [],
  "conclusions": [],
  "blockers": [],
  "limitations": []
}
```

A conclusion identifies `hypothesisId`, `status`, `reason`, and `evidenceIds`. Its status uses the hypothesis enum. `metrics` retain measured numbers and denominators rather than only a pass/fail assertion. `inputSha256` maps preserved input evidence IDs to their actual file hashes. Implementation hashes identify the code actually executed; do not require code for a legitimately manual test, but record its method and limitations.

Each `artifacts` entry identifies `path`, `sha256`, `bytes`, `kind`, and `evidenceIds`. Derived results link back to original evidence. Keep obsolete inputs and plan versions when they explain an executed result; distinguish refreshed versions rather than counting them as new independent units.

## Reproducibility and completion

A `passed` reproducibility status requires an executed, scoped verification and its output evidence; booleans must agree with it. State whether the comparison was byte equality, parsed data equality, a numerical tolerance, or a partial metric check. A script replaying calculations against manual transcriptions does not authenticate the external transcription. A hash check does not independently verify the source. Live refetching is a new acquisition, not deterministic replay of an old event.

A finished report may correctly contain blocked or inconclusive tests if it honestly states the delivered scope and remaining limits. It must not say all P01–P12 stages ran when they did not. Before delivery, remove unfilled prose placeholders, reconcile identifiers and statuses, and ensure every claimed test outcome is backed by the corresponding executed result or explicitly marked not tested/not applicable.
