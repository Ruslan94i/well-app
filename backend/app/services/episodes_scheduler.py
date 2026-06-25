from __future__ import annotations

import logging
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.services.auto_episodes import clear_auto_episode_caches


logger = logging.getLogger(__name__)

_scheduler_stop = threading.Event()
_scheduler_thread: threading.Thread | None = None


def run_episode_recompute_once(wells: str | None = None) -> bool:
    started_at = datetime.now(timezone.utc)
    script_path = settings.episodes_compute_script_path
    telemetry_path = settings.episodes_compute_telemetry_data_path
    output_path = settings.episodes_table_data_path

    if not script_path.exists():
        logger.warning("Episode recompute script is missing: %s", script_path)
        return False
    if not telemetry_path.exists():
        logger.warning("Episode recompute telemetry file is missing: %s", telemetry_path)
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(script_path),
        "--telem",
        str(telemetry_path),
        "--out",
        str(output_path),
        "--model-version",
        settings.episodes_model_version,
    ]

    if settings.episodes_compute_wct_data_path.exists():
        command.extend(["--wct", str(settings.episodes_compute_wct_data_path)])
    if settings.episodes_compute_enriched_data_path:
        command.extend(["--enrich", str(settings.episodes_compute_enriched_data_path)])
    if settings.episodes_compute_kprod_data_path:
        command.extend(["--kprod", str(settings.episodes_compute_kprod_data_path)])
    if wells:
        command.extend(["--wells", wells])

    logger.info("Starting offline episode recompute: %s", " ".join(command))
    try:
        completed = subprocess.run(
            command,
            cwd=str(script_path.parent),
            timeout=settings.episodes_compute_timeout_seconds,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.exception("Offline episode recompute timed out")
        return False

    if completed.stdout:
        logger.info("Episode recompute stdout: %s", completed.stdout.strip())
    if completed.stderr:
        log = logger.error if completed.returncode else logger.warning
        log("Episode recompute stderr: %s", completed.stderr.strip())
    if completed.returncode:
        logger.error("Offline episode recompute failed with code %s", completed.returncode)
        return False

    clear_auto_episode_caches()
    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
    logger.info("Offline episode recompute finished in %.1fs: %s", duration, output_path)
    return True


def _seconds_until_next_run() -> float:
    hour = min(23, max(0, int(settings.episodes_scheduler_hour_utc)))
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def _scheduler_loop() -> None:
    while not _scheduler_stop.wait(_seconds_until_next_run()):
        run_episode_recompute_once()


def start_episode_scheduler() -> None:
    global _scheduler_thread
    if not settings.episodes_scheduler_enabled:
        logger.info("Offline episode scheduler is disabled")
        return
    if _scheduler_thread and _scheduler_thread.is_alive():
        return

    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, name="episode-recompute-scheduler", daemon=True)
    _scheduler_thread.start()
    logger.info("Offline episode scheduler started at %02d:00 UTC", settings.episodes_scheduler_hour_utc)


def stop_episode_scheduler() -> None:
    _scheduler_stop.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)
