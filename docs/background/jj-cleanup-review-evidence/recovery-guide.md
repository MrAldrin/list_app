# Inspect the private recovery archive

This is an inspection guide, not permission to change the live repository.
Commands use Fish-compatible syntax. Keep the archive private: it contains native
repository history. It does not include the project `.env`, databases or caches.

## Check the retained file

```sh
sha256sum /home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/native-history.tar
```

Expected SHA-256:
`e703ef0567c351c41f195603656c297af08290d7063cafdf41181fa24ffb604d`.

The native snapshot operation is:
`f6e9450d01c4e22635b646e9038ac50980a99903124bfb7e5adc15f6a0cd878d59bf692b1032c78c83c8e49549299b02be248946281f3f58ac1328adf6ce226d`.

## Extract into a new private directory

Do not reuse an existing directory. The first `mkdir` must succeed before the
remaining steps. These commands do not modify the live repository.

```sh
mkdir -m 700 /tmp/jj-cleanup-recovery-view
mkdir -m 700 /tmp/jj-cleanup-recovery-view/home
mkdir -m 700 /tmp/jj-cleanup-recovery-view/repo
tar --no-same-owner -xf /home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/native-history.tar -C /tmp/jj-cleanup-recovery-view/repo
```

The archive holds `.jj` and `.git` together. Their relative store path must remain
unchanged. There are no object alternates or Git remotes. Do not connect this
copy to a remote or register it as a live source workspace.

**Do not launch sandbox jj from a live repository, even with `-R`.** jj can
load the current directory's config before it selects the `-R` repository.
A failed review demonstrated that this can change the live repo's config ID.

Before any jj launch, verify the physical sandbox paths: `.jj/repo` must be a
real directory, not a workspace pointer or symlink; the Git store must resolve
inside this extraction; no object alternates may exist. Reject any unexpected
path. Run Python in isolated mode from neutral `/tmp`, not a repository. This
check also saves only the names of the live user's per-repo config directories;
it does not read their contents. Do not proceed if it fails:

```sh
env -C /tmp python3 -I -c 'from pathlib import Path; import json; p=Path("/tmp/jj-cleanup-recovery-view/repo"); assert p.resolve()==p; r=p/".jj/repo"; assert r.is_dir() and not r.is_symlink(); s=r/"store"; g=(s/(s/"git_target").read_text().strip()).resolve(); assert g==p/".git"; assert not any(x.is_symlink() for x in p.rglob("*")); assert not (g/"objects/info/alternates").exists(); c=Path("/home/hsa/.config/jj/repos"); names=sorted(x.name for x in c.iterdir() if x.is_dir()) if c.exists() else []; Path("/tmp/jj-cleanup-recovery-view/config-names-before.json").write_text(json.dumps(names))'
```

Continue only if that check passes. Use `env -C` to set the **process's physical
cwd before jj starts**. Isolate HOME/config and clear inherited repository/config
overrides. `--ignore-working-copy` prevents snapshots. Explicit `--at-op` reads
the saved metadata, including the original visible alternatives. No `-R` is used.

```sh
env -C /tmp/jj-cleanup-recovery-view/repo -u JJ_CONFIG -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR -u GIT_ALTERNATE_OBJECT_DIRECTORIES -u GIT_CONFIG_PARAMETERS -u GIT_CONFIG_COUNT HOME=/tmp/jj-cleanup-recovery-view/home XDG_CONFIG_HOME=/tmp/jj-cleanup-recovery-view/home/config XDG_DATA_HOME=/tmp/jj-cleanup-recovery-view/home/data XDG_STATE_HOME=/tmp/jj-cleanup-recovery-view/home/state XDG_CACHE_HOME=/tmp/jj-cleanup-recovery-view/home/cache GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 jj --ignore-working-copy --at-op=f6e9450d01c4e22635b646e9038ac50980a99903124bfb7e5adc15f6a0cd878d59bf692b1032c78c83c8e49549299b02be248946281f3f58ac1328adf6ce226d log -r 'conflicts() | divergent()'
```

After the first jj inspection, compare live config-directory names from neutral
cwd. Stop and report any difference; do not delete an unfamiliar directory:

```sh
env -C /tmp python3 -I -c 'from pathlib import Path; import json; c=Path("/home/hsa/.config/jj/repos"); after=sorted(x.name for x in c.iterdir() if x.is_dir()) if c.exists() else []; before=json.loads(Path("/tmp/jj-cleanup-recovery-view/config-names-before.json").read_text()); assert after==before, "Live per-repo config directory names changed"'
```

The copy retains historical workspace names/commit targets. They are metadata,
not permission to operate on the corresponding old directories. Use only pinned,
read-only inspection here; never run workspace repair/update or a checkout that
could reach another live directory. The recovery tests traced every restored
source lookup and found no live repository/workspace/archive path access.

## Evidence of tested restoration

The test extracted a copy, simulated sets A/B there, then extracted the original
archive again to a different directory. The second extraction matched all 988
native visible metadata records and 1,024 exact source/conflict tree fingerprints.
This includes 36 old exact resume commits, both divergent alternatives, all three
conflicts, paused manual WIP, protected bookmarks and workspace commit targets.
See `recovery-receipt.json`, `restore-final-receipt.json` and
`recovery-tree-fingerprints.json` beside this guide.

For live recovery, select exact commits and intended destination with the owner,
then review and test that specific import in isolation. Native copy inspection
is proven; a live import/rebase or feature repair is not authorized or tested by
this guide. Do not use broad operation restore in the active shared repository.
