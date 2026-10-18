# Public list sharing

## Behavior

- **Share List** in the list's ⋮ menu produces `/share/<token>`. Anyone holding
  it can view and edit that list without the room password. It does not grant
  room management.
- **Reset share link** in that menu is available only to authorized room members
  and asks for confirmation. The server rechecks current room authorization and list ownership
  in the same transaction as rotation. An admin login alone is insufficient.
- Resetting invalidates the previous link for everyone. Already-open public
  pages cannot keep editing with it; their next action/refresh or periodic check
  removes access. Previously displayed or copied data cannot be recalled.
- Room navigation continues using `/list/<slug>`, now requiring room access.
  An unauthorized visitor sees a room-entry button, not list contents or a token.
  Old URLs never publicly redirect to a new token. Room access survives rotation.
- On the share page, a browser that also has access to the list's room gets the
  back arrow to the room and "Reset share link". Any other browser (no cookie,
  another room's cookie, a stale cookie) gets neither, and nothing on the page
  or in the API answers names the room. The server decides this on each read;
  the reset itself still goes through the room endpoint and its checks.
- Share links are independent of room passwords. Changing a room password revokes
  room authorization, **not public share links**; reset those separately if needed.
- The room menu has **Share Room**. Native sharing sends only the URL, so
  iPhone Copy does not include explanatory text. Access reminders appear in
  the app after sharing, or in the fallback copy-link dialog.
  The API is in [share links](api.md#share-links).

## Implementation

`lists.share_token` has a unique index. New lists receive
`secrets.token_urlsafe(32)` tokens (256 random bits), stored in the database.
Renaming lists and restarting the app preserve tokens. Tokens are stored in
plaintext: the database already contains the list contents. Treat URLs, browser
history, server request logs, and backups as sensitive. List pages suppress
outgoing referrers (Svelte: a `same-origin` policy, because `no-referrer` would
also blank the `Origin` its API writes need); this does not eliminate all URL
leakage.

Share writes check the token inside their write transaction, so a reset also
blocks queued edits and undo. Page refreshes, suggestions, and periodic checks
revalidate access. Room pages address lists and items by public `uid`
([API](api.md)).
The application remains single-instance; see [deployment](deployment.md).

## Rollout and verification

The [deploy script](deployment.md#backup-before-deploying) takes a backup. Startup adds/backfills tokens automatically.
Existing room URLs/passwords, manifest addresses, and remembered-access mechanisms
are unchanged. Replace any previously saved/shared public list URLs with new
Share links. Rolling back to older application code re-exposes the old public
slug routes; do not treat that as a security-preserving rollback.

Automated coverage: `tests/test_public_share_tokens.py`,
`tests/test_api_share.py` and the [real-browser suite](browser-testing.md)
(`test_public_sharing.py`, `test_svelte_share.py`). All run locally over HTTP
only.

These automated tests are the verification; there are no extra manual checks.
