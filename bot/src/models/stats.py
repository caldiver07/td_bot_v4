
from datetime import datetime
import json
from collections import deque

class Stats:

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.rolling_size = 50 # Number of recent orders to track for rolling stats
        self.symbol = None

        #### Opening Order Stats...
        self.opening_order_count = 0
        self.opening_order_filled = 0
        self.opening_order_canceled = 0
        self.opening_order_filled_percent = 0.0
        self.opening_order_canceled_percent = 0.0

        ### Rolling last 100 orders tracking
        self.opening_orders_history = deque(maxlen=self.rolling_size)  # Stores 'filled', 'canceled', or 'other'
        self.opening_order_count_rolling = 0
        self.opening_order_filled_rolling = 0
        self.opening_order_canceled_rolling = 0
        self.opening_order_filled_percent_rolling = 0.0
        self.opening_order_canceled_percent_rolling = 0.0

        #### Closing Order Stats....
        self.closing_order_count = 0
        self.closing_order_filled = 0
        self.closing_order_canceled = 0
        self.closing_order_replaced = 0
        self.closing_order_filled_percent = 0.0
        self.closing_order_canceled_percent = 0.0
        self.closing_order_replaced_percent = 0.0

        ### Rolling Clsing Order Stats
        self.closing_orders_history = deque(maxlen=self.rolling_size)  # Stores 'filled', 'canceled', or 'other'
        self.closing_order_count_rolling = 0
        self.closing_order_filled_rolling = 0
        self.closing_order_canceled_rolling = 0
        self.closing_order_replaced_rolling = 0
        self.closing_order_filled_percent_rolling = 0.0
        self.closing_order_canceled_percent_rolling = 0.0
        self.closing_order_replaced_percent_rolling = 0.0
        
        #### Time stats...... This is used to set how long a chart stays paused for.....
        self.started_date = datetime.utcnow()
        self.updated_date = datetime.utcnow()
        self.duration = None ### in minutes between started_date and updated_date
        self.age = None ### in minutes fro now and started_date
        self.paused = None
        self.stat_age_reset_minutes = 15  ### after this many minutes, the stats will reset

        ### Chart Streaming stats... updated from streaming.py
        self.chart_spread = 0  ### this is the spread between bid and ask in the chart
        self.chart_change = 0  ### this is how many time the bid changed in the chart
        self.current_change = 0 ### this is how many time the bid changed in the last 20 updates
        self.chart_status = 'neutral' ### this is the current status of the chart (bullish, bearish, neutral)
        self.current_status = 'neutral' ### this is the current status of the symbol (bullish, bearish, neutral)
    
    def reset_all_stats(self):
        self.reset_stats()
        ## Reset Opening Order Stats
        self.opening_order_count = 0
        self.opening_order_filled = 0
        self.opening_order_canceled = 0
        self.opening_order_filled_percent = 0.0
        self.opening_order_canceled_percent = 0.0

        ## Reset Closing Order Stats
        self.closing_order_count = 0
        self.closing_order_filled = 0
        self.closing_order_canceled = 0
        self.closing_order_replaced = 0
        self.closing_order_filled_percent = 0.0
        self.closing_order_canceled_percent = 0.0
        self.closing_order_replaced_percent = 0.0

    def reset_stats(self):
        # Rolling last 100 orders tracking
        self.opening_orders_history = deque(maxlen=self.rolling_size)  # Stores 'filled', 'canceled', or 'other'
        self.opening_order_count_rolling = 0
        self.opening_order_filled_rolling = 0
        self.opening_order_canceled_rolling = 0
        self.opening_order_filled_percent_rolling = 0.0
        self.opening_order_canceled_percent_rolling = 0.0

        ## Rolling Closing Order Stats
        self.closing_orders_history = deque(maxlen=self.rolling_size)  # Stores 'filled', 'canceled', or 'other'
        self.closing_order_count_rolling = 0
        self.closing_order_filled_rolling = 0
        self.closing_order_canceled_rolling = 0
        self.closing_order_replaced_rolling = 0
        self.closing_order_filled_percent_rolling = 0.0
        self.closing_order_canceled_percent_rolling = 0.0
        self.closing_order_replaced_percent_rolling = 0.0
       
        ### Reset Time Stuff.....
        self.started_date = datetime.utcnow()
        self.updated_date = datetime.utcnow()
        self.duration = None
        self.age = None
        self.paused = None

    def _recalculate_rolling_opening_stats(self):
        """Recalculate rolling stats based on last X orders"""
        self.opening_order_filled_rolling = self.opening_orders_history.count('filled')
        self.opening_order_canceled_rolling = self.opening_orders_history.count('canceled')
        
        total = len(self.opening_orders_history)
        if total > 0:
            self.opening_order_count_rolling = total
            self.opening_order_filled_percent_rolling = round((self.opening_order_filled_rolling / total) * 100, 1)
            self.opening_order_canceled_percent_rolling = round((self.opening_order_canceled_rolling / total) * 100, 1)
        else:
            self.opening_order_count_rolling = 0
            self.opening_order_filled_percent_rolling = 0.0
            self.opening_order_canceled_percent_rolling = 0.0

    def _recalculate_rolling_closing_stats(self):
        """Recalculate rolling stats based on last X orders"""
        self.closing_order_filled_rolling = self.closing_orders_history.count('filled')
        self.closing_order_canceled_rolling = self.closing_orders_history.count('canceled')
        
        total = len(self.closing_orders_history)
        if total > 0:
            self.closing_order_count_rolling = total
            self.closing_order_filled_percent_rolling = round((self.closing_order_filled_rolling / total) * 100, 1)
            self.closing_order_canceled_percent_rolling = round((self.closing_order_canceled_rolling / total) * 100, 1)
        else:
            self.closing_order_count_rolling = 0
            self.closing_order_filled_percent_rolling = 0.0
            self.closing_order_canceled_percent_rolling = 0.0

    def update_opening_order_count(self, chart):
        self.opening_order_count += 1
        self.updated_date =  datetime.utcnow()
        self.update_date_durations(chart)

    def update_opening_filled(self, chart):
        self.opening_order_filled += 1
        self.opening_orders_history.append('filled')
        self._recalculate_rolling_opening_stats()
        self.updated_date =  datetime.utcnow()
        self.update_date_durations(chart)
        self.update_opening_filled_percent()
        self.update_opening_canceled_percent()

    def update_opening_filled_percent(self):
        if self.opening_order_count > 0:
            self.opening_order_filled_percent = round((self.opening_order_filled / self.opening_order_count) * 100, 1)

    def update_opening_canceled(self, chart):
        self.opening_order_canceled += 1
        self.opening_orders_history.append('canceled')
        self._recalculate_rolling_opening_stats()
        self.updated_date =  datetime.utcnow()
        self.update_date_durations(chart)
        self.update_opening_canceled_percent()
        self.update_opening_filled_percent()
    
    def update_opening_canceled_percent(self):
        if self.opening_order_count > 0:
            self.opening_order_canceled_percent = round((self.opening_order_canceled / self.opening_order_count) * 100, 1)

    def update_closing_order_count(self, chart):
        self.closing_order_count += 1
        self.updated_date =  datetime.utcnow()
        self.update_date_durations(chart)

    def update_closing_filled(self, chart):
        self.closing_order_filled += 1
        self.closing_orders_history.append('filled')
        self._recalculate_rolling_closing_stats()
        self.updated_date =  datetime.utcnow()
        self.update_date_durations(chart)
        self.update_closing_filled_percent()
        self.update_closing_canceled_percent()

    def update_closing_filled_percent(self):
        if self.closing_order_count > 0:
            self.closing_order_filled_percent = round((self.closing_order_filled / self.closing_order_count) * 100, 1)

    def update_closing_canceled(self, chart):
        self.closing_order_canceled += 1
        self.closing_orders_history.append('canceled')
        self._recalculate_rolling_closing_stats()
        self.updated_date =  datetime.utcnow()
        self.update_date_durations(chart)
        self.update_closing_canceled_percent()
        self.update_closing_filled_percent()

    def update_closing_canceled_percent(self):
        if self.closing_order_count > 0:
            self.closing_order_canceled_percent = round((self.closing_order_canceled / self.closing_order_count) * 100, 1)

    def update_date_durations(self, chart):
        self.duration = round(((self.updated_date - self.started_date).total_seconds() / 60), 1)
        self.age = round(((datetime.utcnow() - self.started_date).total_seconds() / 60), 1)
        if chart.pause_orders:
            self.paused = round(((datetime.utcnow() - self.updated_date).total_seconds() / 60), 1)
        else:
            self.paused = 0.0

        # if self.age > self.stat_age_reset_minutes:
        #     self.reset_stats()

    def update_closing_replaced(self, chart):
        self.closing_order_replaced += 1
        self.closing_orders_history.append('replaced')
        self._recalculate_rolling_closing_stats()
        self.updated_date =  datetime.utcnow()
        self.update_date_durations(chart)
        self.update_closing_replaced_percent()
        self.update_closing_filled_percent()
        self.update_closing_canceled_percent()

    def update_closing_replaced_percent(self):
        if self.closing_order_count > 0:
            self.closing_order_replaced_percent = round((self.closing_order_replaced / self.closing_order_count) * 100, 1)


    def load_dict(self):
        data = self.redis_client.get(f"stats_v4:{self.symbol}")
        if data:
            data = json.loads(data)
        else:
            data = {}

        self.opening_order_count = data.get('opening_order_count', 0)
        self.opening_order_filled = data.get('opening_order_filled', 0)
        self.opening_order_canceled = data.get('opening_order_canceled', 0)
        self.opening_order_filled_percent = data.get('opening_order_filled_percent', 0.0)
        self.opening_order_canceled_percent = data.get('opening_order_canceled_percent', 0.0)

        # Load rolling history
        history = data.get('opening_orders_history', [])
        self.opening_orders_history = deque(history, maxlen=self.rolling_size)
        self._recalculate_rolling_opening_stats()

        # Load rolling history for closing orders
        closing_history = data.get('closing_orders_history', [])
        self.closing_orders_history = deque(closing_history, maxlen=self.rolling_size)
        self._recalculate_rolling_closing_stats()

        self.closing_order_count = data.get('closing_order_count', 0)
        self.closing_order_filled = data.get('closing_order_filled', 0)
        self.closing_order_canceled = data.get('closing_order_canceled', 0)
        self.closing_order_filled_percent = data.get('closing_order_filled_percent', 0.0)
        self.closing_order_canceled_percent = data.get('closing_order_canceled_percent', 0.0)
        
        self.started_date = datetime.fromisoformat(data.get('started_date')) if data.get('started_date') else datetime.utcnow()
        self.updated_date = datetime.fromisoformat(data.get('updated_date')) if data.get('updated_date') else datetime.utcnow()
        self.duration = data.get('duration', None)
        self.age = data.get('age', None)
        self.paused = data.get('paused', None)

    def to_dict(self):
        rtn = {
            'symbol': self.symbol,
            
            'opening_order_count': self.opening_order_count,
            'opening_order_filled': self.opening_order_filled,
            'opening_order_canceled': self.opening_order_canceled,
            'opening_order_filled_percent': self.opening_order_filled_percent,
            'opening_order_canceled_percent': self.opening_order_canceled_percent,

            # Rolling stats
            'opening_order_count_rolling': self.opening_order_count_rolling,
            'opening_order_filled_rolling': self.opening_order_filled_rolling,
            'opening_order_canceled_rolling': self.opening_order_canceled_rolling,
            'opening_order_filled_percent_rolling': self.opening_order_filled_percent_rolling,
            'opening_order_canceled_percent_rolling': self.opening_order_canceled_percent_rolling,
             # Store history for persistence
            'opening_orders_history': list(self.opening_orders_history),

            'closing_order_count': self.closing_order_count,
            'closing_order_filled': self.closing_order_filled,
            'closing_order_canceled': self.closing_order_canceled,
            'closing_order_filled_percent': self.closing_order_filled_percent,
            'closing_order_canceled_percent': self.closing_order_canceled_percent,

            # Rolling stats
            'closing_order_count_rolling': self.closing_order_count_rolling,
            'closing_order_filled_rolling': self.closing_order_filled_rolling,
            'closing_order_canceled_rolling': self.closing_order_canceled_rolling,
            'closing_order_filled_percent_rolling': self.closing_order_filled_percent_rolling,
            'closing_order_canceled_percent_rolling': self.closing_order_canceled_percent_rolling,
            # Store history for persistence
            'closing_orders_history': list(self.closing_orders_history),
            
            'chart_spread': self.chart_spread,
            'chart_change': self.chart_change,
            'chart_status': self.chart_status,
            'current_status': self.current_status,
            'current_change': self.current_change,

            'started_date': self.started_date.isoformat() if self.started_date else None,
            'updated_date': self.updated_date.isoformat() if self.updated_date else None,
            'duration': self.duration,
            'age': self.age,
            'paused': self.paused,
        }
        redis_write = self.redis_client.set(name=f"stats_v4:{self.symbol}", value=json.dumps(rtn), ex=43200)
        return rtn