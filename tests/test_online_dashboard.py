import re
import time

import pytest

from room_store import RoomStore

PASSWORD = "a long test password"
BASE = "https://quiet-river.trycloudflare.com"
PAGES = ["/", "/trends", "/events", "/limits", "/system"]
CONTROLS = [("/profile", {"temp_c_low": 20, "temp_c_high": 27, "hold_s": 9}), ("/silence", {"token": "t"}),
            ("/acknowledge", {"alert_id": "a"}), ("/signout", {})]


class FakeTunnel:
    def __init__(self, state="active", url=BASE + "/", reason=None):
        self.value = {"state": state, "url": url, "reason": reason}

    def state(self):
        return dict(self.value)


@pytest.fixture
def online(tmp_path):
    pytest.importorskip("flask")
    from dashboard import create_app
    from online_auth import LoginLimiter, read_secret, write_secret

    write_secret(tmp_path / "secret.yaml", PASSWORD)
    secret = read_secret(tmp_path / "secret.yaml")
    path = tmp_path / "room.sqlite3"
    clock = [0.0]
    app = create_app(path, online=True, secret=secret, tunnel=FakeTunnel(),
                     limiter=LoginLimiter(clock=lambda: clock[0]))
    return app.test_client(), RoomStore(path), secret, clock


def csrf(client, path="/signin"):
    page = client.get(path, base_url=BASE).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page)
    assert match, page
    return match.group(1)


def sign_in(client, password=PASSWORD, headers=None):
    token = csrf(client)
    return client.post("/signin", data={"password": password, "csrf_token": token, "next": "/limits"},
                       base_url=BASE, headers=headers or {})


@pytest.mark.parametrize("path", PAGES + ["/api/room", "/signin"])
def test_online_pages_and_data_can_be_read_without_sign_in(online, path):
    client = online[0]
    response = client.get(path, base_url=BASE)
    assert response.status_code == 200


@pytest.mark.parametrize("path, form", CONTROLS)
def test_online_controls_are_refused_without_sign_in(online, path, form):
    client, store = online[0], online[1]
    assert client.post(path, data=form, base_url=BASE).status_code == 403
    token = csrf(client)
    assert client.post(path, data={**form, "csrf_token": token}, base_url=BASE).status_code == 403
    assert store.load_profile() is None


def test_online_controls_need_the_session_csrf_token(online):
    client, store = online[0], online[1]
    assert sign_in(client).status_code == 303
    form = {"temp_c_low": 20, "temp_c_high": 27, "hold_s": 9}
    assert client.post("/profile", data=form, base_url=BASE).status_code == 403
    assert client.post("/profile", data={**form, "csrf_token": "forged"}, base_url=BASE).status_code == 403
    assert store.load_profile() is None
    token = csrf(client, "/limits")
    assert client.post("/profile", data={**form, "csrf_token": token}, base_url=BASE).status_code == 303
    assert store.load_profile() == {"limits": {"temp_c": [20, 27]}, "hold_s": 9}


def test_sign_in_needs_its_csrf_token(online):
    client = online[0]
    csrf(client)
    response = client.post("/signin", data={"password": PASSWORD}, base_url=BASE)
    assert response.status_code == 403


def test_signed_in_session_expires_after_its_lifetime(online, monkeypatch):
    client = online[0]
    sign_in(client)
    token = csrf(client, "/limits")
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 9 * 3600)
    response = client.post("/profile", data={"hold_s": 9, "csrf_token": token}, base_url=BASE)
    assert response.status_code == 403


def test_sign_in_and_out_are_recorded_without_secrets(online):
    client, store, secret, _ = online
    assert sign_in(client, "wrong password").status_code == 401
    assert sign_in(client).headers["Location"].endswith("/limits")
    token = csrf(client, "/")
    assert client.post("/signout", data={"csrf_token": token}, base_url=BASE).status_code == 303
    events = store.events()
    assert [event["kind"] for event in events] == ["online_signed_out", "online_signed_in", "online_signin_failed"]
    text = repr(events)
    for hidden in (PASSWORD, "wrong password", secret["password_hash"], secret["secret_key"]):
        assert hidden not in text
    assert client.post("/profile", data={"hold_s": 9, "csrf_token": token}, base_url=BASE).status_code == 403


def test_sign_in_is_rate_limited_per_client(online):
    client, _, _, clock = online
    one = {"CF-Connecting-IP": "203.0.113.1"}
    for _ in range(5):
        assert sign_in(client, "wrong password", one).status_code == 401
    response = sign_in(client, PASSWORD, one)
    assert response.status_code == 429
    assert "Too many failed sign-ins" in response.get_data(as_text=True)
    other = client.application.test_client()
    assert sign_in(other, PASSWORD, {"CF-Connecting-IP": "203.0.113.2"}).status_code == 303
    clock[0] += 301
    assert sign_in(client, PASSWORD, one).status_code == 303


def test_online_origin_sends_protective_headers(online):
    client = online[0]
    for path in ("/", "/api/room", "/signin"):
        headers = client.get(path, base_url=BASE).headers
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "no-referrer"
        policy = headers["Content-Security-Policy"]
        assert "default-src 'self'" in policy and "frame-ancestors 'none'" in policy
        assert "unsafe-inline" not in policy


def test_session_cookie_is_secure_httponly_and_strict(online):
    client = online[0]
    cookie = client.get("/signin", base_url=BASE).headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie


