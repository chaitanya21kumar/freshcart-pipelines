"""Connection details stay outside source control."""
import json, os
from datetime import datetime, timezone
import pika
EXCHANGE = 'rapido-dispatch'

def connect():
    url = os.environ.get('AMQP_URL', 'amqp://guest:guest@127.0.0.1:5672/%2F')
    params = pika.URLParameters(url)
    params.heartbeat = 30
    params.blocked_connection_timeout = 30
    params.connection_attempts = 3
    params.retry_delay = 1
    return pika.BlockingConnection(params)

def log(**fields):
    print(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **fields}, sort_keys=True), flush=True)
