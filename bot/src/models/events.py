
from datetime import datetime
from uuid import uuid4
import os
from typing import Optional
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta, time

import threading

class Event:
    def __init__(self, write_to_es):
        self.write_to_es = write_to_es

        #### Event Counters
        self.order_api_count = 0
        self.all_api_count = 0
        self.error_count = 0
        self.rate_limit_count = 0
        
        self._lock = threading.Lock()

    def add_event(self, event_type: str, symbol: Optional[str] = None, strategy_type: Optional[str] = None, position_effect: Optional[str] = None, chart_number: Optional[str] = None, order_type: Optional[str] = None, response_time: Optional[int] = 0, stream_id: Optional[str] = None, time_to_clear: Optional[float] = None):
        event_date = datetime.utcnow()
        
        doc = {
            'event_id': str(uuid4()),
            'stream_id': stream_id,
            'event_type': event_type,
            'event_date': event_date.isoformat(),
            'symbol': symbol,
            'strategy_type': strategy_type,
            'position_effect': position_effect,
            'chart_number': chart_number,
            'order_type': order_type,
            'response_time': response_time,
            'time_to_clear': time_to_clear
        }

        #### Update Counters safely
        with self._lock:
            if event_type in ["order_api_limit_cnt"]:
                self.order_api_count += 1
            if "fail" in event_type:
                self.error_count += 1
            if "rate_limit" in event_type:
                self.rate_limit_count += 1
            self.all_api_count += 1

        if self.write_to_es:
            self.index_event(doc, event_date)
            
    def index_event(self, doc: dict, event_date: datetime) -> dict | None:
        index_name = event_date.strftime("events_v3.%Y.%m.%d")
        es_client = None
        try:
            if Elasticsearch is None:
                raise RuntimeError("elasticsearch package not installed; please add it to requirements.txt")
            es_url = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
            es_client = Elasticsearch([es_url])
            resp = es_client.index(index=index_name, document=doc)
            return resp
        except Exception as e:
            print(f"Failed to index event to Elasticsearch: {e}")
            # Do not raise to prevent killing the ThreadPool
            return None
        finally:
            if es_client is not None:
                try:
                    es_client.close()
                except Exception:
                    pass
        
    def refresh_counters_from_es(self,
                             es_client: Optional[Elasticsearch] = None,
                             index_pattern: str = 'events_v3.*',
                             start_dt: Optional[datetime] = None,
                             end_dt: Optional[datetime] = None) -> dict:
        """
        Refresh counters from Elasticsearch for today (UTC).
        Returns a dict with keys: all_api_count, schwab_api_count, schwab_order_api_count
        """
        if es_client is None:
            es_url = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
            es_client = Elasticsearch([es_url])

        # Hard-code range to today (UTC)
        today = datetime.utcnow().date()
        start_dt = datetime.combine(today, time.min)
        end_dt = start_dt + timedelta(days=1)
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
        range_clause = {"range": {"event_date": {"gte": start_iso, "lt": end_iso}}}

        try:
            # all events today
            q_all = {"bool": {"must": [range_clause]}}

            # schwab order events today (place_order or cancel_order)
            q_orders = {"bool": {"must": [
                {"terms": {"event_type": ["order_api_limit_cnt"]}},
                range_clause
            ]}}

            resp_all = es_client.count(index=index_pattern, query=q_all)
            resp_orders = es_client.count(index=index_pattern, query=q_orders)

            counts = {
                "all_api_count": int(resp_all.body.get('count', 0)),
                "order_api_count": int(resp_orders.body.get('count', 0)),
            }

            self.all_api_count = counts['all_api_count']
            self.order_api_count = counts['order_api_count']

            return counts
        except Exception as e:
            raise RuntimeError(f"Failed to refresh counters from Elasticsearch: {e}")