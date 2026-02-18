from src.orchestrator.scheduler import JobScheduler


class DummyConfig:
    def get(self, key, default=None):
        values = {
            "schedule.max_instances_per_job": 1,
            "schedule.misfire_grace_time_seconds": 120,
            "schedule.tiktok_creative_center_hours": 1,
            "schedule.aliexpress_hours": 2,
            "schedule.scoring_hours": 1,
            "schedule.alert_check_minutes": 10,
        }
        return values.get(key, default)


class DummyCoordinator:
    async def run_agent(self, *args, **kwargs):
        return None

    async def run_supplier_matching(self, *args, **kwargs):
        return None

    async def run_scoring(self, *args, **kwargs):
        return None

    async def check_alerts(self, *args, **kwargs):
        return None

    async def cleanup_old_data(self, *args, **kwargs):
        return None


def test_scheduler_sets_guardrail_defaults():
    scheduler = JobScheduler(DummyCoordinator(), DummyConfig())
    scheduler.configure_jobs()

    assert scheduler.scheduler._job_defaults["coalesce"] is True
    assert scheduler.scheduler._job_defaults["max_instances"] == 1
    assert scheduler.scheduler._job_defaults["misfire_grace_time"] == 120

    for job in scheduler.scheduler.get_jobs():
        assert job.max_instances == 1
