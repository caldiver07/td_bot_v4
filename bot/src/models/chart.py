
from .order import Order
from .position import Position
from .stats import Stats
from datetime import datetime

class Chart:
    def __init__(self, redis_client=None):
        self.redis_client = redis_client

        self.rank = 0
        self.stream_id = None
        self.symbol = None
        self.algo_type = None
        self.bid = None
        self.bid_size = None
        self.ask = None
        self.ask_size = None
        self.size_gap = None
        self.last = None
        self.volume = None
        self.level_2_volume = 0
        self.time_to_clear = None
        self.days_high = None
        self.days_low = None
        self.tmstamp = None
        self.ba_gap = 0
        self.hl_gap = 0

        self.current_vol = None
        self.previous_vol = None
        self.current_tmstamp = None
        self.previous_tmstamp = None

        #### Objects....
        self.order_opening = Order("", self.symbol, 0)
        self.order_closing = Order("", self.symbol, 0)
        self.position = None
        self.has_position = False
        self.stats = Stats(redis_client=redis_client)

        self.trade_order = False
        self.quantity = 20
        
        self.pause_orders = False
        self.paused_reason = "" ## opening / closing / volatility

        self.update_order_opening_flag = False
        self.update_order_closing_flag = False

        self.can_short = True

        self.exit_position_count = 0

        #### Transing indicators
        self.smart_direction = None
        self.spoofing_detected = 'no'
        self.level_2_obi = 0
        self.liq_consump_rate = 0
        self.spread_volatility = 0
        self.trend = "NA"
        self.vwap_distance_cents = 0.0
        self.avg_vwap_extension = 0.0
        
        self.last_opening_order_time = 0
        self.last_closing_order_time = 0

    def load_from_dict(self, data):
        def format_price(val):
            try:
                return f"{float(val):.2f}" if val is not None and val != "" else val
            except (ValueError, TypeError):
                return val

        
        self.stream_id = data.get('stream_id') or "NA"
        bid_val = data.get('bid')
        self.bid = format_price(bid_val) if bid_val is not None else self.bid
        
        ask_val = data.get('ask')
        self.ask = format_price(ask_val) if ask_val is not None else self.ask
        
        self.smart_direction = data.get('smart_direction') or self.smart_direction
        self.spoofing_detected = data.get('spoofing_detected') or self.spoofing_detected
        self.level_2_obi = data.get('level_2_obi') or self.level_2_obi
        self.liq_consump_rate = data.get('liq_consump_rate') or self.liq_consump_rate
        self.spread_volatility = data.get('spread_volatility') or self.spread_volatility
        self.can_short = data.get('can_short') or False
        self.trend = data.get('trend', self.trend)
        self.current_vol = data.get('current_vol', self.current_vol)
        self.volume = data.get('volume', 0)
        self.level_2_volume = data.get('level_2_volume', self.level_2_volume)
        self.time_to_clear = data.get('time_to_clear') or 0.0
        self.vwap_distance_cents = data.get('vwap_distance_cents') or self.vwap_distance_cents
        self.avg_vwap_extension = data.get('avg_vwap_extension') or self.avg_vwap_extension
        self.algo_type = data.get('algo_type') or ""

        self.pause_orders = True
        self.paused_reason = ""
        
        if "flat" in self.algo_type:
            if not getattr(self, 'algo_flat_enabled', True):
                self.pause_orders = True
                self.paused_reason = "disabled flat algo "
            else:
                self.pause_orders = False
                self.paused_reason = ""
        elif "vwap" in self.algo_type:
            if not getattr(self, 'algo_vwap_enabled', True):
                self.pause_orders = True
                self.paused_reason = "disabled vwap algo"
            else:
                self.pause_orders = False
                self.paused_reason = ""
        elif self.algo_type:
            self.pause_orders = True
            self.paused_reason = "no algo type set"


    def to_dict(self):
        return {
            'rank': self.rank,
            'stream_id': self.stream_id,
            'symbol': self.symbol,
            'algo_type': self.algo_type,
            'bid': self.bid,
            'bid_size': self.bid_size,
            'ask': self.ask,
            'ask_size': self.ask_size,
            'size_gap': self.size_gap,
            'last': self.last,
            'volume': self.volume,
            'days_high': self.days_high,
            'days_low': self.days_low,
            'tmstamp': self.tmstamp,
            'ba_gap': self.ba_gap,
            'hl_gap': self.hl_gap,
            'trade_order': self.trade_order,
            'stats': self.stats.to_dict() if self.stats else None,
            'pause_orders': self.pause_orders,
            'paused_reason': self.paused_reason,
            'order_opening': self.order_opening.to_dict() if self.order_opening else None,
            'order_closing': self.order_closing.to_dict() if self.order_closing else None,
            'position': self.position.to_dict() if self.position else None,
            'has_position': self.has_position,
            'can_short': self.can_short,
            'smart_direction': self.smart_direction,
            'spoofing_detected': self.spoofing_detected,
            'level_2_obi': self.level_2_obi,
            'liq_consump_rate': self.liq_consump_rate,
            'spread_volatility': self.spread_volatility,
            'trend': self.trend,
            'current_vol': self.current_vol,
            'level_2_volume': self.level_2_volume,
            'time_to_clear': self.time_to_clear,
        }