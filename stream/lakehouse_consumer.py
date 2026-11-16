"""Collect FreshCart web orders for one minute and publish them through the real ELT."""
import argparse, copy, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
from stream.common import EXCHANGE, connect, log
from elt import freshcart as f

ROUTING_KEY = 'freshcart.orders'

def collect_batch(seconds=60):
    conn = connect(); channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic')
    # The bonus queue survives a consumer connection loss and can requeue unacked rows.
    channel.queue_declare(queue='freshcart-lakehouse-assignment', durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue='freshcart-lakehouse-assignment', routing_key=ROUTING_KEY)
    channel.basic_qos(prefetch_count=100)
    records, tags = [], []
    def receive(ch, method, properties, body):
        try:
            record = json.loads(body)
            assert isinstance(record,dict) and record.get('order_id')
        except (ValueError, AssertionError, UnicodeDecodeError):
            ch.basic_nack(delivery_tag=method.delivery_tag,requeue=False)
            log(event='BONUS_NACK_DISCARD'); return
        records.append(record); tags.append(method.delivery_tag)
        log(event='BONUS_RECEIVED',order_id=record['order_id'])
    channel.basic_consume(queue='freshcart-lakehouse-assignment', on_message_callback=receive, auto_ack=False)
    log(event='BONUS_READY',seconds=seconds)
    start=time.monotonic()
    while time.monotonic()-start < seconds:
        conn.process_data_events(time_limit=min(0.2, seconds-(time.monotonic()-start)))
    run_id=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    path=f.write_landing('web',records,run_id)
    # ACK only after the raw file closes successfully. SQL can be retried from the file.
    for tag in tags: channel.basic_ack(delivery_tag=tag)
    conn.close()
    log(event='BONUS_LANDED',count=len(records),elapsed_seconds=round(time.monotonic()-start,3))
    return records,path,run_id

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=60)
    parser.add_argument('--collect-only',action='store_true')
    args=parser.parse_args()
    records,path,run_id=collect_batch(args.seconds)
    if args.collect_only: return
    if not records: raise RuntimeError('No orders collected; nothing was published')
    f.connect_snowflake(); f.run_sql(f.SQL_00_SETUP)
    # Match the B4 final state when enriching the streamed orders.
    # Existing CRM history is preserved in bronze; no new baseline batch is needed.
    f.load_file(path,'bronze.orders_raw',f'stream/{run_id}')
    checks=f.transform_existing(run_id)
    first=f.gold_totals()
    ids=[r['order_id'] for r in records]
    # Replay the same payload in a new raw file so COPY really appends another copy.
    replay_id=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    replay=f.write_landing('web',records,replay_id)
    bronze_before=f.query('SELECT COUNT(*) FROM bronze.orders_raw')[0][0]
    published=dict(f.query('SELECT order_id,published_at FROM gold.fct_orders'))
    f.load_file(replay,'bronze.orders_raw',f'stream/{replay_id}')
    f.transform_existing(replay_id)
    second=f.gold_totals()
    changed=sum(published[k]!=v for k,v in f.query('SELECT order_id,published_at FROM gold.fct_orders'))
    result={'batch_order_ids':ids,'first_gold_totals':first,'second_gold_totals':second,
      'replay_bronze_growth':f.query('SELECT COUNT(*) FROM bronze.orders_raw')[0][0]-bronze_before,
      'published_at_changed_on_replay':changed,'checks':checks}
    assert first==second and changed==0
    assert result['replay_bronze_growth']==len(records)
    target=Path(__file__).resolve().parents[1]/'evidence/bonus-results.json'
    target.write_text(json.dumps(result,indent=2,default=str))
    print(json.dumps(result,indent=2,default=str))
    f.query('ALTER WAREHOUSE FRESHCART_WH SUSPEND');f.conn.close()

if __name__=='__main__': main()
