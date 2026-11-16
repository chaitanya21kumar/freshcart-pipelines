"""Publish two new synthetic orders for the one-minute bonus experiment."""
import copy,json,time
import pika
from stream.common import EXCHANGE,connect,log
from stream.lakehouse_consumer import ROUTING_KEY
from elt.freshcart import MOCK_WEB_ORDERS

def main():
    conn=connect();channel=conn.channel()
    channel.exchange_declare(exchange=EXCHANGE,exchange_type='topic');channel.confirm_delivery()
    for template,new_id,amount in [(MOCK_WEB_ORDERS[0],'ORD-2001','500.00'),
                                    (MOCK_WEB_ORDERS[2],'ORD-2002','10.00')]:
        order=copy.deepcopy(template);order.update(order_id=new_id,amount=amount)
        channel.basic_publish(exchange=EXCHANGE,routing_key=ROUTING_KEY,
            body=json.dumps(order),mandatory=True,
            properties=pika.BasicProperties(content_type='application/json',delivery_mode=2))
        log(event='BONUS_PUBLISHED',order_id=new_id);conn.sleep(2)
    conn.close()
if __name__=='__main__':main()
