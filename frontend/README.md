# Svelte frontend

The new browser-side frontend (SvelteKit in SPA mode, Svelte 5). It is built
step by step following the [rewrite plan](../plans/svelte-frontend-rewrite.md)
and talks to Python through the [JSON API](../docs/api.md). It is the live app:
Python serves the built files at `/`. The stack is in
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Setup

Use Node 24 via [fnm](https://github.com/Schniz/fnm) and npm (not bun or
pnpm). Do not install packages globally. Run every command from this folder.

```sh
fnm use        # picks Node 24 from .node-version
npm ci
```

## Develop

Run two servers:

1. Python, from the repository root: `uv run python src/main.py` (port 8080).
   Do not use your real `list.db`; set `DB_PATH` to a test file.
2. Svelte, from here: `npm run dev` (port 5173).

Open <http://localhost:5173/>. Vite reloads the page when you save a file.
It forwards `/api/…` requests to Python on 8080, so the browser sees one origin
and the room cookies work. The install manifests and icons come from Python
too.

## Build

```sh
npm run build
```

This writes static files to `build/` (ignored by version control). Restart the
Python server once after the first build; it then serves the app at
<http://localhost:8080/>. Later builds need no restart.

## Checks

```sh
npm run format && npm run lint && npm run check && npm run test && npm run build
```

- `format` / `lint`: Prettier and ESLint.
- `check`: TypeScript and Svelte type checks.
- `test`: Vitest unit tests (`src/**/*.test.ts`).
