import os


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str) -> list[str]:
    return [v.strip().lower() for v in os.environ.get(name, "").split(",") if v.strip()]


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///stockroom.sqlite")
    # Hosted Postgres providers hand out postgres:// URLs; SQLAlchemy needs the driver spelled out.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def load_config() -> dict:
    return {
        "APP_NAME": os.environ.get("APP_NAME", "Stockroom"),
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": database_url(),
        "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
        # Sign-in: any OpenID Connect provider (Google, Microsoft Entra, Okta, Auth0, ...).
        "OIDC_CLIENT_ID": os.environ.get("OIDC_CLIENT_ID"),
        "OIDC_CLIENT_SECRET": os.environ.get("OIDC_CLIENT_SECRET"),
        "OIDC_DISCOVERY_URL": os.environ.get(
            "OIDC_DISCOVERY_URL", "https://accounts.google.com/.well-known/openid-configuration"
        ),
        "OIDC_PROVIDER_NAME": os.environ.get("OIDC_PROVIDER_NAME", "Google"),
        "ALLOWED_EMAIL_DOMAINS": env_list("ALLOWED_EMAIL_DOMAINS"),
        "SUPERUSER_EMAIL": os.environ.get("SUPERUSER_EMAIL", "").strip().lower() or None,
        "DEV_LOGIN": env_bool("DEV_LOGIN"),
        # Email: Resend's HTTP API if a key is set, otherwise SMTP, otherwise just log.
        "MAIL_FROM": os.environ.get("MAIL_FROM"),
        "RESEND_API_KEY": os.environ.get("RESEND_API_KEY"),
        "MAIL_SERVER": os.environ.get("MAIL_SERVER"),
        "MAIL_PORT": int(os.environ.get("MAIL_PORT", "587")),
        "MAIL_USERNAME": os.environ.get("MAIL_USERNAME"),
        "MAIL_PASSWORD": os.environ.get("MAIL_PASSWORD"),
        "MAIL_USE_TLS": env_bool("MAIL_USE_TLS", True),
    }
