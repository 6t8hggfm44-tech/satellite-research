# Finland GNSS worked example

This historical case explains how the reusable workflow emerged. Its observations concern **September 13, 2026**; final testing and publication of the local report continued into September 14 UTC. It is an example of the method, not a current intelligence assessment or a default set of parameters.

- [Chronology](chronology.md): material actions across P01–P12, including initial lead selection, GEV usage correction, preserved histories, maps, deep analysis, test execution, access failures, revisions and verification.
- [Lessons](lessons.md): the case-specific failure modes and the generalized rules they justify.
- [Hypothesis test results](hypothesis-test-results.md): the completed report, with an added portability note.
- [Compact result extracts](test-result-extracts.json): central metrics and the two second-publisher rounding comparisons, with the original report's SHA-256.

## Reproduction boundary

The originating investigation preserved six initial traces, 14 additional aircraft histories, two refreshed histories, source captures, analysis scripts, test plans and a hash manifest. Its local final evidence ZIP held **83 files** including the report and manifest. The staged evidence calculations were rerun in isolation: three analysis outputs matched byte-for-byte, and the second-publisher coordinate comparison and NOAA event-window calculations reproduced.

This public repository contains **compact historical results and methodology**, not that complete provider-data archive or the earlier PDF/ZIP deliverables. Consequently, the original numerical analysis cannot be independently rerun from this public example alone. The successful reproduction described in the report belongs to the original preserved archive; it is not a claim that this repository supplies those missing inputs.

The result extracts are calculated facts copied from that verified deliverable. They do not authenticate the upstream measurements. The Airplanes.live readings are manually transcribed values from a historical viewer, not a downloaded receiver archive. Agreement across two publishers does not establish independent receiving hardware or software.

Public source links in the report may roll forward or stop serving the original interval. Treat retrieval dates, product types, saved event windows and source dependencies as part of the evidence. Do not fetch today's data and call it reproduction of this case.

The general workflow and templates intentionally preserve the distinction between an anomaly in processed data, a real-world event, a mechanism, attribution and trade impact. In this case the cargo anomaly remained the strongest follow-up lead, while spoofing, jamming, actor responsibility and economic consequences remained unconfirmed.
