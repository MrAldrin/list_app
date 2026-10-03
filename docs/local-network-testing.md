# Testing on a Phone before Deployment

Run the app on your laptop and open it on your phone. This is free and catches
most layout and touch problems before deployment.

## How it works

- `localhost` means "this computer". Your phone cannot reach your laptop's
  `localhost`.
- The app already listens on all network interfaces (`host="0.0.0.0"` in
  `src/main.py`), so other devices can reach it through the laptop's address.
- Tailscale gives the laptop a private address (`100.x.x.x`) that only your own
  devices can reach, at home or away.

## Current setup (Tailscale)

Access is limited in two places. Both must allow port `8080`:

- **Tailscale access rules** (<https://login.tailscale.com/admin/acls>): a rule
  "iphone to list app dev server" allows only the iPhone (`100.121.206.45`) to
  reach the laptop (`100.121.200.49`) on `tcp:8080`.
- **Laptop firewall (`ufw`)**: `sudo ufw allow in on tailscale0 to any port 8080 proto tcp`
  allows port 8080 on the Tailscale interface only.

## Steps

1. Start the app (see the [README](../README.md)):

   ```bash
   uv run python src/main.py
   ```

2. Turn on Tailscale on the phone.
3. Open `http://100.121.200.49:8080`. Include `http://`; `https` does not work.
4. Stop the app with `Ctrl+C` when done.

## Svelte prototype

The new Svelte app runs next to NiceGUI under `/app/`. One command builds it
and starts the app with a separate test database:

```bash
uv run python scripts/serve_svelte_local.py
```

- Stop the normal app first: both use port `8080`, the only port the firewall
  rules allow.
- It prints the phone address, for example `http://100.121.200.49:8080/app/`.
  NiceGUI is the same address without `/app/`.
- The test database is in `~/.local/share/list_app/svelte-phone-test/`, never
  `list.db` or production. A new one has one room, `Home`, with
  `APP_PASSWORD` as its password. `--db` picks another file.
- `--skip-build` reuses the last build; `--port` changes the port.
- Sign in to NiceGUI and to the Svelte app separately. On plain `http` they
  keep room access in different places.

What to check is in the [Gate A checklist](../plans/svelte-frontend-rewrite.md#gate-a-checklist).

## If the page loads forever

- Check that the app is running and Tailscale is on for the phone.
- Check the Tailscale rule's source IP matches the phone (`tailscale status`).
  A typo here blocks the phone silently.
- If requests never reach the laptop, a Tailscale access rule is blocking them.
  If they are blocked on the laptop, check `sudo ufw status`.

## Alternative: home Wi-Fi without Tailscale

Open `http://<laptop-ip>:8080` (find the IP with `hostname -I`). This needs a
firewall rule for the home network, for example
`sudo ufw allow from 192.168.10.0/24 to any port 8080 proto tcp`.
Guest Wi-Fi often blocks devices from reaching each other.

## Limits

- It uses plain `http`, not `https`. Home-screen install and other features
  that need HTTPS may behave differently from production.
- It uses an empty test database. Changes to the database structure may still
  fail on production's older data.
- It uses local `.env` settings, not Railway's settings, volume or build.
  Railway-specific problems need a real deployment; see the
  [staging environment plan](../plans/staging-environment.md).
