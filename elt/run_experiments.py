"""Capture actual B1-B5 results from the student's own Snowflake account."""
import copy, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from elt import freshcart as f
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'evidence'

def save(name, value):
    (EVIDENCE/name).write_text(json.dumps(value, indent=2, default=str))
    print(name, json.dumps(value, default=str), flush=True)

def run():
    f.connect_snowflake()
    f.run_sql(f.SQL_00_SETUP)
    # Never drop an existing database to force the expected count.
    count = f.query('SELECT COUNT(*) FROM bronze.orders_raw')[0][0]
    if count: raise RuntimeError('Use a fresh dedicated FRESHCART trial database for the baseline; existing data was preserved')
    f.SQL_10_ORDERS_CLEAN = f.SQL_10_ORDERS_CLEAN_BASELINE
    f.run_pipeline()
    baseline = {'bronze_rows':f.query('SELECT COUNT(*) FROM bronze.orders_raw')[0][0],
        'silver_clean_rows':f.query('SELECT COUNT(*) FROM silver.orders_clean')[0][0],
        'quarantine_rows':f.query('SELECT COUNT(*) FROM quarantine.orders')[0][0],
        'dedup_rows':f.query('SELECT COUNT(*) FROM silver.orders_dedup')[0][0],
        'gold':f.gold_totals(), 'rejected_share':str(f.query('SELECT COUNT_IF(ARRAY_SIZE(reasons)>0)/COUNT(*) FROM silver.orders_checked')[0][0])}
    save('B1-baseline.json',baseline)
    assert baseline['bronze_rows']==8 and baseline['silver_clean_rows']==6
    assert baseline['quarantine_rows']==2 and baseline['dedup_rows']==4
    assert baseline['gold']=={'orders':4,'revenue_inr':'7785.00','loyalty_points':126}
    save('B2-raw-records.json',f.query("SELECT source,raw FROM bronze.orders_raw WHERE COALESCE(raw:order_id::STRING,raw:orderId::STRING) IN ('ORD-1003','ORD-1005','ORD-1001') ORDER BY ingest_seq"))
    save('B2-gold-records.json',f.query('SELECT order_id,order_date,tier,amount,currency,fx_rate,amount_inr,loyalty_points FROM gold.fct_orders ORDER BY order_id'))
    before=f.query("SELECT reasons FROM silver.orders_checked WHERE order_id='ORD-1006' ORDER BY ingest_seq LIMIT 1")[0][0]
    f.SQL_10_ORDERS_CLEAN = f.SQL_10_ORDERS_CLEAN_BASELINE.replace(
       "    IFF(amount <= 0, 'non_positive_amount', NULL)",
       "    IFF(currency IS NULL OR currency NOT IN ('INR', 'USD'), 'unsupported_currency', NULL),\n    IFF(amount <= 0, 'non_positive_amount', NULL)")
    f.run_pipeline()
    after=f.query("SELECT reasons FROM silver.orders_checked WHERE order_id='ORD-1006' ORDER BY ingest_seq DESC LIMIT 1")[0][0]
    b3={'checked_reasons_before':json.loads(before),'checked_reasons_after':json.loads(after),
        'stored_quarantine_reasons':json.loads(f.query("SELECT reasons FROM quarantine.orders WHERE order_id='ORD-1006'")[0][0]),
        'quarantine_rows':f.query('SELECT COUNT(*) FROM quarantine.orders')[0][0], 'gold':f.gold_totals()}
    save('B3-validation.json',b3)
    assert b3['quarantine_rows']==2 and 'unsupported_currency' in b3['checked_reasons_after']
    assert b3['gold']==baseline['gold']
    # The prediction file was committed before this experiment.
    prediction=json.loads((EVIDENCE/'B4-predictions.json').read_text())
    published_before=dict(f.query('SELECT order_id,published_at FROM gold.fct_orders'))
    f.MOCK_CRM_TIER_EVENTS.append({'cust_id':'CUST-02','email':'arjun.k@yahoo.in','tier':'Gold','effective_from':'2026-08-15'})
    f.run_pipeline()
    published_after=dict(f.query('SELECT order_id,published_at FROM gold.fct_orders'))
    tier,points=f.query("SELECT tier,loyalty_points FROM gold.fct_orders WHERE order_id='ORD-1002'")[0]
    b4={'prediction':prediction,'actual':{'CUST-02 rows':f.query("SELECT COUNT(*) FROM dim.customers_scd2 WHERE cust_id='CUST-02'")[0][0],
         'ORD-1002 tier':tier,'ORD-1002 points':points,'gold total points':f.gold_totals()['loyalty_points'],
         'published_at changed rows':sum(published_before[k]!=v for k,v in published_after.items())},
         'customer_history':f.query("SELECT cust_id,tier,valid_from,valid_to,is_current FROM dim.customers_scd2 WHERE cust_id='CUST-02' ORDER BY valid_from")}
    save('B4-history.json',b4)
    for key,value in b4['actual'].items(): assert value==prediction[key],(key,value,prediction[key])
    snapshot=dict(f.query('SELECT order_id,published_at FROM gold.fct_orders'))
    bronze_before=f.query('SELECT COUNT(*) FROM bronze.orders_raw')[0][0]
    f.run_pipeline()
    b4_repeat={'bronze_growth':f.query('SELECT COUNT(*) FROM bronze.orders_raw')[0][0]-bronze_before,
        'gold':f.gold_totals(),'published_at_changed':sum(snapshot[k]!=v for k,v in f.query('SELECT order_id,published_at FROM gold.fct_orders'))}
    save('B4-idempotency.json',b4_repeat)
    assert b4_repeat['bronze_growth']==8 and b4_repeat['published_at_changed']==0
    # B5 adds a real synthetic raw order with a date in the future.
    future=f.query('SELECT DATEADD(day,1,CURRENT_DATE())')[0][0]
    mock=copy.deepcopy(f.MOCK_WEB_ORDERS[0]); mock.update(order_id='ORD-QC-FUTURE',order_date=str(future),
           updated_at=str(future)+' 12:00:00')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    path=f.write_landing('web',[mock],run_id)
    f.load_file(path,'bronze.orders_raw',f'qc_future/{run_id}')
    failed=f.transform_existing(run_id)
    save('B5-failed-check.json',{'mock_order':mock,'checks':failed})
    assert failed['orders dated in the future']==1
    # A source-only removal cannot undo append-only bronze or delete rows via MERGE.
    # Remove only this uniquely named experimental record from this isolated trial.
    f.query("DELETE FROM bronze.orders_raw WHERE source='web' AND raw:order_id::STRING='ORD-QC-FUTURE'")
    f.query("DELETE FROM gold.fct_orders WHERE order_id='ORD-QC-FUTURE'")
    recovered=f.transform_existing(run_id+'_recovered')
    save('B5-recovered-check.json',{'checks':recovered,'gold':f.gold_totals()})
    assert all(value==0 for value in recovered.values())
    # Suspend unused compute explicitly at the end of the experiment.
    f.query('ALTER WAREHOUSE FRESHCART_WH SUSPEND')
    f.conn.close()

if __name__=='__main__': run()
