#!/usr/bin/env bash
set -eu
cd /home/hsa/projects/list_app-night-s3-review
python3 - <<'PY'
import csv
import hashlib
import json
import pathlib
import subprocess
import time

root = pathlib.Path.cwd()
out = root / 'docs/background/reminders-s3-scope-review-evidence'
archive = pathlib.Path('/home/hsa/projects/reminders-archive')
before = json.loads((out / 'protection-before.json').read_text())
def jj(*args):
    return subprocess.check_output(['jj', '--ignore-working-copy', *args], text=True)
def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        while data := file.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()
started = time.time()
rows = list(csv.DictReader((out / 'archive-before.tsv').open(), delimiter='\t'))
files = {str(p.relative_to(archive)) for p in archive.rglob('*') if p.is_file()}
expected = {row['path'] for row in rows}
failures = []
checked_bytes = 0
for row in rows:
    path = archive / row['path']
    if not path.is_file() or path.stat().st_size != int(row['bytes']) or digest(path) != row['sha256']:
        failures.append({'kind': 'archive-bytes', 'path': row['path']})
    checked_bytes += int(row['bytes'])
if files != expected:
    failures.append({'kind': 'archive-file-set', 'added': sorted(files-expected), 'missing': sorted(expected-files)})
bookmarks = jj('bookmark', 'list', '--all-remotes')
workspaces = jj('workspace', 'list')
conflicts = jj('log', '-r', 'conflicts()', '--no-graph', '-T', 'commit_id ++ "\n"')
divergent = jj('log', '-r', 'divergent()', '--no-graph', '-T', 'commit_id ++ "\n"')
checks = {
    'all_bookmark_targets_unchanged': bookmarks == before['bookmarks'],
    'other_workspace_revisions_unchanged': [s for s in workspaces.splitlines() if not s.startswith('night-s3-review:')] == [s for s in before['workspaces'].splitlines() if not s.startswith('night-s3-review:')],
    'conflict_identities_unchanged': set(conflicts.splitlines()) == set(before['conflicts'].splitlines()),
    'divergent_identities_unchanged': set(divergent.splitlines()) == set(before['divergent'].splitlines()),
}
for name, passed in checks.items():
    if not passed:
        failures.append({'kind': name})
refs = {}
for commit in before['source_commits']:
    resolved = jj('log', '-r', commit, '--no-graph', '-T', 'commit_id').strip()
    refs[commit] = resolved
    if resolved != before['source_commits'][commit]:
        failures.append({'kind': 'resume-ref', 'commit': commit})
fingerprints = []
for item in json.loads((out / 'protected-source-fingerprints.json').read_text()):
    tree = jj('file', 'list', '-r', item['commit'], '-T', 'path ++ "\t" ++ file_type ++ "\t" ++ executable ++ "\t" ++ normal_value ++ "\n"')
    actual = {'commit': item['commit'], 'sha256': hashlib.sha256(tree.encode()).hexdigest(), 'entries': len(tree.splitlines())}
    fingerprints.append(actual)
    if actual != item:
        failures.append({'kind': 'source-tree-fingerprint', 'commit': item['commit']})
result = {'root': str(root), 'elapsed_seconds': round(time.time()-started, 2), 'archive_files_checked': len(rows), 'archive_bytes_checked': checked_bytes, 'archive_file_set_unchanged': files == expected, 'checks': checks, 'bookmarks': bookmarks, 'workspaces': workspaces, 'conflicts': conflicts, 'divergent': divergent, 'exact_resume_refs_checked': len(refs), 'source_commits': refs, 'protected_trees_checked': len(fingerprints), 'protected_tree_fingerprints': fingerprints, 'failures': failures, 'pass': not failures}
(out / 'protection-after.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k: result[k] for k in ('elapsed_seconds','archive_files_checked','archive_bytes_checked','checks','exact_resume_refs_checked','protected_trees_checked','failures','pass')}, indent=2))
raise SystemExit(bool(failures))
PY
