# ListR — shared lists

A mobile-first web app for small groups to share shopping and other lists.
Organize lists in password-protected rooms, add items, adjust quantities, use
tags, and see other users' changes in real time.

Built with Python, NiceGUI, and SQLite; hosted on Railway.
**Anyone with a public list link can view and edit that list.** Room passwords
protect room controls, not public list links.

Use the moon button at the top right to switch between light and dark mode.
The choice is saved in that device's browser, not shared with other devices.

## Local setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use
Python 3.13 or newer. From the repository root:

```bash
uv sync
cp .env.example .env
```

If you already have a `.env`, keep it instead of running the copy command.
Edit `.env` and replace both required placeholders. Generate a separate random
value for each with:

```bash
uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

- `APP_PASSWORD`: admin password and initial password for the default `Home` room.
  Changing it later does not change existing room passwords.
- `NICEGUI_STORAGE_SECRET`: private key for NiceGUI session storage; keep it stable
  across restarts. It is not a room password.
- `.env` is ignored by version control. Never commit passwords, keys, or databases.

## Start the app

```bash
uv run python src/main.py
```

Open <http://localhost:8080/admin> and sign in with `APP_PASSWORD` to find the
default room or create room invitations. Room access requires its own password;
admin login does not bypass it.

The default database is `list.db` in the repository root, regardless of the
startup directory. Optional `DB_PATH` overrides it. The port defaults to `8080`;
set `PORT` or override it with `uv run python src/main.py --port 8081`.

For automatic restarts after local code edits, set `APP_RELOAD=true` in `.env`
(already included in `.env.example`). See the [deployment guide](docs/deployment.md)
for configuration and production behavior.

The server listens on all network interfaces. Use it only on a trusted network
during development.

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

Real-browser sharing tests (Chromium and Firefox, disposable data):

```bash
uv run playwright install chromium firefox
uv run pytest browser_tests -q -n 0
```

Setup, coverage, and diagnostics: [browser testing](docs/browser-testing.md).

Benchmark results and trade-offs: [test speed experiments](plans/test-speed-experiments.md).

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

- [Deployment, backups, and recovery](docs/deployment.md)
- [Room invitations](docs/room-invitations.md)
- [Hiding checked-off items](docs/checked-item-visibility.md)
- [Home-screen installation and device checks](docs/home-screen-installation.md)
- [Architecture and security boundaries](ARCHITECTURE.md)
- [Remaining work](plans/backlog.md)
