import logging
import traceback
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, current_app, Response

from .. import schwab_client, trading_bot

bot = Blueprint('bot', __name__)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

@bot.route('/account-info/', methods=['GET'])
def account_info():
    ### get alpaca account info
    try:
        # Initialize client if needed
        account_details = schwab_client.account_details_all(timeout=6)

        return jsonify([account_details]), 200

    except Exception as e:
        print(f"Error fetching account info: {e}")
        return jsonify({'error': 'Failed to fetch account info'}), 500

@bot.route('/update-chart-settings/', methods=['POST'])
def update_chart_settings():
    try:
        data = request.json
        print(f"DEBUG: update_chart_settings received: {data}")

        # Handling list of config dicts or single config dict matching {symbol, trade...}
        configs = data if isinstance(data, list) else [data]

        for config in configs:
            if 'symbol' in config:
                for chart in schwab_client.stream.chart_list:
                    if chart.symbol == config['symbol']:
                        chart.trade_order = config.get('trade', False)
                        break

        schwab_client.charts_initialized = True
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        print(f"Error updating chart settings: {e}")
        return jsonify({'error': 'Invalid JSON data'}), 400

@bot.route('/load-chart-settings/', methods=['POST'])
def load_chart_settings():
    try:
        data = request.json
        symbols = []
        symbols = schwab_client.redis_client.get('stream_symbols')
        symbols = json.loads(symbols)
        schwab_client.stream.set_chart_symbols(symbols)

        schwab_client.charts_initialized = True
        schwab_client._load_history()
        return jsonify({'load chart settings': 'ok'}), 200
    except Exception as e:
        print(f"Error loading chart settings: {e}")
        return jsonify({'error': 'Invalid JSON data'}), 400
    
@bot.route('/update-settings/', methods=['POST'])
def update_settings():
    try:
        data = request.json

        schwab_client.auto_trading = data.get('auto_trading', schwab_client.auto_trading)
        schwab_client.order_timeout = data.get('order_timeout', schwab_client.order_timeout)
        schwab_client.paused_charts_threshold = data.get('paused_charts_threshold', schwab_client.paused_charts_threshold)
        schwab_client.stuck_timeout_mult = data.get('stuck_timeout_mult', schwab_client.stuck_timeout_mult)

        schwab_client.stream.pause_threshold = data.get('pause_threshold', schwab_client.stream.pause_threshold)
        schwab_client.stream.pause_threshold_2 = data.get('pause_threshold_2', schwab_client.stream.pause_threshold_2)
        schwab_client.stream.current_change_threshold = data.get('current_change_threshold', schwab_client.stream.current_change_threshold)

        schwab_client.stream.opening_fill_threshold = data.get('opening_fill_threshold', schwab_client.stream.opening_fill_threshold)
        schwab_client.stream.closing_fill_threshold = data.get('closing_fill_threshold', schwab_client.stream.closing_fill_threshold)
        schwab_client.stream.opening_order_threshold = data.get('opening_order_threshold', schwab_client.stream.opening_order_threshold)

        schwab_client.stream.paused_charts_timeout = data.get('paused_charts_timeout', schwab_client.stream.paused_charts_timeout)

        schwab_client.closing_order_multiplier = data.get('closing_order_multiplier', schwab_client.closing_order_multiplier)
        schwab_client.closing_timeout = data.get('closing_timeout', schwab_client.closing_timeout)
        schwab_client.group_order_multiplier = data.get('group_order_multiplier', schwab_client.group_order_multiplier)

        return jsonify({'auto_trading': 'ok'}), 200
    except Exception as e:
        print(f"Error fetching auto trading status: {e}")
        return jsonify({'error': 'Failed to fetch auto trading status'}), 500


@bot.route('/account-orders/', methods=['GET'])
def account_orders():
    account_hash = schwab_client.check_account_hash()
    orders_data = schwab_client.account_orders(accountHash=account_hash, maxResults=1000, range_minutes=300, status=None)

    return jsonify(orders_data), 200


@bot.route('/account-positions', methods=['GET'])
def account_positions():
    positions_data = schwab_client.account_positions(fields="positions")
    return jsonify(positions_data), 200


@bot.route('/bot', methods=['GET'])
def bot_route():
    data = trading_bot.last_rtn_data
    return Response(
        json.dumps(data, sort_keys=False, cls=DateTimeEncoder),
        mimetype='application/json'
    ), 200

@bot.route('/flush-redis', methods=['POST'])
def flush_redis():
    try:
        schwab_client.redis_client.flushdb()
        return jsonify({'status': 'Redis flushed successfully'}), 200
    except Exception as e:
        print(f"Error flushing Redis: {e}")
        return jsonify({'error': 'Failed to flush Redis'}), 500
    
@bot.route('/reset-stats/<symbol>', methods=['POST'])
def reset_stats(symbol):
    try:
        schwab_client.redis_client.delete(f"stats_v4:{symbol}")
        if hasattr(schwab_client, 'stream') and hasattr(schwab_client.stream, 'chart_list'):
            for chart in schwab_client.stream.chart_list:
                if chart.symbol == symbol:
                    if hasattr(chart, 'stats') and chart.stats:
                        chart.stats.reset_all_stats()
        return jsonify({'status': f'Stats reset for ' + symbol}), 200
    except Exception as e:
        print(f"Error resetting stats: {e}")
        return jsonify({'error': 'Failed to reset stats'}), 500
