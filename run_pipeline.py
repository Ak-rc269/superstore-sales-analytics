"""Run ingest -> transform -> publish with one command."""

from __future__ import annotations

import argparse
import logging
import time

from config import get_settings
from ingest import ingest
from transform import transform
from publish import publish, validate_publish_config

LOGGER = logging.getLogger("superstore")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-publish", action="store_true",
        help="Run local PostgreSQL stages while Google credentials are being prepared.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stage = "configuration"
    started = time.perf_counter()
    try:
        settings = get_settings()
        if not args.skip_publish:
            validate_publish_config(settings)
        stage = "ingest"
        LOGGER.info("Step 1: CSV -> raw_data.superstore")
        ingest(settings)
        stage = "transform"
        LOGGER.info("Step 2: raw_data -> production tables")
        transform(settings)
        if args.skip_publish:
            LOGGER.info("Local stages completed. Google Sheets was not updated (--skip-publish).")
        else:
            stage = "publish"
            LOGGER.info("Step 3: production.sales_detail -> Google Sheets")
            publish(settings)
            LOGGER.info("All three stages completed successfully.")
        LOGGER.info("Elapsed time: %.1f seconds", time.perf_counter() - started)
        return 0
    except (ValueError, FileNotFoundError) as exc:
        LOGGER.error("Stopped at %s: %s", stage, exc)
    except PermissionError as exc:
        LOGGER.error("Stopped at %s: %s", stage, exc)
    except ModuleNotFoundError as exc:
        LOGGER.error("Missing dependency: %s. Run python -m pip install -r requirements.txt", exc.name)
    except Exception as exc:
        LOGGER.error("Stopped at %s (%s). See README.md troubleshooting.", stage, type(exc).__name__)
        if stage in {"ingest", "transform"}:
            LOGGER.error("Check docker compose ps, DB_PORT and the local database settings in .env.")
        else:
            LOGGER.error("Check Google API access, the spreadsheet ID and service-account Editor access.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
