"""Receive requests in a private exclusive queue and ACK or discard them."""
import argparse, json, time
try:
    from .common import EXCHANGE, connect, log
except ImportError:
    from common import EXCHANGE, connect, log

def handle(channel, method, properties, body, name):
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or 'zone' not in payload:
            raise ValueError('missing zone')
    except (ValueError, TypeError, UnicodeDecodeError) as error:
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        log(event='NACK_DISCARD', driver=name, routing_key=method.routing_key,
            id=payload.get('id') if isinstance(locals().get('payload'), dict) else None,
            reason=str(error))
        return
    log(event='PROCESSED', driver=name, routing_key=method.routing_key, id=payload.get('id'), zone=payload['zone'])
    channel.basic_ack(delivery_tag=method.delivery_tag)
    log(event='ACK', driver=name, routing_key=method.routing_key, id=payload.get('id'))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name'); parser.add_argument('pattern')
    parser.add_argument('--duration', type=float, default=0, help='0 means run until interrupted')
    args = parser.parse_args()
    conn = connect(); channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic')
    queue = channel.queue_declare(queue='', exclusive=True, auto_delete=True).method.queue
    channel.queue_bind(exchange=EXCHANGE, queue=queue, routing_key=args.pattern)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue, auto_ack=False,
        on_message_callback=lambda ch, method, properties, body: handle(ch, method, properties, body, args.name))
    log(event='READY', driver=args.name, pattern=args.pattern, queue=queue, exclusive=True)
    started = time.monotonic()
    try:
        while args.duration <= 0 or time.monotonic() - started < args.duration:
            conn.process_data_events(time_limit=0.2)
    except KeyboardInterrupt: pass
    finally:
        if conn.is_open: conn.close()
        log(event='STOPPED', driver=args.name)

if __name__ == '__main__': main()
