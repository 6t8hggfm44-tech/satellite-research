# {{case_title}}

{{Direct answer to the user: what the completed work supports, what changed after testing, and the most important unresolved question. If no test ran, state that clearly.}}

Case: {{case_id}} · Domain: {{domain}} · Workflow: {{workflow_version}}  
Event scope: {{event_start_utc}}–{{event_end_utc}} · Region/reference frame: {{region}}  
Evidence retrieved: {{retrieval_start_utc}}–{{retrieval_end_utc}} · Report updated: {{report_updated_utc}}

## Findings and revised hypotheses

| Hypothesis ID and claim | Status | Evidence from completed tests | Remaining uncertainty |
|---|---|---|---|
| {{hypothesis_id_and_claim}} | {{supported / weakened / inconclusive / not_tested / not_applicable}} | {{test IDs, measured result, evidence IDs}} | {{specific limit}} |

{{Distinguish recorded observations from interpretations. State whether hypotheses can coexist. Do not assign numerical probabilities without an appropriate model and explicit assumptions.}}

## Scope, provenance, and coverage

{{Describe actual sources, acquisition methods, selection versions and amendments, event-time coverage, field-time availability, reference frames, source dependencies, and applicable licenses. Distinguish original measurements, processed products, rendered-view observations, and manual transcription.}}

| Sample or source | Included units and observations | Usable event-time coverage | Missingness and selection limits |
|---|---|---|---|
| {{source_or_sample}} | {{counts with unit definitions}} | {{coverage and quality criteria actually met}} | {{unknown, absent, stale, unavailable, outside scope, or otherwise unclassifiable}} |

{{An observation count is not automatically an independent event count, exposure duration, or population denominator. Distinguish a source retrieval time from event time and the age of individual fields.}}

## Tests actually performed

| Test ID | Predefined prediction and decision rule | Execution status | Measured result | Effect on hypothesis |
|---|---|---|---|---|
| {{test_id}} | {{prediction, controls, thresholds, plan version}} | {{completed / partial / blocked / failed / skipped / not_started / not_applicable}} | {{actual result and evidence IDs, or why no result exists}} | {{claim-specific status and practical limit}} |

{{Explain the strongest case evidence, counterexamples, comparison quality, and threshold sensitivity. Preserve failed attempts and negative results. Say when a plan was recorded after inspecting the data. Do not describe unavailable controls as normal or a blocked test as a completed negative finding.}}

## What the results establish

{{Separate consistency within a recorded dataset, corroboration across published products, independence of measurement or processing, an underlying physical/operational mechanism, and practical consequences. State which distinctions were actually tested; do not advance a claim merely because a lower-level check passed.}}

## Practical significance

**Business:** {{Observed implication with evidence IDs, or unknown/not assessed/not applicable. Separate measured impact from a testable commercial hypothesis and list the assumptions needed for a decision.}}

**Military:** {{Observed relevance with evidence IDs, or unknown/not assessed/not applicable. Do not infer intent, attribution, deployments, or operational effects solely from an unexplained data anomaly.}}

## Unresolved questions and next discriminating tests

{{Identify the smallest next tests that could distinguish the remaining explanations, the evidence required, and whether that evidence is available. Clearly label these as proposed and not executed. Distinguish an access blocker from an analytical result.}}

## Sources and reproducibility

{{Link evidence IDs to the source register, preserved artifacts, source URLs where available, and test results. Identify any manual transcription, sampling/rounding limits, and shared source dependencies.}}

{{State which calculations were reproduced, how input hashes were checked, and what was not independently verified. Give portable artifact paths and the verified reproduction command, if one exists. Otherwise state that reproduction has not been performed. Hashes verify file integrity, not source truth.}}
