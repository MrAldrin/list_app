# Architecture: Shared Shopping List App

## Purpose

ListR is a mobile-first shared list app for small groups. People add items,
mark them done, and organize/filter lists. The MVP prioritizes simplicity and
learning, targeting up to four simultaneous users rather than large-scale use.

## Core architecture decisions

- **Frontend/backend:** Python with NiceGUI, serving the UI and application logic
  together, with live updates between connected users.
- **Storage:** SQLite, with one application instance using one database.
  Schema changes use a small own migration runner, not Alembic, which would
  add SQLAlchemy.
- **Hosting:** Railway with persistent volume storage. Deployment configuration,
  process limits, and recovery procedures belong in the
  [deployment guide](docs/deployment.md).

Keep this stack for current small improvements. The agreed future direction is a
browser-side frontend with a Python API, introduced in stages so offline viewing
can evolve into offline editing without replacing the interface again. The chosen
frontend is Svelte 5 with SvelteKit in static/SPA mode, built on a separate branch
following the [rewrite plan](plans/svelte-frontend-rewrite.md); see the
[migration plan](plans/offline-frontend-migration.md) for the reasons. SQLite and Railway need not
change for this direction. Discuss other stack changes before implementation.

## Domain and security boundaries

- **Room:** A password-protected workspace containing lists. Shared room access
  grants management rights; there are no individual owner/member accounts.
- **List:** Belongs to a room. Its `/share/{token}` URL grants public view/edit
  access using a high-entropy token, but not room management. Authorized room
  members can reset the link to revoke it for everyone. `/list/{slug}` is
  room-authorized navigation, not public access. See [public sharing](docs/public-sharing.md).
- **Item:** A list entry, with completion state and optional details/tags for
  organization. Field-level schema details may evolve.
- **Admin:** `/admin` requires the global app password. A nonblank `APP_PASSWORD`
  is required before opening the database; there is no password-free fallback.
  Admins can view the room overview and reset passwords, so rooms are not private
  from the server administrator. Admin login or `?admin=true` alone does not
  grant entry to a room.
- **Room authorization:** Entry requires the room password or a valid token
  issued after checking it. Private reads and operations revalidate access;
  cached UI state is not authorization. Password changes revoke old tokens.
  Browser storage remembers tokens, never room passwords. HTTPS uses secure,
  HTTP-only cookies, with localStorage fallback for HTTP or unavailable cookies.
  Cookie writes and Socket.IO handshakes enforce same-origin checks.
- **Creation invitations:** Authenticated admins issue reusable, expiring,
  revocable invitations to create rooms. Invitations never grant access to
  existing rooms; expiry/revocation does not affect rooms already created.
  See [room invitations](docs/room-invitations.md).

Token storage, revocation and cookie details are in the
[remembered-access guide](docs/home-screen-installation.md).
An unauthorized room visitor sees a password prompt, including when navigating
back from a public list.

## Code boundaries

- `src/main.py`: Entry point, routes, UI composition, and live-update wiring.
- `src/database_setup.py`: SQLite schema and the list of migrations.
- `src/migrations.py`: versioned migration runner and pre-migration backup.
- `src/database_crud.py`: Database reads/writes and persisted authorization.
- `src/item_service.py`: Item business rules over database operations.
- `src/room_access.py` and `src/room_cookies.py`: Private-page authorization
  context and the HTTPS remembered-access bridge.
- `src/room_invitations.py` and `src/ui/`: Invitation logic and extracted UI helpers.
- `src/svelte_frontend.py`: Serves the built Svelte prototype under `/app/`.

UI and service logic are not yet fully separated; splitting `src/main.py` is
deferred in the [backlog](plans/backlog.md).

## Major UX decisions

- Prioritize quick list editing on mobile, with changes reflected for other
  connected users.
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
- Offline use is not supported. An earlier read-only experiment was rolled back
  (see [findings](docs/background/offline-findings.md)). Offline viewing and
  editing will come with the future browser-side frontend, in stages.

## Evolution and documentation

This document is the source of truth for high-level architecture. If code differs,
flag it and agree whether to change the implementation or update the decision.
Keep current operational details in `docs/`, supporting evidence and history in
`docs/background/`, proposed work in `plans/`, and unfinished work in the
[backlog](plans/backlog.md). Follow the documentation
lifecycle in [AGENTS.md](AGENTS.md).
