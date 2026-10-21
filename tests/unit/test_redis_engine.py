import pytest

from app.cache_redis.redis_engine import RedisEngine
from app.cache_redis.tasks import process_video


def test_enqueue_job_puts_the_task_on_the_default_queue(job_queue):
    RedisEngine().enqueue_job(process_video, 99)

    [job] = job_queue.jobs
    assert job.func_name == "app.cache_redis.tasks.process_video"
    assert job.args == (99,)
    assert job.timeout == 36000  # long videos take hours to process


def test_enqueue_errors_are_propagated(monkeypatch):
    engine = RedisEngine()

    def broken_enqueue(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr(engine.queue, "enqueue", broken_enqueue)

    with pytest.raises(ConnectionError):
        engine.enqueue_job(process_video, 1)
