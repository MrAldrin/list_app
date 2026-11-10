#!/usr/bin/env bash
# Lead-requested overnight composition checks, not S3 feature evidence.
# No installs, source repair, formatting writes, browser matrix or provider calls.
set -u
ROOT=/home/hsa/projects/list_app-night-s3-review
EVIDENCE="$ROOT/docs/background/reminders-s3-scope-review-evidence"
cd "$ROOT" || exit 91
export UV_PROJECT_ENVIRONMENT=/home/hsa/projects/list_app/.venv
export PYTHON_DOTENV_DISABLED=1 DB_PATH=:memory:
export APP_PASSWORD=test-only-composition-check APP_RELOAD=false
export REMINDERS_ENABLED=false PUSH_ENABLED=false TZ=UTC
export PYTHONPATH="$ROOT/src:$ROOT/scripts:$ROOT/tests"
mkdir -p "$EVIDENCE/composition"
: > "$EVIDENCE/composition/exits.tsv"
check() {
  label="$1"; shift
  available=$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')
  if test "$available" -lt 6291456; then
    printf '%s\tRESOURCE_BLOCKED_BELOW_6_GIB\n' "$label" >> "$EVIDENCE/composition/exits.tsv"
    return 90
  fi
  {
    printf 'cwd=%s\nTZ=%s\n' "$PWD" "$TZ"
    printf 'command='; printf '%q ' "$@"; printf '\n'
    date -u
    "$@"
    result=$?
    date -u
    printf 'EXIT=%s\n' "$result"
    printf '%s\t%s\n' "$label" "$result" >> "$EVIDENCE/composition/exits.tsv"
  } > "$EVIDENCE/composition/$label.log" 2>&1
  return 0
}
check python-roots uv run --offline --no-sync python - <<'PY'
import importlib.util, json, pathlib, sys, pytest
root=pathlib.Path.cwd().resolve()
expected=pathlib.Path('/home/hsa/projects/list_app-night-s3-review')
assert root==expected
modules=['config','database_setup','server','reminders.identity','api.reminders','server_launcher']
origins={name:importlib.util.find_spec(name).origin for name in modules}
assert all(pathlib.Path(path).resolve().is_relative_to(root) for path in origins.values())
config=pytest.Config.fromdictargs({},[])
assert config.rootpath.resolve()==root
assert config.inipath.resolve()==root/'pyproject.toml'
print(json.dumps({'cwd':str(root),'executable':sys.executable,'module_origins':origins,'pytest_root':str(config.rootpath),'pytest_config':str(config.inipath),'testpaths':config.getini('testpaths'),'pythonpath':[str(p) for p in config.getini('pythonpath')],'addopts':config.getini('addopts')},indent=2))
config._ensure_unconfigure()
PY
if ! grep -qx $'python-roots\t0' "$EVIDENCE/composition/exits.tsv"; then exit 94; fi
check python-dependencies uv pip check --python "$UV_PROJECT_ENVIRONMENT/bin/python"
# Canonical frontend commands, using a copied matching existing node_modules.
cd "$ROOT/frontend" || exit 92
check node-roots node --input-type=module - <<'JS'
import {createRequire} from 'node:module';
import {realpathSync} from 'node:fs';
const require=createRequire(process.cwd()+'/package.json');
const resolved={cwd:process.cwd(),node:process.version,package:realpathSync('./package.json'),viteConfig:realpathSync('./vite.config.ts'),svelte:require.resolve('svelte/package.json'),vitest:require.resolve('vitest/package.json'),typescript:require.resolve('typescript/package.json')};
if(!Object.values(resolved).filter(v=>v.startsWith('/')).every(v=>v.startsWith('/home/hsa/projects/list_app-night-s3-review/frontend'))) throw new Error('Wrong frontend root');
console.log(JSON.stringify(resolved,null,2));
JS
if ! grep -qx $'node-roots\t0' "$EVIDENCE/composition/exits.tsv"; then exit 95; fi
check node-dependencies npm ls --depth=0
if ! grep -qx $'node-dependencies\t0' "$EVIDENCE/composition/exits.tsv"; then exit 96; fi
check frontend-lint npm run lint
check frontend-types npm run check
check frontend-build npm run build
export TZ=UTC
check frontend-units-utc npm test
export TZ=Europe/Oslo
check frontend-units-oslo npm test
cd "$ROOT" || exit 93
export TZ=UTC
check ruff-format-check uv run --offline --no-sync ruff format --check .
check ruff-check uv run --offline --no-sync ruff check .
check ty-check uv run --offline --no-sync ty check
check pytest uv run --offline --no-sync pytest -q --basetemp "$EVIDENCE/composition-temp"
printf 'Composition checks finished. Read composition/exits.tsv and per-command logs.\n'
