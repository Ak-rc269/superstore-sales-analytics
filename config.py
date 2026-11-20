"""Project configuration. Importing this module never connects to a database."""

from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    csv_path: Path
    output_dir: Path
    google_credentials_path: Path
    google_sheet_id: str
    google_worksheet_name: str


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def get_settings() -> Settings:
    """Read .env next to this file, regardless of the current working directory."""
    load_dotenv(PROJECT_DIR / ".env", override=False)
    port = int(os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5433")))
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be between 1 and 65535.")
    return Settings(
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=port,
        db_name=os.getenv("POSTGRES_DB", "superstore_db"),
        db_user=os.getenv("POSTGRES_USER", "superstore"),
        db_password=os.getenv("POSTGRES_PASSWORD", "superstore_local_change_me"),
        csv_path=_project_path(os.getenv("CSV_PATH", "data/raw/superstore.csv")),
        output_dir=_project_path(os.getenv("OUTPUT_DIR", "outputs")),
        google_credentials_path=_project_path(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
        ),
        google_sheet_id=os.getenv("GOOGLE_SHEET_ID", "").strip(),
        google_worksheet_name=os.getenv("GOOGLE_WORKSHEET_NAME", "dashboard_data").strip(),
    )


def get_engine(settings: Settings | None = None):
    """Build a lazy SQLAlchemy engine; do not print its URL or credentials."""
    try:
        from sqlalchemy import URL, create_engine
        import psycopg  # noqa: F401 - fail early with the install guidance below
    except ImportError as exc:
        raise RuntimeError(
            "Database dependencies are missing. Run: python -m pip install -r requirements.txt"
        ) from exc
    settings = settings or get_settings()
    url = URL.create(
        "postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
