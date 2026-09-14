#!/usr/bin/env python3
"""Check workflow/template consistency, local document links and JSON syntax."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


def main():
    root = Path(__file__).resolve().parents[1]
    errors = []
    files = [p for p in root.rglob('*') if p.is_file()
             and not any(part in {'.git', 'runs', '__pycache__'} for part in p.relative_to(root).parts)]
    for path in files:
        if path.suffix == '.json':
            try:
                json.loads(path.read_text())
            except (ValueError, UnicodeError) as exc:
                errors.append(f'{path.relative_to(root)}: invalid JSON: {exc}')
        if path.suffix == '.md':
            for target in re.findall(r'\[[^\]\n]*\]\(([^\s)]+)\)', path.read_text()):
                parsed = urlsplit(target.strip('<>'))
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                resolved = (path.parent / unquote(parsed.path)).resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    errors.append(f'{path.relative_to(root)}: unresolved local link {target}')
    workflow = json.loads((root / 'workflow.json').read_text())
    stages = workflow['stages']
    ids = [s['id'] for s in stages]
    expected = [f'P{i:02d}' for i in range(1, 13)]
    if ids != expected:
        errors.append('workflow must preserve P01–P12 order')
    seen_steps = set()
    for stage in stages:
        for dependency in stage['dependsOn']:
            if dependency not in ids[:ids.index(stage['id'])]:
                errors.append(f'{stage["id"]}: invalid dependency {dependency}')
        for step in stage['steps']:
            if step['id'] in seen_steps or not step['id'].startswith(stage['id'] + '.'):
                errors.append(f'duplicate or misassigned step {step["id"]}')
            seen_steps.add(step['id'])
            for field in ('action', 'method', 'artifact'):
                if not step.get(field):
                    errors.append(f'{step["id"]}: missing {field}')
    doc = (root / 'WORKFLOW.md').read_text()
    for step_id in seen_steps:
        if f'| {step_id} |' not in doc:
            errors.append(f'workflow document omits {step_id}')
    case = json.loads((root / 'templates/case.json').read_text())
    if [s['id'] for s in case['stages']] != ids:
        errors.append('case template stages do not match workflow')
    if any(s.get('executed') or s['status'] != 'not_started' for s in case['stages']):
        errors.append('blank case template claims execution')
    if any(case['execution'].values()):
        errors.append('blank case execution flags must be false')
    result = json.loads((root / 'templates/test-results.json').read_text())
    if result['executionStarted'] or result['results']:
        errors.append('blank result template must not contain executed results')
    print(json.dumps({'status': 'FAIL' if errors else 'PASS', 'filesChecked': len(files),
                      'stages': len(stages), 'steps': len(seen_steps), 'errors': errors}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
