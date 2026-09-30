from hashlib import sha256

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class SignupRateThrottle(AnonRateThrottle):
    scope = "signup"


class LoginIPRateThrottle(AnonRateThrottle):
    scope = "login_ip"


class LoginUsernameRateThrottle(SimpleRateThrottle):
    scope = "login_username"

    def get_cache_key(self, request, view):
        username = str(request.data.get("username", "")).strip().lower()
        if not username:
            return None
        username_digest = sha256(username.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": username_digest}
