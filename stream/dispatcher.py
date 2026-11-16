"""Publish topic requests every two seconds; every tenth random request lacks zone."""
import argparse, json, random, time, uuid
from datetime import datetime, timezone
import pika
try:
    from .common import EXCHANGE, connect, log
except ImportError:
    from common import EXCHANGE, connect, log

PROBES = ['bangalore.koramangala.food', 'bangalore.indiranagar.ride',
          'bangalore.whitefield.ride', 'chennai.tnagar.food',
          'chennai.whitefield.ride', 'bangalore.koramangala']
ZONES = {'bangalore': ['koramangala', 'indiranagar', 'whitefield'],
         'chennai': ['tnagar', 'whitefield']}

def publish(channel, key, payload):
    try:
        channel.basic_publish(exchange=EXCHANGE, routing_key=key,
                              body=json.dumps(payload).encode(), mandatory=True,
                              properties=pika.BasicProperties(content_type='application/json'))
        log(event='PUBLISHED', routing_key=key, id=payload['id'], bad='zone' not in payload)
    except pika.exceptions.UnroutableError:
        log(event='DROPPED_NO_BINDING', routing_key=key, id=payload['id'], bad='zone' not in payload)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=120)
    parser.add_argument('--seed', type=int, default=64)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.duration <= 0: parser.error('duration must be positive')
    rng = random.Random(args.seed)
    conn = connect(); channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic')
    channel.confirm_delivery()
    try:
        if args.probe:
            for i, key in enumerate(PROBES, 1):
                words = key.split('.')
                publish(channel, key, {'id': f'D1-{i}', 'city': words[0], 'zone': words[1],
                    'type': words[2] if len(words) == 3 else 'food',
                    'ts': datetime.now(timezone.utc).isoformat()})
        start = time.monotonic(); i = 0
        while time.monotonic() - start < args.duration:
            i += 1
            city = rng.choice(list(ZONES)); zone = rng.choice(ZONES[city]); kind = rng.choice(['ride', 'food'])
            # Keep bad messages routable so their NACKs can be observed reliably.
            if i % 10 == 0: city, zone, kind = 'bangalore', 'koramangala', 'food'
            payload = {'id': f'R-{i:03d}-{uuid.uuid4().hex[:8]}', 'city': city, 'zone': zone,
                       'type': kind, 'ts': datetime.now(timezone.utc).isoformat()}
            if i % 10 == 0: del payload['zone']
            publish(channel, f'{city}.{zone}.{kind}', payload)
            delay = min(start + i * 2, start + args.duration) - time.monotonic()
            if delay > 0: conn.sleep(delay)
        log(event='FINISHED', random_messages=i, elapsed_seconds=round(time.monotonic()-start,3))
    finally:
        conn.close()

if __name__ == '__main__': main()
