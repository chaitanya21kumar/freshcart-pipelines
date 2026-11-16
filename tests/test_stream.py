from types import SimpleNamespace
from unittest.mock import Mock
from stream.driver import handle

def test_good_message_is_acknowledged():
    channel=Mock(); method=SimpleNamespace(delivery_tag=7,routing_key='bangalore.koramangala.food')
    handle(channel,method,None,b'{"id":"good","zone":"koramangala"}','Ravi')
    channel.basic_ack.assert_called_once_with(delivery_tag=7)
    channel.basic_nack.assert_not_called()

def test_missing_zone_is_discarded_without_requeue():
    channel=Mock(); method=SimpleNamespace(delivery_tag=8,routing_key='bangalore.koramangala.food')
    handle(channel,method,None,b'{"id":"bad"}','Ravi')
    channel.basic_nack.assert_called_once_with(delivery_tag=8,requeue=False)
    channel.basic_ack.assert_not_called()

def test_malformed_json_is_discarded():
    channel=Mock(); method=SimpleNamespace(delivery_tag=9,routing_key='bangalore.koramangala.food')
    handle(channel,method,None,b'not json','Ravi')
    channel.basic_nack.assert_called_once_with(delivery_tag=9,requeue=False)
