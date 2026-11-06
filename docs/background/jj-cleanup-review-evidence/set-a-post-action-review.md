# Set A independent static receipt audit: PASS

The 43 indexed private files matched their indexed paths, byte counts and SHA-256 values. Ten state receipts independently matched the before inventory (including full descriptions) and complete Git fingerprint/tree maps, minus exactly the cumulative selected IDs. The checks included all physical-OID flags and the separately marked synthetic zero root. All protected fields, 67 tree hashes, head sets, operation links, status receipts, commands and counts passed as detailed below.

Static limits: these checks validate recorded receipts, not native metadata reads, a restoration, an independent tree readback, remote operations or garbage collection. The execution receipt reports no B/remotes/bookmark cleanup, rebase or GC; unchanged inventory and refs and recorded commands are consistent with that report, but cannot establish absence of unrecorded operations. The receipt reports 36 archived trees and 11 retired readbacks matching the prior unchanged archive SHA; this was not independently rerun. The prior reviewer capability block was not a repository failure. No jj or Git commands were run, no repository or input files were edited, and no tests were run. The only write was this routed artifact. Model tier was not self-verified.

## Main audit command actually run

```sh
python3 -I -B <<'PY'
import json, pathlib, hashlib
base = pathlib.Path('docs/background/jj-cleanup-review-evidence')
raw = pathlib.Path('/home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/set-a-20261106')
def load(p): return json.loads(p.read_bytes())
index = load(base/'set-a-receipt-index.json')
assert index['private_phase_directory'] == str(raw)
entries = index['files']; names = [e['path'] for e in entries]
assert len(names) == len(set(names)) == 43
for e in entries:
 p = pathlib.PurePosixPath(e['path']); assert not p.is_absolute() and '..' not in p.parts
 b = (raw/p).read_bytes(); assert len(b) == e['bytes'] and hashlib.sha256(b).hexdigest() == e['sha256'], e['path']
print('receipt paths/bytes/SHA-256: 43/43')
manifest = load(base/'proposed-exact-sets.json'); a = next(x for x in manifest if x['phase']=='A-empty-review')
ids = [x['commit'] for x in a['commits']]; assert len(ids)==len(set(ids))==11
pre = load(base/'set-a-preflight.json'); ex = load(base/'set-a-execution.json')
assert pre == load(raw/'preflight.json') and ex == load(raw/'execution.json')
assert ids == ex['exact_removed_commits'] == [x['commit'] for x in pre['candidates']]
commands = [['jj','abandon','-r',i] for i in ids[:9]] + [['jj','abandon','-r',ids[9],'-r',ids[10]]]
assert pre['commands'] == commands and len(ex['steps']) == 10
before = load(raw/'before.json'); inv = before['inventory']; objects = before['complete_git_commit_objects']; zero='0'*40
assert len(inv)==len(objects)==992 and set(inv)==set(objects) and len(before['heads'])==28
assert objects[zero]=={'native_synthetic_root_no_git_object':True}
assert all(v.get('physical_commit_oid_verified') is True and 'git_commit_body_sha256' in v and 'git_tree_id' in v for k,v in objects.items() if k!=zero)
assert len(before['protected_tree_sha256'])==67 and len(before['conflicts'])==3 and len(before['divergent'])==4
fields = ['bookmarks','tags','workspaces','workspace_commits','held_commits','critical_refs','working_tree','conflicts','divergent','config_id','original_config_metadata_sha256','archive_resume_sha256','protected_tree_sha256']
def heads(d):
 return set(d) - {p for v in d.values() for p in v['parents']}
assert heads(inv)==set(before['heads'])
assert pre['operation']==before['operation']
previous=before['operation']; removed=set(); parent_heads=set(); checked=0
for i, step in enumerate(ex['steps'],1):
 cmd=load(raw/f'step-{i:02}-command.json'); state=load(raw/f'step-{i:02}-state.json'); clean=load(raw/f'clean-status-step-{i:02}.json')
 assert cmd==step and step['step']==i and step['command']==commands[i-1] and step['exit']==0
 assert step['pre_operation']==previous and step['post_operation']==state['operation'] and step['post_operation']!=previous
 previous=step['post_operation']; selected=ids[i-1:i] if i<10 else ids[9:11]; removed.update(selected)
 assert set(step['removed_total'])==removed
 assert clean['command']==['jj','status'] and clean['exit']==0 and clean['stdout'].startswith('The working copy has no changes.\n') and clean['stderr']==''
 expected_inv={k:v for k,v in inv.items() if k not in removed}; expected_obj={k:v for k,v in objects.items() if k not in removed}
 assert state['inventory']==expected_inv and state['complete_git_commit_objects']==expected_obj
 assert all(state[f]==before[f] for f in fields)
 assert all(v.get('physical_commit_oid_verified') is True for k,v in state['complete_git_commit_objects'].items() if k!=zero)
 assert state['complete_git_commit_objects'][zero]=={'native_synthetic_root_no_git_object':True}
 h=heads(state['inventory']); assert h==set(state['heads']) and len(h)==28-i==step['heads_after']
 assert len(state['inventory'])==992-len(removed)==step['visible_after']
 parent_heads.update(p for k in selected for p in inv[k]['parents'] if p not in removed)
 assert not (h & parent_heads) and not any(p in removed for v in state['inventory'].values() for p in v['parents'])
 checked+=len(state['inventory'])
assert load(raw/'after.json')==state and ex['post_operation']==previous
assert set(pre['predicted_heads'])==set(state['heads'])
assert len(state['inventory'])==981 and len(state['heads'])==18
bids={x['commit'] for x in next(x for x in manifest if x['phase']=='B-alternates')['commits']}; assert bids <= set(state['inventory'])
print('manifest/preflight/execution: 11 exact IDs; 9 single + 1 joint command; 10 zero exits; 10 operation links; 10 clean statuses')
print('inventory and full Git fingerprint/tree maps: 10/10 states,',checked,'retained entries compared; 991 physical + 1 synthetic before, 980 + 1 after')
print('protected fields:',len(fields)*10,'comparisons; 67 tree hashes each state; 10 exact head sets; no exposed parents or surviving children')
print('after equals step 10; visible 992 -> 981; heads 28 -> 18; conflicts 3; divergent 4; B IDs retained')
print('static receipts report 36 archived trees and 11 retired readbacks; archive SHA:',ex['durable_archive_sha256_unchanged'])
print('PASS: static checks only')
PY
```

Actual output:

```text
receipt paths/bytes/SHA-256: 43/43
manifest/preflight/execution: 11 exact IDs; 9 single + 1 joint command; 10 zero exits; 10 operation links; 10 clean statuses
inventory and full Git fingerprint/tree maps: 10/10 states, 9864 retained entries compared; 991 physical + 1 synthetic before, 980 + 1 after
protected fields: 130 comparisons; 67 tree hashes each state; 10 exact head sets; no exposed parents or surviving children
after equals step 10; visible 992 -> 981; heads 28 -> 18; conflicts 3; divergent 4; B IDs retained
static receipts report 36 archived trees and 11 retired readbacks; archive SHA: e703ef0567c351c41f195603656c297af08290d7063cafdf41181fa24ffb604d
PASS: static checks only
```

Two preliminary bounded `python3 -I -B` heredocs inspected receipt schemas and the zero-root record before writing the main check. They only read the allowed `before.json`, `step-01-command.json`, and `clean-status-step-01.json`; the zero root was `{'native_synthetic_root_no_git_object': True}`. No input code was executed.
