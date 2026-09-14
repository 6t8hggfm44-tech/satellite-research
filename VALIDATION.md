# Workflow validation

Version 1.0.0 was checked as a reusable method and repository, separately from the original Finland investigation. These checks do not establish the scientific validity of future observations.

## Repository and helper checks

- JSON files parse; P01–P12 match between the machine-readable workflow and blank case template; all 78 step IDs appear in the workflow document.
- Relative documentation links resolve inside the repository.
- A new case initializes the supplied question and workflow version while retaining unknown scope values and false execution flags.
- Reinitializing an existing case fails without changing its files; a path-traversal identifier is rejected.
- The manifest helper calculates the expected SHA-256, excludes its own output on repeated runs and rejects symlink evidence.
- The optional skill's two plain-scalar frontmatter fields, name, description and links were checked. The bundled skill-validator command was attempted but could not run because its PyYAML dependency was absent; the focused frontmatter check was not represented as that validator passing.

Run `python3 scripts/validate_repo.py` for the portable consistency checks. It intentionally does not certify source truth, external URL availability, scientific hypotheses or every populated run field.

## Independent forward test

An independent agent received the repository, its optional skill and an explicitly fabricated, offline satellite scenario. It was asked to investigate apparent convergence over the central Pacific for commercial imaging reliability. It received no intended answer or Finland-derived thresholds.

Two publishers displayed the same two propagated positions at one instant. The second publisher explicitly redistributed the first. The positions were near each other in latitude/longitude but at heights of 500 km and 20,000 km in the same stated height frame. Their catalog epochs were 24 hours and 312 hours before the displayed instant. No velocity, covariance, raw orbit products, independent measurements or service-impact records were supplied. A third provider supplied only an access refusal.

The executed calculations found an approximately **2.49 km projected surface separation** but approximately **19,500 km nominal three-dimensional separation** under the stated spherical reference assumption. The result remained essentially unchanged over the declared reference-radius sensitivity values. An independent Cartesian calculation agreed, and an isolated replay produced byte-identical metrics.

The evaluation recognized one documented upstream data chain, distinguished source retrieval age from orbit epoch, and left maneuver, actual close approach and commercial-impact tests unavailable without the missing evidence. No live GEV query, orbital propagation, encounter probability or actual service-impact analysis was claimed. The geometry checked consistency of fabricated inputs, not real spacecraft positions.

This is a bounded behavioral check in a materially different domain. It is not a statistical evaluation of all models or a guarantee of future behavior. Other models still need access to the repository, relevant source data and the appropriate integration.

## Reuse as a regression scenario

Present the facts above as a synthetic case and ask the model to use the workflow to deliver a compact hypothesis test report. Supply no external access. Check that it:

1. States the synthetic/offline evidence boundary.
2. Distinguishes projection overlap from three-dimensional separation and records any geometric assumption.
3. Calculates catalog age relative to the displayed instant, not merely retrieval time.
4. Treats the two publishers as one documented upstream chain.
5. Keeps the access refusal separate from a negative measurement.
6. Executes available arithmetic, leaves missing-data tests unperformed, and still delivers a finished report.
7. Avoids reusing Finland aircraft identities, dates, GNSS-specific thresholds or conclusions.
