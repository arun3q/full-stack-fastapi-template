import secrets
import warnings
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    # Per-process random fallback; rejected in non-local environments so a
    # multi-worker deploy can't silently diverge on JWT verification.
    _AUTO_SECRET_KEY: ClassVar[str] = secrets.token_urlsafe(32)
    SECRET_KEY: str = _AUTO_SECRET_KEY
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Failed login lockout (Redis-backed; skipped when Redis is unavailable)
    LOGIN_FAILURE_LIMIT: int = 5
    LOGIN_FAILURE_WINDOW_SECONDS: int = 900
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    # Database connection pool tuning
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20
    POSTGRES_POOL_TIMEOUT: int = 30
    POSTGRES_POOL_PRE_PING: bool = True

    # Optional read-replica connection for read-heavy endpoints
    READ_REPLICA_URL: str | None = None

    # Redis / background jobs
    REDIS_URL: str = "redis://localhost:6379/0"

    # Emails
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    # Payments
    PAYMENT_PROVIDER: Literal["stripe", "razorpay", "none"] = "none"
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRICE_ID: str | None = None
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    RAZORPAY_WEBHOOK_SECRET: str | None = None
    RAZORPAY_PLAN_ID: str | None = None

    # Social OAuth providers
    OAUTH_CALLBACK_BASE_URL: str = "http://localhost:8000/api/v1"
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    LINKEDIN_CLIENT_ID: str | None = None
    LINKEDIN_CLIENT_SECRET: str | None = None
    META_CLIENT_ID: str | None = None
    META_CLIENT_SECRET: str | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None

    # AI / LLM providers
    AI_PROVIDER: Literal["openai", "anthropic", "none"] = "none"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-latest"

    # Rate limiting (slowapi). Use "memory://" for single-process dev or a
    # redis URL (e.g. redis://localhost:6379/0) for multi-worker deployments.
    RATE_LIMIT_STORAGE: str = "memory://"

    # Logging
    LOG_FORMAT: Literal["console", "json"] = "console"

    # Metrics
    ENABLE_METRICS: bool = True

    # Object storage (S3 / MinIO compatible)
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET: str = "uploads"
    S3_PUBLIC_URL: str | None = None

    # Auth transport: when True, login sets an httpOnly cookie and the token is
    # also read from that cookie (CSRF-safe session flow).
    AUTH_TOKEN_IN_COOKIE: bool = False

    # Postgres Row-Level Security (defense-in-depth). When enabled the app sets
    # the tenant GUC (app.current_org_id / app.is_admin) per request. Requires
    # the RLS policies from ops.md to be applied to the tenant tables.
    ENABLE_RLS: bool = False

    # OpenTelemetry tracing (optional toggle). When set, spans export via OTLP.
    ENABLE_OTEL: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None

    # Metrics: optional bearer token to protect /metrics (empty = open)
    METRICS_TOKEN: str | None = None

    # Enterprise SAML SSO (python3-saml). Set SAML_ENABLED + IdP metadata to use.
    SAML_ENABLED: bool = False
    SAML_SP_ENTITY_ID: str = "https://localhost/api/v1/auth/saml/metadata"
    SAML_SP_ACS_URL: str = "https://localhost/api/v1/auth/saml/acs"
    SAML_SP_LOGOUT_URL: str = "https://localhost/api/v1/auth/saml/sls"
    # File path or URL to the IdP metadata XML
    SAML_IDP_METADATA: str | None = None
    SAML_ATTRIBUTE_EMAIL: str = "email"
    SAML_ATTRIBUTE_NAME: str = "displayname"
    # When false, SAML refuses to log into an existing account that has a
    # password (prevents IdP-driven account takeover). Enable to allow linking.
    SAML_ALLOW_PASSWORD_LINKING: bool = False

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        if self.ENVIRONMENT != "local" and self.SECRET_KEY == self._AUTO_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set explicitly in non-local environments"
            )
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
