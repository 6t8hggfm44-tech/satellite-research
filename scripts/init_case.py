#!/usr/bin/env python3
"""Create a blank, isolated investigation; never fetch data or overwrite a run."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_id', help='Lowercase letters, digits and hyphens')
    parser.add_argument('--question', required=True)
    parser.add_argument('--domain', default=None)
    parser.add_argument('--output-root', type=Path, default=None)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', args.case_id):
        parser.error('case_id must be 1–80 lowercase letters, digits or hyphens, starting with a letter or digit')
    if not args.question.strip():
        parser.error('question must not be blank')
    repo = Path(__file__).resolve().parents[1]
    workflow = json.loads((repo / 'workflow.json').read_text())
    target = (args.output_root or repo / 'runs') / args.case_id
    if target.exists():
        parser.error('run already exists; resume it instead of overwriting it')
    now = datetime.now(timezone.utc).isoformat()
    prepared = {}
    for src in sorted((repo / 'templates').iterdir()):
        if src.name.startswith('_') or not src.is_file():
            continue
        content = src.read_text()
        if src.suffix == '.json':
            data = json.loads(content)
            if src.name == 'case.json':
                data.update(id=args.case_id, userRequest=args.question, domain=args.domain,
                            workflowVersion=workflow['workflowVersion'], createdAtUTC=now, updatedAtUTC=now)
            else:
                data['caseId'] = args.case_id
                if 'workflowVersion' in data:
                    data['workflowVersion'] = workflow['workflowVersion']
            content = json.dumps(data, indent=2) + '\n'
        prepared[src.name] = content
    target.mkdir(parents=True, exist_ok=False)
    for name, content in prepared.items():
        (target / name).write_text(content)
    (target / 'README.md').write_text(
        '# Investigation run\n\n'
        f'Case: `{args.case_id}`. Workflow version: `{workflow["workflowVersion"]}`.\n\n'
        'The templates have been initialized. No evidence has been acquired, no test has '
        'been executed, and no hypothesis has been accepted. Read the repository AGENTS.md, '
        'WORKFLOW.md and templates/_schema-notes.md before filling these records. '
        'Keep raw evidence separate from derivatives and record a plan before testing.\n')
    print(json.dumps({'caseId': args.case_id, 'path': str(target.resolve()),
                      'files': len(prepared) + 1, 'testsExecuted': False}, indent=2))


if __name__ == '__main__':
    main()
