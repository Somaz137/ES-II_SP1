import stat

import pytest

from online_auth import (LoginLimiter, PASSWORD_MIN, check_password, new_csrf_token, prompt_password,
                         read_secret, tokens_match, write_secret)


def test_secret_file_holds_a_hash_and_a_key_but_not_the_password(tmp_path):
    path = tmp_path / "online_secret.yaml"
    write_secret(path, "correct horse battery")
    text = path.read_text()
    assert "correct horse battery" not in text
    secret = read_secret(path)
    assert set(secret) == {"password_hash", "secret_key"}
    assert secret["password_hash"] != "correct horse battery" and len(secret["secret_key"]) >= 32
    assert check_password(secret, "correct horse battery")
    assert not check_password(secret, "wrong password")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_a_new_password_replaces_the_session_key(tmp_path):
    path = tmp_path / "online_secret.yaml"
    write_secret(path, "first password")
    first = read_secret(path)["secret_key"]
    write_secret(path, "second password")
    assert read_secret(path)["secret_key"] != first


def test_missing_secret_file_reads_as_none(tmp_path):
    assert read_secret(tmp_path / "absent.yaml") is None


@pytest.mark.parametrize("text", ["- a list\n", "password_hash: x\n", "{password_hash: '', secret_key: k}\n"])
def test_malformed_secret_file_is_refused(tmp_path, text):
    path = tmp_path / "online_secret.yaml"
    path.write_text(text)
    with pytest.raises(ValueError):
        read_secret(path)


def test_short_passwords_are_refused(tmp_path):
    with pytest.raises(ValueError, match=str(PASSWORD_MIN)):
        write_secret(tmp_path / "s.yaml", "short")


def test_prompt_asks_twice_and_requires_a_match():
    answers = iter(["a long password", "a long password"])
    assert prompt_password(lambda prompt: next(answers)) == "a long password"
    answers = iter(["a long password", "another password"])
    with pytest.raises(ValueError, match="did not match"):
        prompt_password(lambda prompt: next(answers))


def test_secret_file_is_ignored_by_git():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert "/src/config/online_secret.yaml" in (root / ".gitignore").read_text().split()


def test_limiter_blocks_a_client_after_five_failures_for_five_minutes():
    now = [1000.0]
    limiter = LoginLimiter(clock=lambda: now[0])
    for _ in range(5):
        assert limiter.wait_s("a") == 0
        limiter.failed("a")
    assert 0 < limiter.wait_s("a") <= 300
    assert limiter.wait_s("b") == 0
    now[0] += 301
    assert limiter.wait_s("a") == 0


def test_limiter_success_clears_the_client_and_total_cap_applies():
    limiter = LoginLimiter(clock=lambda: 0.0)
    for _ in range(4):
        limiter.failed("a")
    limiter.succeeded("a")
    assert limiter.wait_s("a") == 0
    for index in range(20):
        limiter.failed(f"client {index}")
    assert limiter.wait_s("fresh client") > 0


def test_csrf_tokens_are_random_and_compared_safely():
    first, second = new_csrf_token(), new_csrf_token()
    assert first != second and len(first) >= 32
    assert tokens_match(first, first)
    assert not tokens_match(first, second)
    assert not tokens_match(first, None) and not tokens_match(None, None) and not tokens_match("", "")
