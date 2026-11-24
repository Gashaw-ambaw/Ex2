import hashlib
import hmac


class QrTokens:
    """Short-lived QR tokens. A token proves the student saw the live screen."""

    def __init__(self, secret_key, rotate_sec, clock):
        self._key = secret_key.encode()
        self._rotate_sec = rotate_sec
        self._clock = clock

    def window(self):
        # Window number: it grows by 1 every rotate_sec seconds.
        return int(self._clock.now().timestamp()) // self._rotate_sec

    def make(self, session_id, window):
        message = f"{session_id}:{window}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()[:16]

    def verify(self, session_id, window, token):
        # Only the current and the previous window are valid (a scan may be slow).
        if window not in (self.window(), self.window() - 1):
            return False
        if not isinstance(token, str):
            return False
        # compare_digest takes the same time for any input, so timing leaks nothing.
        return hmac.compare_digest(self.make(session_id, window).encode(), token.encode())
