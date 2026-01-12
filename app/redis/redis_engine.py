import redis
from rq import Queue
from rq.repeat import Repeat
import os
import json
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

class RedisEngine:
    def __init__(self):
        try:
            self.client = redis.Redis(
                    host=REDIS_HOST, 
                    port=REDIS_PORT, 
                    db=REDIS_DB,
                    password=REDIS_PASSWORD
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