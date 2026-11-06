# ListR — shared lists

A mobile-first web app for small groups to share shopping and other lists.
Organize lists in password-protected rooms, add items, adjust quantities, use
tags, and see other users' changes in real time.

Built with a Svelte frontend, a Python FastAPI server, and SQLite; hosted on
Railway. See the [architecture](ARCHITECTURE.md).
**Anyone with a public list link can view and edit that list.** Room passwords
protect room controls, not public list links.

Switch between light and dark mode with the moon button or **Dark mode** in the
⋮ menu on room and list pages. Choose a color theme under **Appearance** in the
same menu: Classic, Nord, Solarized, Gruvbox, Catppuccin or Rosé Pine. Each theme
has light and dark colors. The app saves both choices in that device's browser.
It does not share them with other devices.

Scope and approval rules: [scope](docs/scope.md). Task status lives in local
[Beads](docs/beads.md); the [backlog entry point](plans/backlog.md#current-focus)
links the agenda. Native Ready does not approve work.

## Local setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use
Python 3.13 or newer. For the frontend, use Node 24 via
[fnm](https://github.com/Schniz/fnm) and npm. From the repository root:

```bash
uv sync
cp .env.example .env
(cd frontend && fnm use && npm ci)
```

If you already have a `.env`, keep it instead of running the copy command.
Edit `.env` and replace the required placeholder. Generate a random value
with:

```bash
uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

- `APP_PASSWORD`: admin password and initial password for the default `Home` room.
  Changing it later does not change existing room passwords.
- `.env` is ignored by version control. Never commit passwords, keys, or databases.

### New jj workspace

A jj workspace gets its own copy of tracked files only. Ignored files such as
`.env`, `list.db` and `.venv` are not copied:

- `.env`: share the main workspace's file with a symlink. From the new workspace:

  ```bash
  ln -s ../list_app/.env .env
  ```

- `.venv`: `uv` creates it on the first `uv run`.
- `frontend/node_modules`: run `npm ci` in `frontend/`. `frontend/build/` is
  also not copied; build it again (see below).
- `list.db`: the app creates an empty database on first start. Each workspace
  keeps its own test data; do not symlink the main workspace's database.

Testing on a phone before deploying is optional and rarely needed; see
[phone testing](docs/local-network-testing.md).

## Start the app

Build the frontend once, then start the server:

```bash
(cd frontend && npm run build)
uv run python src/main.py
```

Open <http://localhost:8080/admin> and sign in with `APP_PASSWORD` to find the
default room or create room invitations. Room access still requires its own
password; admin login does not bypass it. The server starts without a frontend
build and logs a warning, but it does not serve the app.

The default database is `list.db` in the repository root, regardless of the
startup directory. Optional `DB_PATH` overrides it. The port defaults to `8080`;
set `PORT` or override it with `uv run python src/main.py --port 8081`.

For automatic restarts after local code edits, set `APP_RELOAD=true` in `.env`
(already included in `.env.example`). See the [deployment guide](docs/deployment.md)
for configuration and production behavior.

The server listens on all network interfaces. Use it only on a trusted network
during development.

## Develop the frontend

Run two servers: Python as above (port 8080), and `npm run dev` in `frontend/`
(port 5173). Open <http://localhost:5173/>; Vite forwards `/api` to Python.
Setup and checks: [frontend guide](frontend/README.md).

To try the built app on a phone with a test database, run
`uv run python scripts/serve_svelte_local.py`
([phone testing](docs/local-network-testing.md)).

## Tests and code checks

```bash
uv run pytest -q
```

Before a change is done, run the full [Python quality checks](AGENTS.md#python-quality-checks).

Tests provide their own credentials and databases; they do not need your real
passwords. Tests run across 8 worker processes by default. Production
password-hashing settings remain unchanged.

Override the worker count on smaller machines, or run serially for debugging:

```bash
uv run pytest -q -n 2  # Two workers
uv run pytest -q -n 0  # Serial (also use this with --pdb)
```

Real-browser tests (Chromium, Firefox and WebKit) are a separate suite. Setup,
commands, coverage and diagnostics: [browser testing](docs/browser-testing.md).
Why eight workers and real password hashing: [test speed decision](docs/background/test-suite-speed.md#worker-and-hashing-decision).

## Allium pilot (optional)

A small spec trial. Setup and status: [Allium pilot](docs/allium/README.md).

## Repository map

| Path                               | Purpose                                                                            |
| ---------------------------------- | ---------------------------------------------------------------------------------- |
| `src/`                             | Python server. `main.py` is the entry point.                                       |
| `frontend/`                        | Svelte app, built to `frontend/build/`.                                            |
| `tests/`                           | Pytest suite.                                                                      |
| `browser_tests/`, `android_tests/` | Real-browser and Android emulator suites.                                          |
| `scripts/`                         | Helpers: deploy with backup, phone serving, test data, icons.                      |
| `docs/`                            | Current behavior, contracts and guides. Evidence in `docs/background/`.            |
| `plans/`                           | The [task entry point](plans/backlog.md) and supporting detail for larger items. |

## Documentation

Start with the [documentation hub](docs/index.md) for current behavior, API,
operations, testing, and planning. The root [architecture](ARCHITECTURE.md) is
the authority for the stack and major decisions. Background research lives in
`docs/background/`; it is evidence, not current guidance.

### Documentation preview (local only)

Zensical builds the maintained Markdown directly, including the root
`ARCHITECTURE.md`; there is no second architecture copy. Install the development
dependencies with `uv sync`, then build and serve the static preview from the
repository root:

```bash
uv run python scripts/build_docs_site.py
python3 -m http.server --bind 127.0.0.1 --directory site 8000
```

Open <http://127.0.0.1:8000/>. Stop the local server with Ctrl-C. The build
wrapper makes a temporary staging tree of individual file symlinks to the
allowed maintained documentation sources. It builds the site from that tree.
It does not copy or move the maintained source files. The wrapper rejects unsafe
source/output paths and symlinks. It discovers excluded pages, writes
fragment-free redirects, and checks generated links. Treat `zensical.toml` as
trusted project code; its exclusions are not a security boundary. Review
generated output after changing preview configuration or source files. The
`site/` directory is ignored. The preview excludes
`docs/local-network-testing.md` and all of `docs/background/`; source files stay
unchanged. Links to excluded pages redirect to a site-specific exclusions
notice. Other operational guides and planning proposals remain included. This
local preview is not approval to publish or expose the site. See the hub for
content and privacy limits.

The preview is a manual snapshot. After you edit documentation or its
configuration, rerun `uv run python scripts/build_docs_site.py` and reload the
browser page. The local HTTP server does not watch maintained sources or rebuild
the preview automatically.
