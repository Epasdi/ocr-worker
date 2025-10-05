import os
from dotenv import load_dotenv
from redis import Redis
from rq import Worker, Queue, Connection

load_dotenv()
listen = ["ocr"]
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

conn = Redis.from_url(redis_url)
with Connection(conn):
    worker = Worker(map(Queue, listen))
    worker.work(with_scheduler=True)
