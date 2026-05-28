import redis
from rq import Queue
import json
from app.core.config import settings


class RedisEngine:
    def __init__(self):
        try:
            self.client = redis.Redis(
                    host=settings.REDIS_HOST, 
                    port=settings.REDIS_PORT, 
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD
                )
            self.queue = Queue(connection=self.client)
        except Exception as e:
            print(f"Error connecting to Redis: {e}")
            raise

    def enqueue_job(self, function: str, job_data: dict):
        # Encuar tasca
        try:
            job = self.queue.enqueue(
                function, 
                json.dumps(job_data)
            )
            # Al encuar sempre fem al redis i sempre es una tasca de processament de video
        
        except Exception as e:
            print(f"Error enqueuing job: {e}")
            raise