from datetime import datetime, timezone

from app.clock import Clock
from app.qr_tokens import QrTokens


def make_tokens(secret="test-secret-key"):
    clock = Clock()
    # 10:00:05 UTC is in the middle of a 10 s window, so +4 s stays in the same window.
    clock.set(datetime(2026, 11, 24, 10, 0, 5, tzinfo=timezone.utc))
    return QrTokens(secret, 10, clock), clock


# TC-10: a token of the current window is accepted.
def test_token_of_current_window_is_accepted():
    qr, _ = make_tokens()
    w = qr.window()
    assert qr.verify(1, w, qr.make(1, w))


# TC-11: a student may scan just before the QR changes, so the previous window is accepted.
def test_token_of_previous_window_is_accepted():
    qr, _ = make_tokens()
    w = qr.window()
    assert qr.verify(1, w - 1, qr.make(1, w - 1))


# TC-12: an older token is a stale or shared photo, so it is rejected.
def test_token_two_windows_old_is_rejected():
    qr, _ = make_tokens()
    w = qr.window()
    assert not qr.verify(1, w - 2, qr.make(1, w - 2))


# TC-13: a token from one class session must not work in another.
def test_token_of_another_session_is_rejected():
    qr, _ = make_tokens()
    w = qr.window()
    assert not qr.verify(2, w, qr.make(1, w))


# Extra: a window number from the future cannot be guessed ahead of time.
def test_token_of_a_future_window_is_rejected():
    qr, _ = make_tokens()
    w = qr.window()
    assert not qr.verify(1, w + 1, qr.make(1, w + 1))


# Extra: bad input from a browser must give False, never an error.
def test_wrong_empty_or_non_string_token_is_rejected():
    qr, _ = make_tokens()
    w = qr.window()
    for bad in ("", "wrong", "x" * 16, None, 123, b"abc"):
        assert qr.verify(1, w, bad) is False


# Extra: the token has a fixed shape and is the same for the same input.
def test_token_is_16_hex_characters_and_repeatable():
    qr, _ = make_tokens()
    token = qr.make(1, 5)
    assert len(token) == 16
    int(token, 16)  # raises ValueError if it is not hex
    assert qr.make(1, 5) == token


# Extra: without SECRET_KEY nobody can forge a token, so another key must differ.
def test_other_secret_key_gives_other_token():
    a, _ = make_tokens("key-a")
    b, _ = make_tokens("key-b")
    assert a.make(1, 5) != b.make(1, 5)
    assert not b.verify(1, 5, a.make(1, 5))


# Extra: the window number must change exactly every QR_ROTATE_SEC seconds.
def test_window_changes_at_the_rotate_boundary():
    qr, clock = make_tokens()
    first = qr.window()
    clock.set(datetime(2026, 11, 24, 10, 0, 9, tzinfo=timezone.utc))
    assert qr.window() == first
    clock.set(datetime(2026, 11, 24, 10, 0, 10, tzinfo=timezone.utc))
    assert qr.window() == first + 1
