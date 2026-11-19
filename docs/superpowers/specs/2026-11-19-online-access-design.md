# Online access design

Approved scope: the user decided on 19 November 2026 that the dashboard can be viewed online through a Cloudflare quick tunnel, started on request. The laptop stays the edge device. Monitoring, alerts and the local alarm never depend on the internet or on the tunnel. No new Python dependencies.

## Decisions

- Opt-in: `dashboard.py --online` starts online access. Without it nothing changes.
- Quick tunnel: `cloudflared tunnel --no-autoupdate --url http://127.0.0.1:<online_port>`. The random `https://*.trycloudflare.com` link changes on each start. A named tunnel later is a settings change (`cloudflared_tunnel`, `online_public_url`), not a rewrite.
- Online is view-only. Saving limits, silencing the alarm and acknowledging need a password. The laptop itself keeps the controls without sign-in.
- `cloudflared` is installed separately. When it is missing, the online state is "failed: cloudflared not found" and the local dashboard keeps working.

## Two listeners

Tunnel requests reach the dashboard from 127.0.0.1, so the remote address cannot tell local from online. The dashboard therefore serves two origins from one process, both bound to 127.0.0.1:

| Origin | Port | Who | Controls |
|---|---|---|---|
| Local | 5000 | The laptop's browser | As today; host check and Origin check unchanged |
| Online | `online_port` (5001) | Only `cloudflared` points here | Every request is remote: GET pages and `/api/room` allowed; every POST needs a signed-in session and a valid CSRF token, otherwise 403 |

The online origin does not use the local Host check (the tunnel forwards the public host name). It compares a POST's Origin host with the request host.

## Password and sessions

- `dashboard.py --set-password` prompts twice with `getpass` and writes `config/online_secret.yaml` (git-ignored, file mode 0600): a werkzeug password hash and a random session secret key. The plain password is never stored.
- `--online` without that file prints a clear message and serves the local dashboard only.
- Session cookie: HttpOnly, Secure, SameSite=Strict, lifetime `online_session_hours` (default 8).
- Sign-in uses `check_password_hash`. Rate limit in memory: 5 failures per 5 minutes per client, then wait (HTTP 429), plus 20 failures per 5 minutes in total. `CF-Connecting-IP` is only a rate-limit key on the online origin, never an authorisation input.
- CSRF: one random token per session, a hidden `csrf_token` field in every control form and in sign-in and sign-out, checked with a constant-time compare on the online origin.
- Events: "Online access started", "Online access stopped", "Online access failed", "Signed in online", "Online sign-in failed", "Signed out online". No password, hash, secret, IP or link in events, logs, pages or `/api/room`.

## Headers on the online origin

`Cache-Control: no-store`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'`. The chart's two inline `style` attributes become CSS classes so the pages satisfy the policy.

## Tunnel module

`online_tunnel.py` starts the child with `subprocess.Popen` (list arguments, no shell), reads its output on a thread and parses the link. State: off, starting, active (with link), failed (with reason). A child that exits is restarted at most twice, then the state is failed. `stop()` terminates the child (kill after 5 s); `dashboard.py` registers it with `atexit` and turns SIGTERM into a normal exit.

## Dashboard

- `/api/room` gains `online: {state, url, reason}`. `url` is present only on the local origin and for signed-in online users.
- Sidebar foot and System page card show the real state. When active: "View-only link active", the link in a read-only field and a "Copy link" button. No Stop button (stop by ending `dashboard.py --online`).
- Online top bar: "Sign in" at the right, or "Signed in · Sign out". Locally no sign-in appears.
- Online without sign-in: controls stay visible but disabled, with words: "Sign in to save limits", "Sign in to silence alarm", "Sign in to acknowledge".

## Settings (`config/runtime.yaml`, optional)

`online_port` (1024 to 65535, not 5000), `cloudflared_path` (non-empty text), `online_session_hours` (positive), `cloudflared_tunnel` (null or a name), `online_public_url` (null or https URL; required with a name).