@pytest.mark.parametrize("path", PAGES)
def test_pages_have_no_inline_script_or_style(online, path):
    page = online[0].get(path, base_url=BASE).get_data(as_text=True)
    assert "style=" not in page
    assert not re.search(r"<script(?![^>]*\bsrc=)", page)
    assert not re.search(r"\son[a-z]+=", page)


def test_no_secret_appears_in_pages_or_data(online):
    client, _, secret, _ = online
    sign_in(client)
    texts = [client.get(path, base_url=BASE).get_data(as_text=True) for path in PAGES + ["/api/room", "/signin"]]
    for text in texts:
        for hidden in (PASSWORD, secret["password_hash"], secret["secret_key"]):
            assert hidden not in text


def test_anonymous_online_view_locks_controls_with_words(online):
    client = online[0]
    page = client.get("/limits", base_url=BASE).get_data(as_text=True)
    assert "Sign in to save limits" in page and "Sign in to silence alarm" in page
    assert "Sign in to acknowledge" in page
    assert re.search(r"<button[^>]*data-control[^>]*disabled", page)
    assert 'href="/signin?next=/limits"' in page and "Sign out" not in page
    assert client.get("/api/room", base_url=BASE).json["online"] == {"state": "active", "url": None, "reason": None}
    assert BASE not in client.get("/system", base_url=BASE).get_data(as_text=True)


def test_signed_in_online_view_has_controls_and_the_link(online):
    client = online[0]
    sign_in(client)
    page = client.get("/limits", base_url=BASE).get_data(as_text=True)
    assert "Sign in to save limits" not in page and "Signed in" in page and "Sign out" in page
    assert not re.search(r"<button[^>]*data-control[^>]*disabled", page)
    assert client.get("/api/room", base_url=BASE).json["online"]["url"] == BASE + "/"


def test_cross_site_posts_are_refused_online(online):
    client = online[0]
    sign_in(client)
    token = csrf(client, "/limits")
    response = client.post("/profile", data={"hold_s": 9, "csrf_token": token}, base_url=BASE,
                           headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


def test_local_origin_has_no_sign_in_and_keeps_controls(tmp_path):
    pytest.importorskip("flask")
    from dashboard import create_app

    client = create_app(tmp_path / "room.sqlite3", tunnel=FakeTunnel()).test_client()
    page = client.get("/system").get_data(as_text=True)
    assert "Sign in" not in page and "View-only link active" in page and BASE in page
    assert "Copy link" in page
    assert client.get("/signin").status_code == 404
    assert client.post("/profile", data={"hold_s": 9}).status_code == 303
    assert client.get("/api/room").json["online"]["url"] == BASE + "/"
    assert "Content-Security-Policy" not in client.get("/").headers


@pytest.mark.parametrize("state, words", [
    ({"state": "off", "url": None, "reason": None}, "Online access: off"),
    ({"state": "starting", "url": None, "reason": None}, "Online access: starting"),
    ({"state": "failed", "url": None, "reason": "cloudflared not found"},
     "Online access failed: cloudflared not found")])
def test_local_system_page_shows_the_tunnel_state(tmp_path, state, words):
    pytest.importorskip("flask")
    from dashboard import create_app

    tunnel = FakeTunnel(**state)
    page = create_app(tmp_path / "room.sqlite3", tunnel=tunnel).test_client().get("/system").get_data(as_text=True)
    assert words in page


def test_online_app_needs_a_secret(tmp_path):
    pytest.importorskip("flask")
    from dashboard import create_app

    with pytest.raises(ValueError):
        create_app(tmp_path / "room.sqlite3", online=True, secret=None)


def test_set_password_command_writes_a_hash(tmp_path, monkeypatch, capsys):
    pytest.importorskip("flask")
    import dashboard
    from online_auth import read_secret

    monkeypatch.setattr(dashboard.getpass, "getpass", lambda prompt: PASSWORD)
    secret_path = tmp_path / "online_secret.yaml"
    assert dashboard.main(["--set-password", "--secret", str(secret_path)]) == 0
    assert PASSWORD not in secret_path.read_text() and read_secret(secret_path)
    assert PASSWORD not in capsys.readouterr().out


def test_online_without_a_password_runs_the_local_dashboard_only(tmp_path, monkeypatch, capsys):
    pytest.importorskip("flask")
    import dashboard
    from flask import Flask

    ran = []
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: ran.append(kwargs))
    started = []
    monkeypatch.setattr(dashboard, "start_online", lambda *args, **kwargs: started.append(args))
    assert dashboard.main(["--online", "--db", str(tmp_path / "r.sqlite3"),
                           "--secret", str(tmp_path / "absent.yaml")]) == 0
    assert ran == [{"host": "127.0.0.1", "port": 5000}] and not started
    assert "dashboard.py --set-password" in capsys.readouterr().out


def test_tunnel_changes_are_recorded_as_events_without_the_link(tmp_path):
    pytest.importorskip("flask")
    from dashboard import record_tunnel_change

    store = RoomStore(tmp_path / "r.sqlite3")
    record_tunnel_change(store, {"state": "starting", "url": None, "reason": None})
    record_tunnel_change(store, {"state": "active", "url": BASE, "reason": None})
    record_tunnel_change(store, {"state": "failed", "url": None, "reason": "cloudflared not found"})
    record_tunnel_change(store, {"state": "off", "url": None, "reason": None})
    events = store.events()
    assert [(e["kind"], e["message"]) for e in events] == [
        ("online_stopped", "Online access stopped"),
        ("online_failed", "Online access failed: cloudflared not found"),
        ("online_started", "Online access started (view-only link)")]
    assert BASE not in repr(events)
