# Local helpers

The executable collection and screening pipeline is documented in [the pipeline guide](../docs/PIPELINE.md). Its entry point is `python3 -m satresearch`; it is separate from the case-document helpers below. `prepare_collector_service.py` creates a reviewable macOS service file and does not install or start it.

These scripts use Python **3.9 or newer** and its standard library. They do not contact GEV, fetch external data or execute the scientific analysis automatically. The model chooses the appropriate domain methods and records their actual execution.

## Initialize a run

```sh
python3 scripts/init_case.py case-name --question "The new investigation question"
```

Optional `--domain` records a domain label; `--output-root` chooses a different parent directory. Existing runs are never overwritten. The generated files retain unknown scope values and false execution flags until actual work occurs.

## Check repository consistency

```sh
python3 scripts/validate_repo.py
```

This checks JSON syntax, local documentation links, phase/step IDs and blank-template consistency. It does not validate the truth of an investigation, remote source availability, hypothesis logic or every field in a filled run. Follow the schema notes and audit the case evidence separately.

## Hash reviewed evidence

```sh
python3 scripts/build_manifest.py runs/case-name --output runs/case-name/manifest.json
```

This records SHA-256 and byte counts for each regular file, excluding the manifest itself. It refuses symlinks. Review the directory for secrets, personal data, unrelated files and publication permissions before sharing; hashing does not perform that review or authorize publication. Preserve the manifest alongside the evidence and verify extracted archive bytes when packaging.
