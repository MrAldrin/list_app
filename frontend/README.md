# Svelte frontend

The new browser-side frontend (SvelteKit in SPA mode, Svelte 5). It is built
step by step following the [rewrite record](../docs/background/svelte-frontend-rewrite.md)
and talks to Python through the [JSON API](../docs/api.md). It is the live app:
Python serves the built files at `/`. The stack is in
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Setup

Use Node 24 via [fnm](https://github.com/Schniz/fnm) and **Bun 1.4.4** for
package installation and Vite builds. Install that Bun version with the
[official installer](https://bun.sh/docs/installation). `packageManager` in
`package.json` records the version; it does not install or enforce it.
Do not install project packages globally. Run every command from this folder.

```sh
fnm use        # picks Node 24 from .node-version
bun --version  # must print 1.4.4
bun install --frozen-lockfile
```

Commit `bun.lock` after an approved dependency change. Do not create an npm,
pnpm or Yarn lockfile. A clean install needs no existing `node_modules`.
Bun runs the root `prepare` script; dependency install scripts follow Bun's
[trust rules](https://bun.sh/docs/pm/lifecycle). Do not trust more packages
without checking why their script is needed.

The build script explicitly runs Vite on Bun. Vitest stays on Node; other tool
CLIs also use their Node shebangs. Do not run Vitest with `--bun` or use
`bun test`: run **`bun run test`**.

### Dependency advisories

Run `bun audit` after installation and before proposing a dependency change.
It checks the lockfile against the npm advisory service and returns a nonzero
status for known vulnerabilities. `bun install` does not run this check.
Review findings; do not run `bun audit fix` or change versions without approval.

## Develop

Run two servers:

1. Python, from the repository root: `uv run python src/main.py` (port 8080).
   Do not use your real `list.db`; set `DB_PATH` to a test file.
2. Svelte, from here: `bun run dev` (port 5173).

Open <http://localhost:5173/>. Vite reloads the page when you save a file.
It forwards `/api/…` requests to Python on 8080, so the browser sees one origin
and the room cookies work. The install manifests and icons come from Python
too.

## Build

```sh
bun run build
```

This runs `bun --bun run vite build` and writes static files to `build/`
(ignored by version control). The `--bun` flag overrides Vite's Node shebang.
Restart the Python server once after the first build; it then serves the app at
<http://localhost:8080/>. Later builds need no restart.

## Local TypeScript server

The default build still makes static files for the Python server. To try the
Bun server locally, use a SQLite backup of a **test** database that Python has
already set up. Do not use the live database.

```sh
bun run build:ts
env DB_PATH=/absolute/path/to/test-copy.db APP_PASSWORD=test-only \
  LISTR_TS_ORIGIN=http://127.0.0.1:3000 bun --no-env-file build-ts/index.js
```

Open <http://127.0.0.1:3000/>. The server can write to the test copy. It does
not run migrations or forward missing routes to Python. Stop it with Ctrl-C.
See [TypeScript server checks](../docs/browser-testing.md#typescript-server)
for the available routes and automated checks. The pinned Bun adapter patch
sets security and cache headers even for assets that bypass SvelteKit hooks.
It also keeps a missing current worker file a 404.

## Checks

```sh
bun run format && bun run lint && bun run test:lint && bun run check && bun run test && bun run build
```

- `format`: Prettier.
- `lint`: Prettier checks, then Oxlint, then the remaining ESLint checks.
- `test:lint`: checks the lint configuration and its Svelte coverage.
- `check`: TypeScript and Svelte type checks.
- `test`: Vitest unit tests on Node (`src/**/*.test.ts`).
- `test:list`: list Vitest cases without running them.

Native lint rules live in `.oxlintrc.json`. ESLint reads that file through
`eslint-plugin-oxlint` to turn off duplicate checks in JavaScript and TypeScript.
Keep the Oxlint and plugin versions matched. ESLint still checks `.svelte`
files in full: Oxlint reads their scripts, not their template expressions.
Svelte rules that apply to plain scripts also stay in ESLint. Do not replace
`bun run lint` with Oxlint alone. See the [coverage review](../docs/background/oxlint-first.md).
