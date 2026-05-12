import os
from datetime import datetime
from uuid import uuid4

from elasticsearch import Elasticsearch

class BotLog:
    def __init__(self, write_to_es):
        self.write_to_es = write_to_es
        self.es_url = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')

    def to_dict(self, record=None):
        if record is None:
            return {}

        normalized_record = dict(record)
        normalized_record['event_id'] = normalized_record.get('event_id') or str(uuid4())
        normalized_record['event_type'] = normalized_record.get('event_type') or 'bot_v4'
        normalized_record['event_date'] = normalized_record.get('event_date') or datetime.utcnow().isoformat()

        return normalized_record

    def build_records(self, payload):
        if isinstance(payload, list):
            return [self.to_dict(record) for record in payload if isinstance(record, dict)]

        if not isinstance(payload, dict):
            raise TypeError('BotLog payload must be a dict or a list of dict records')

        stream_snapshot = payload.get('stream', {})
        if not isinstance(stream_snapshot, dict):
            return [self.to_dict(payload)]

        bot_stats = payload.get('stats', {}) if isinstance(payload.get('stats', {}), dict) else {}
        event_date = datetime.utcnow().isoformat()
        shared_fields = {
            'event_date': event_date,
            'event_type': 'bot_v4',
            'bot_phase': bot_stats.get('phase'),
            'bot_status': bot_stats.get('status'),
            'bot_sub_status': bot_stats.get('sub_status'),
            'bot_message': bot_stats.get('message'),
            'paused_charts': stream_snapshot.get('paused_charts', 0),
            'order_count': stream_snapshot.get('order_count', 0),
        }

        records = []
        for chart_name, chart_data in stream_snapshot.items():
            if not isinstance(chart_data, dict) or not chart_data.get('symbol'):
                continue

            record = dict(shared_fields)
            record['chart_name'] = chart_name
            record.update(chart_data)
            records.append(self.to_dict(record))

        if records:
            return records

        return [self.to_dict(payload)]
    
    def add_event(self, payload):
        records = self.build_records(payload)

        if not records or not self.write_to_es:
            return records

        return self.index_event(records)

    def add_events(self, payload):
        return self.add_event(payload)
    
    def index_event(self, payload) -> dict:
        """
        Index bot log records into Elasticsearch.

        Parameters:
        payload: dict or list of dict records to index
        es_client: optional Elasticsearch client. If not provided, one will be created
                    using the ELASTICSEARCH_URL environment variable (default: http://elasticsearch:9200).
        index_format: strftime-style format for the index name (default 'bot_v4.%Y.%m.%d')

        Returns:
        The response dict returned by Elasticsearch `bulk` API.

        Raises:
        RuntimeError if the elasticsearch client library is not available or the index operation fails.
        """
        if Elasticsearch is None:
            raise RuntimeError("elasticsearch package not installed; please add it to requirements.txt")

        records = self.build_records(payload)
        es_client = Elasticsearch([self.es_url])
        operations = []

        for record in records:
            doc = self.to_dict(record)
            event_date = datetime.fromisoformat(doc['event_date'])
            index_name = event_date.strftime('bot_v4.%Y.%m.%d')
            operations.append({'index': {'_index': index_name}})
            operations.append(doc)

        try:
            resp = es_client.bulk(operations=operations)

            if resp.get('errors'):
                first_error = None
                for item in resp.get('items', []):
                    index_result = item.get('index', {})
                    if index_result.get('error'):
                        first_error = index_result['error']
                        break
                raise RuntimeError(f"Failed to index bot log records to Elasticsearch: {first_error}")

            return resp
        except Exception as e:
            # Re-raise as RuntimeError for callers to handle easily
            raise RuntimeError(f"Failed to index bot log records to Elasticsearch: {e}")
        finally:
            es_client.close()