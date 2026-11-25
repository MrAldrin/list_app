# Side-by-side check: Python and Bun (November 2026)

Evidence for the [switch to Bun](../deployment.md#one-time-switch-between-python-and-bun).
Beads: lr-5g6.6.4 and children .1 to .4. Run on 2026-11-25.

**Verdict: GO WITH NOTES.** Sign-ins carry over in both directions. Both
servers give the same answers on real data. The only differences in data are
the owner-approved deviations. The owner accepts the notes in
[Findings](#findings) before the switch.

## What was compared

- Code: bookmark `typescript-port` at `46d62839`. Python ran with
  `uv run python src/main.py` for checks 1 and 2 and from the `python` image
  target for the measurements. Bun ran from the default (production) image
  target in all checks.
- Data: copies of the newest production backup (2026-11-23), stored in a
  temporary folder outside the repository. The copies had 12 rooms, 28 lists
  (all shared), 442 items, 841 stored op answers and 2 invitations. No real
  names, item text, passwords, tokens or cookie values were recorded.
- Access: a throwaway `APP_PASSWORD`. Room passwords were reset on the copies
  through the admin API.
- Production mode: every request came through a fake proxy
  (`X-Forwarded-Proto: https`, `X-Forwarded-Host`). This means both servers
  set the `__Host-` cookies that phones have in production.
- Scripts were throwaway Python scripts with `httpx`. They are not kept.

## 1. Sign-ins across the switch

The two servers took turns on the same database copy. Cookies from one server
were sent to the other. Result: 27 of 27 checks pass.

| Cookie | Python → Bun | Bun → Python |
|---|---|---|
| Room (who-am-I, snapshot, write) | pass | pass |
| Last room | pass | pass |
| Admin (overview) | pass | pass |
| Device (reminder settings read, grant stays active, device settings) | pass | pass |
| Existing share link | pass | pass |

| Revocation on one server, checked on the other | Result |
|---|---|
| Sign-out on Bun: cookie refused on Python, other cookies still work | pass |
| Sign-out on Python: cookie refused on Bun, device grant cut (`needs_resume`) | pass |
| Password change on Bun: old cookies refused on Python, new cookie and new password work, device grant cut | pass |
| Password change on Python: old cookie refused on Bun, new cookie works | pass |
| Admin reset on Bun: old cookie refused on Python | pass |

Extra check: room tokens shaped like the real rows (SQLite timestamp text,
200 and 400 days old) behave the same on both servers. The 200-day token
enrolls as `active`. The 400-day token reports `needs_resume`.

## 2. Answers on real data

**Reads.** Both servers ran on one copy at the same time. 778 requests were
compared and 774 were equal. Every API data answer was equal. Also, 40 of 40
live-stream first frames were equal.

| Endpoint group | Compared | Equal |
|---|---:|---:|
| Room snapshot and changes feed (since 0, middle, seq−1, seq, beyond seq, no cookie, 422 cases) | 96 | 96 |
| Share feed (no cookie, room cookie) and share-link | 84 | 84 |
| Reminder reads (preferences, device, room/list/item policy) | 530 | 530 |
| Room session, last room | 24 | 24 |
| Room install manifests | 24 | 24 |
| Admin, global manifests, `/healthz`, error paths | 16 | 16 |
| `/sw.js` and icon files | 4 | 0 |
| Room and share live streams (first frame) | 40 | 40 |

Normalizations: the `Date`, `Server` and `Content-Length` headers. JSON was
compared after parsing (key order and spacing ignored). In live streams, the
`charset` in `Content-Type` and the JSON spacing were ignored.

**Writes.** A 47-step script ran on two identical copies, one per server. It
included add, rename, check, uncheck, quantity, edit with due time, delete,
restore, all tag ops, list create, rename and delete, visibility, a retry,
a reused `op_id`, stale edits, share-link ops, a share-link reset, reminder
writes and error cases. Real lists and items were used where possible.

- 30 answers were equal. The other 17 differ only in `seq` and
  `changed_seq`. The difference is a constant +1, which starts at
  `list.tag_remove` (see F1).
- The final databases have the same row count in all 14 tables. Only the seq
  columns and the seq in stored answers differ. Normalizations: list slug
  suffix and share token values, timestamps compared by format only, JSON
  columns parsed. Not compared: password, token, share and request hashes.
- A retry of the same op on the same server returns the stored answer on both.
- A retry on the other server gets `409 op_id_reused` in both directions.

## 3. Measurements

Machine: AMD Ryzen 7 5700X (16 threads), 15 GB RAM, Linux 7.0, podman 4.9.3.
Bun 1.4.4 and Python 3.13.11 from the images. One server at a time, same copy,
production images. Load: 500 requests for each endpoint, with 1 client and
with 4 clients, after a warm-up of 50 requests. The room is the largest
(321 items, 110 KB snapshot).

| Measure | Python | Bun |
|---|---:|---:|
| Image size | 221 MB | 352 MB |
| Start-up until `/healthz` is 200, including `podman run` (median of 5) | 0.84 s | 0.36 s |
| Memory (RSS) at idle | 56 MB | 70 MB |
| Memory after the load | 58 MB | 128 MB |
| Peak memory | 119 MB | 141 MB |
| Memory, 4 load rounds, then 30 s idle | 59 → 59 MB | 128–136 → 95 MB |
| Server CPU time for the 5,000-request load | 7.0 s | 6.8 s |
| Room snapshot p50 / p95, 1 client | 2.7 / 3.2 ms | 2.9 / 4.3 ms |
| Room snapshot p50 / p95, 4 clients | 10.8 / 11.3 ms | 7.5 / 16.1 ms |
| Changes feed (since seq−10), 1 client | 1.0 / 1.1 ms | 0.8 / 1.0 ms |
| Changes feed, 4 clients | 2.9 / 3.3 ms | 1.8 / 3.1 ms |
| Item write (`item.quantity_delta`), 1 client | 5.1 / 5.8 ms | 6.8 / 8.5 ms |
| Item write, 4 clients | 18.0 / 50.6 ms | 20.1 / 42.7 ms |
| Share feed API, 1 client | 1.8 / 2.2 ms | 1.7 / 2.7 ms |
| Share feed API, 4 clients | 6.6 / 7.5 ms | 3.5 / 7.8 ms |
| Share page HTML, 1 client | 0.9 / 1.0 ms | 0.5 / 0.6 ms |
| Share page HTML, 4 clients | 3.0 / 4.5 ms | 1.6 / 3.0 ms |
| Live stream, write to event, 4 streams × 20 writes, p50 / p95 / max | 15.7 / 19.5 / 24.0 ms | 9.5 / 12.4 / 13.9 ms |

Commands:

```bash
podman build --format docker -t listapp-bun-sbs .
podman build --format docker --target python -t listapp-python-sbs .
podman run -d -p 127.0.0.1:PORT:8080 -v COPY_DIR:/data:Z \
  -e DB_PATH=/data/list.db -e APP_PASSWORD=THROWAWAY IMAGE
```

The Python container also had `FORWARDED_ALLOW_IPS=*`, as on Railway. Memory
is the `VmRSS` and `VmHWM` of the container's server process. CPU is the
process's user plus system time.

For Railway: all times are a few milliseconds and the CPU use is the same.
Bun starts faster, which shortens the gap during a deploy. Bun uses about
70 MB more memory under load. On Railway, memory is billed by use, so expect
a small extra cost.

## Findings

| ID | Where | Python | Bun | User impact | Kind |
|---|---|---|---|---|---|
| F1 | `list.tag_remove` | Keeps the tag on items | Also removes it from every item, so one extra seq step | None. This is the approved rule. | Intended (lr-5g6.18 #2) |
| F2 | Retry of an op sent to the other server | `409 op_id_reused` | `409 op_id_reused` | A phone that lost an answer during the switch sees the op refused. | Intended (cross-version retry rule) |
| F3 | `/sw.js` | Kill-switch script | Same steps, different text | None | Intended (lr-5g6.18 #4) |
| F4 | `docs/api-lists-items.md` | – | The `list.tag_remove` row still says item tags are not changed | Docs are wrong after the switch | Unexpected, bead lr-5g6.6.5 |
| F5 | `/apple-touch-icon*.png`, `/favicon.ico` | `ETag`, `Last-Modified`, no `Cache-Control` | `Cache-Control: no-cache`, no `ETag` | A few kB downloaded again. No visible change. | Unexpected, no fix needed |
| F6 | Unknown page paths, `/index.html` | 200 with the app shell | 404 | Only typed or broken links. Known app routes and `/app` redirects are equal. | Unexpected, no fix needed |
| F7 | Memory | About 59 MB | About 95–136 MB | Small Railway cost | Expected for a Bun process |

Small differences with no effect: `Content-Type` without `charset` on live
streams and HTML, and JSON spacing in live-stream data.

## Not covered

- Real phones and the installed app. The [switch steps](../deployment.md#one-time-switch-between-python-and-bun)
  keep the check with one Android friend.
- The real Railway proxy. The forwarded headers were simulated.
- Stored op answers from before the copy. Their request bodies are not stored,
  so a cross-server replay of an old op was tested only with new ops (F2).
