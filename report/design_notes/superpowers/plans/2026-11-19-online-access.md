# Online access plan

Spec: [online access design](../specs/2026-11-19-online-access-design.md). TDD; commit after each task.

1. Settings: online keys, defaults and validation in `settings.py`; `load_online_settings`. Tests in `tests/test_online_settings.py`.
2. `online_auth.py`: secret file write/read (hash, not plain text; mode 0600), login rate limiter, CSRF token compare. `.gitignore` the secret file. Tests in `tests/test_online_auth.py`.
3. `online_tunnel.py`: link parsing, state transitions with a fake process, missing binary, bounded retry, stop. Tests in `tests/test_online_tunnel.py`.
4. `dashboard.py`: `create_app(..., online=True, secret=..., tunnel=...)`; online gate (GET allowed, POST needs session and CSRF), headers, sign-in and sign-out, rate limit, events, `online` block in `/api/room`; `RoomStore.add_event`. Tests in `tests/test_online_dashboard.py`; existing local tests unchanged.
5. Templates and JS: sign-in page, top bar sign-in, locked controls with words, online state in sidebar and System card with Copy link, chart labels without inline style.
6. Command line: `--set-password`, `--online` (two listeners, tunnel, atexit, SIGTERM).
7. Screenshots (headless Chrome, 1280x800 and 375x812), fixes; one real tunnel run if `cloudflared` is installed.
8. Docs: README.md, README_HUMAN.md, reference_files/PYTHON_FILE_GUIDE.md.
