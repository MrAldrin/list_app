# Architecture: Shared Shopping List App

## Purpose

ListR is a mobile-first shared list app for small groups. People add items,
mark them done, and organize/filter lists. The MVP prioritizes simplicity and
learning, targeting up to four simultaneous users rather than large-scale use.

## Core architecture decisions

- **Frontend:** Svelte 5 with SvelteKit as a single-page app (SPA), built to
  static files in `frontend/build/`. The browser runs the UI. See the
  [frontend guide](frontend/README.md).
- **Backend:** Python FastAPI with a JSON API under `/api/v1` (contract in
  [docs/api.md](docs/api.md)). Live updates reach open pages through
  Server-Sent Events (a one-way stream from server to browser).
- **One process, one origin:** uvicorn runs FastAPI, which also serves the
  built frontend at `/`. There is no second server and no CORS.
- **Storage:** SQLite, with one application instance using one database.
  Schema changes use a small own migration runner, not Alembic, which would
  add SQLAlchemy.
- **Hosting:** Railway with persistent volume storage, built from the root
  `Dockerfile`. Deployment configuration, process limits, and recovery
  procedures belong in the [deployment guide](docs/deployment.md).
- **Offline:** read-only viewing of saved data is built and awaiting owner
  review; editing offline is not supported. Editing can be added in stages (see
  [offline viewing](docs/offline-viewing.md) and the
  [migration plan](plans/offline-frontend-migration.md)). Discuss other stack
  changes before implementation.

## Domain and security boundaries

- **Room:** A password-protected workspace containing lists. Shared room access
  grants management rights; there are no individual owner/member accounts.
- **List:** Belongs to a room. Its `/share/{token}` URL grants public view/edit
  access using a high-entropy token, but not room management. Authorized room
  members can reset the link to revoke it for everyone. `/list/{slug}` is
  room-authorized navigation, not public access. See [public sharing](docs/public-sharing.md).
  The share page reveals nothing about the room unless the browser also has
  room access.
- **Item:** A list entry, with completion state and optional details/tags for
  organization. Field-level schema details may evolve.
- **Admin:** `/admin` requires the global app password. A nonblank `APP_PASSWORD`
  is required before opening the database; there is no password-free fallback.
  Admins can view the room overview and reset passwords, so rooms are not private
  from the server administrator. Admin login or `?admin=true` alone does not
  grant entry to a room. Admin sign-in has its own signed, HTTP-only cookie
  (`__Host-` on HTTPS). It is stateless, and a changed `APP_PASSWORD` ends all
  admin sessions. See [API: Admin](docs/api.md#admin).
- **Room authorization:** Entry requires the room password or a valid token
  issued after checking it. Private reads and operations revalidate access;
  cached UI state is not authorization. Password changes revoke old tokens.
  The token lives in an HTTP-only room cookie (`__Host-`, Secure on HTTPS);
  JavaScript never sees it and the password is never stored. Plain HTTP
  (local testing) uses a cookie without `Secure`.
- **Same-origin writes:** Every API write must come from a page of this exact
  origin and send JSON. CORS is never enabled. The live streams are plain
  same-origin GET requests with the same cookie checks.
- **Creation invitations:** Authenticated admins issue reusable, expiring,
  revocable invitations to create rooms. Invitations never grant access to
  existing rooms; expiry/revocation does not affect rooms already created.
  See [room invitations](docs/room-invitations.md).

Token storage, revocation and cookie details are in the
[remembered-access guide](docs/home-screen-installation.md).
An unauthorized room visitor sees a password prompt, including when navigating
back from a public list.

## Code boundaries

- `src/main.py`: Entry point; runs uvicorn.
- `src/server.py`: `create_app()` builds the FastAPI app (API, old install
  routes, static files, then the Svelte app last).
- `src/api/`: JSON API under `/api/v1`; the contract is in
  [docs/api.md](docs/api.md).
- `src/svelte_frontend.py`: Serves the built Svelte app at `/`, with the old
  page addresses and `/app/...` redirects.
- `src/pwa_routes.py`: Home-screen install manifests and icons, plus the
  `/sw.js` kill switch (below). `src/install_manifest.py` builds the manifests.
- `src/database_setup.py`: SQLite schema and the list of migrations.
- `src/migrations.py`: versioned migration runner and pre-migration backup.
- `src/database_crud.py`: Database reads/writes and persisted authorization.
- `src/item_service.py`: Item business rules over database operations.
- `src/room_cookies.py` and `src/admin_access.py`: Room cookie rules and the
  admin cookie.
- `src/room_invitations.py`: Invitation logic.
- `src/live_updates.py`: Wakes open API live streams when a room changed.

Business rules live in Python. The frontend never copies them.

## Major UX decisions

- Prioritize quick list editing on mobile, with changes reflected for other
  connected users through the live stream.
- The add field creates a new item, leaves an existing active item unchanged,
  or unchecks an existing completed item, with feedback to the user.
- Each list can hide checked-off items immediately, after a full-24-hour age, or
  except for the last N checked items. Hiding does not remove items from search or
  matching; see [checked-item visibility](docs/checked-item-visibility.md).
- Room and list names are shown exactly as typed, with only outer spaces
  removed. Duplicate list names are compared ignoring case. Item names are
  stored in lowercase so duplicate items are easy to catch.
- `/` is a public remembered-room router; admin tools remain separate at `/admin`.
- Home-screen installation requests the current room as its launch address,
  without credentials. ListR remains one installed app identity, not one per room;
  switching rooms does not deliberately retarget the installed icon.
- Installation never grants access. Sign-in carries over only where the browser
  copies cookies into the installed app. See
  [home-screen installation](docs/home-screen-installation.md).
- Offline viewing is read-only: a service worker caches the app shell and the
  browser stores the last server snapshot. Editing offline is not supported. See
  [offline viewing](docs/offline-viewing.md); an earlier experiment was rolled
  back ([findings](docs/background/offline-findings.md)).
- Old phone installs still hold the earlier app's service worker. `/sw.js`
  answers with a script that removes that worker and its caches (a kill
  switch). It must never return 404 or the app page. See
  [home-screen installation](docs/home-screen-installation.md).

## Evolution and documentation

This document is the source of truth for high-level architecture. If code differs,
flag it and agree whether to change the implementation or update the decision.
Keep current operational details in `docs/`, supporting evidence and history in
`docs/background/`, proposed work in `plans/`, and unfinished work in the
[backlog](plans/backlog.md). Follow the documentation
lifecycle in [AGENTS.md](AGENTS.md).
