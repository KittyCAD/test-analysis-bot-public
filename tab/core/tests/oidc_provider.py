import base64
import hashlib
import hmac
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def _base64url_uint(value: int) -> str:
    size = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(size, "big")).rstrip(b"=").decode()


class LocalOIDCProvider:
    key_id = "test-key"
    client_id = "test-client-id"
    client_secret = "test-client-secret"

    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        self.email = "person@example.com"
        self.email_verified = True
        self.id_token_subject = "authentik-user"
        self.userinfo_subject = "authentik-user"
        self.nonce = ""
        self.code_challenge = ""
        self.redirect_uri = ""
        self.id_token_claims: dict[str, object] = {}
        self.token_request: dict[str, str] = {}

        provider = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/token/":
                    self.send_error(404)
                    return

                content_length = int(self.headers.get("Content-Length", "0"))
                form = parse_qs(self.rfile.read(content_length).decode())
                provider.token_request = {
                    key: values[0] for key, values in form.items() if values
                }
                if error := provider._token_request_error():
                    provider._send_json(
                        self,
                        {"error": "invalid_request", "error_description": error},
                        status=400,
                    )
                    return
                provider._send_json(self, provider._token_response())

            def do_GET(self):
                if self.path == "/jwks/":
                    provider._send_json(self, {"keys": [provider._jwk()]})
                    return
                if self.path == "/userinfo/":
                    if self.headers.get("Authorization") != "Bearer test-access-token":
                        provider._send_json(
                            self,
                            {"error": "invalid_token"},
                            status=401,
                        )
                        return
                    provider._send_json(
                        self,
                        {
                            "sub": provider.userinfo_subject,
                            "email": provider.email,
                            "email_verified": provider.email_verified,
                        },
                    )
                    return
                self.send_error(404)

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    @property
    def issuer(self) -> str:
        return f"{self.base_url}/issuer/"

    @property
    def django_settings(self) -> dict[str, object]:
        return {
            "OIDC_OP_ISSUER": self.issuer,
            "OIDC_OP_AUTHORIZATION_ENDPOINT": f"{self.base_url}/authorize/",
            "OIDC_OP_TOKEN_ENDPOINT": f"{self.base_url}/token/",
            "OIDC_OP_USER_ENDPOINT": f"{self.base_url}/userinfo/",
            "OIDC_OP_JWKS_ENDPOINT": f"{self.base_url}/jwks/",
            "OIDC_RP_CLIENT_ID": self.client_id,
            "OIDC_RP_CLIENT_SECRET": self.client_secret,
        }

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def capture_authorization(self, location: str) -> dict[str, list[str]]:
        query = parse_qs(urlparse(location).query)
        self.nonce = query["nonce"][0]
        self.code_challenge = query["code_challenge"][0]
        self.redirect_uri = query["redirect_uri"][0]
        return query

    def _token_request_error(self) -> str | None:
        expected_fields = {
            "grant_type": "authorization_code",
            "code": "valid-code",
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        for field, expected in expected_fields.items():
            if self.token_request.get(field) != expected:
                return f"invalid {field}"

        verifier = self.token_request.get("code_verifier", "")
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        if not hmac.compare_digest(challenge, self.code_challenge):
            return "invalid code_verifier"
        return None

    def _token_response(self) -> dict[str, object]:
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": self.client_id,
            "sub": self.id_token_subject,
            "iat": now,
            "exp": now + 300,
            "nonce": self.nonce,
        }
        claims.update(self.id_token_claims)
        id_token = jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.key_id},
        )
        return {
            "access_token": "test-access-token",
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": 300,
        }

    def _jwk(self) -> dict[str, str]:
        public_numbers = self.private_key.public_key().public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.key_id,
            "n": _base64url_uint(public_numbers.n),
            "e": _base64url_uint(public_numbers.e),
        }

    @staticmethod
    def _send_json(
        handler: BaseHTTPRequestHandler,
        payload: dict[str, object],
        status: int = 200,
    ) -> None:
        body = json.dumps(payload).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
