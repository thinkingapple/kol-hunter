from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


class SchedulerManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._started = False

    def start(self):
        if not self._started:
            self.scheduler.start()
            self._started = True

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False

    def add_job(self, func, cron_expression: str, job_id: str, **kwargs):
        """Add a cron-scheduled job.

        cron_expression: standard 5-field "M H DoM Mon DoW"
        """
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        self.scheduler.add_job(
            func, trigger, id=job_id, replace_existing=True, **kwargs
        )

    def remove_job(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

    def get_jobs(self) -> list:
        return self.scheduler.get_jobs()


# Global scheduler instance
scheduler = SchedulerManager()
