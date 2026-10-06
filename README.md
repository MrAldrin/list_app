# ListR — shared lists

A mobile-first web app for small groups to share shopping and other lists.
Organize lists in password-protected rooms, add items, adjust quantities, use
tags, and see other users' changes in real time.

Built with a Svelte frontend, a Python FastAPI server, and SQLite; hosted on
Railway. See the [architecture](ARCHITECTURE.md).
**Anyone with a public list link can view and edit that list.** Room passwords
protect room controls, not public list links.

Switch between light and dark mode with the moon button, or from the ⋮ menu
on a list page. The choice is saved in that device's browser, not shared with other devices.

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

To test on a phone before deploying, see
[phone testing](docs/local-network-testing.md).

## Start the app

Build the frontend once, then start the server:

```bash
(cd frontend && npm run build)
uv run python src/main.py
```

Open <http://localhost:8080/admin> and sign in with `APP_PASSWORD` to find the
default room or create room invitations. Room access requires its own password;
admin login does not bypass it. Without a frontend build the server still
starts and logs a warning, but it does not serve the app.

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
uv run ruff format --check .
uv run ruff check .
```

Tests provide their own credentials and databases; they do not need your real
passwords. Tests run across 8 worker processes by default. Production
password-hashing settings remain unchanged.

Override the worker count on smaller machines, or run serially for debugging:

```bash
uv run pytest -q -n 2  # Two workers
uv run pytest -q -n 0  # Serial (also use this with --pdb)
```

Real-browser sharing tests (Chromium, Firefox and WebKit, disposable data):

```bash
uv run playwright install chromium firefox webkit
uv run pytest browser_tests -q -n 4
```

Setup, coverage, and diagnostics: [browser testing](docs/browser-testing.md).
Why eight workers and real password hashing: [test speed decision](docs/background/test-speed.md).

## Allium pilot (optional)

A [draft sharing behavior spec](docs/allium/public-sharing.allium) is available for
review alongside the [public-sharing guide](docs/public-sharing.md). It is a
small trial, not a replacement for the guide or pytest tests. The Pi skills are
installed locally under `.pi/skills/` (ignored by the current `.gitignore`);
`skills-lock.json` records their source. To set up another checkout, run
`npx skills add juxt/allium -a pi -s allium distill elicit propagate tend weed witness -y`,
then reload Pi. Install the optional CLI separately with
`cargo install allium-cli --locked`; validate the draft with
`allium check docs/allium/public-sharing.allium`. Review the draft's open
question before treating it as intended behavior. Do not run an autonomous
`/skill:allium` implementation loop without agreeing on the next step.

## Documentation

- [Architecture and security boundaries](ARCHITECTURE.md)
- [Deployment, backups, and recovery](docs/deployment.md)
- [Public list sharing](docs/public-sharing.md)
- [Room invitations](docs/room-invitations.md)
- [Hiding checked-off items](docs/checked-item-visibility.md)
- [Home-screen installation and device checks](docs/home-screen-installation.md)
- [Item writes and stale pages](docs/item-writes.md)
- [JSON API](docs/api.md)
- Testing: [real browsers](docs/browser-testing.md), [Android emulator](docs/android-emulator-testing.md), [phone over the network](docs/local-network-testing.md)
- [Remaining work](plans/backlog.md)

Background material (investigations, measurements, evidence) is in
[`docs/background/`](docs/background/).
