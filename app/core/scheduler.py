import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.services.worker import poll_due_slots

logger = logging.getLogger(__name__)

# APScheduler 3.x SQLAlchemyJobStore requires a sync engine.
# We convert our asyncpg URL to psycopg2.
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")

jobstores = {"default": SQLAlchemyJobStore(url=sync_db_url, tablename="apscheduler_jobs")}

scheduler = AsyncIOScheduler(jobstores=jobstores)


def start_scheduler():
    """Starts the background scheduler and adds the polling job if not exists."""
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")

    # Add the polling job to run every 10 seconds.
    # replace_existing=True ensures we don't pile up jobs on restarts.
    scheduler.add_job(
        poll_due_slots,
        "interval",
        seconds=10,
        id="poll_due_slots_job",
        replace_existing=True,
    )
    logger.info("Registered poll_due_slots_job (interval 10s)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped")
