"""Prepares the Google sign-in client that students use to register a phone."""
from authlib.integrations.starlette_client import OAuth


def make_oauth(settings):
    """Google sign-in (OpenID Connect), as in spike S1. No routes yet (step 5)."""
    # Only prepares the Google client. It does not call Google until someone signs in.
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        # The metadata URL tells the library Google's addresses.
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth
