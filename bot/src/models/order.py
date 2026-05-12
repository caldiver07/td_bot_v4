
from datetime import datetime, timedelta

class Order:
    def __init__(self, order_id, symbol, qty, side="", type="", time_in_force="", status="", filled_qty=0, price=0, strategy_type="", parent_order_id="", parent_status="", entered_time=None, close_time=None, position_effect=None, order_timeout=6000, stuck_timeout_mult=4):
        self.order_id = order_id
        self.algo_type = None
        self.position_effect = position_effect
        self.strategy_type = strategy_type
        self.parent_order_id = parent_order_id 
        self.symbol = symbol
        self.qty = qty
        self.side = side
        self.type = type
        self.time_in_force = time_in_force
        self.status = status
        self.parent_status = parent_status
        self.filled_qty = filled_qty
        self.price = price
        self.order_date = datetime.utcnow()
        self.order_fetch_count = 0
        self.entered_time = entered_time
        self.close_time = close_time
        self.fill_time_seconds = self.calculate_fill_time()
        self.bot_status = 'Ready'  # Paused, Ready, **Order, Waiting, Countdown, Timeout, **Cancel
        self.timeout_date = None
        self.timeout_seconds = 0
        self.stuck_timeout_date = None
        self.price_shift = False  ## if the order has been placed but the price shifted off the mark we will want to use this to cancel the order sooner....
        self.order_timeout = order_timeout
        self.stuck_timeout_mult = stuck_timeout_mult
        self.order_placed = False
        self.order_placed_logged = False
        self.order_filled = False
        self.order_filled_logged = False
        self.order_canceled = False
        self.order_canceled_logged = False

    def to_dict(self):
        return {
            'order_id': self.order_id,
            'algo_type': self.algo_type,
            'position_effect': self.position_effect,
            'strategy_type': self.strategy_type,
            'parent_order_id': self.parent_order_id,
            'symbol': self.symbol,
            'qty': self.qty,
            'side': self.side,
            'type': self.type,
            'time_in_force': self.time_in_force,
            'status': self.status,
            'filled_qty': self.filled_qty,
            'bot_status': self.bot_status,
            'price': self.price,
            'order_date': self.order_date.isoformat(),
            'order_fetch_count': self.order_fetch_count,
            'entered_time': self._format_time(self.entered_time),
            'close_time': self._format_time(self.close_time),
            'fill_time_seconds': self.fill_time_seconds,
            'timeout_seconds': self.timeout_seconds
        }

    def _format_time(self, time_str):
        """Convert datetime string to local HH:MM:SS format"""
        if not time_str:
            return None
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            local_dt = dt.astimezone()
            return local_dt.strftime('%H:%M:%S')
        except:
            return time_str
    
    def calculate_fill_time(self):
        if self.entered_time and self.close_time:
            # Convert strings to datetime if needed
            entered = self.entered_time if isinstance(self.entered_time, datetime) else datetime.fromisoformat(self.entered_time.replace('Z', '+00:00'))
            closed = self.close_time if isinstance(self.close_time, datetime) else datetime.fromisoformat(self.close_time.replace('Z', '+00:00'))
            delta = closed - entered
            return delta.total_seconds()
        return None
    
    def update_order(self, new_order: 'Order'):
        from .. import events
        self.status = new_order.status
        self.parent_order_id = new_order.parent_order_id
        self.parent_status = new_order.parent_status
        self.qty = new_order.qty
        self.filled_qty = new_order.filled_qty
        self.price = new_order.price
        self.entered_time = new_order.entered_time
        self.close_time = new_order.close_time
        self.fill_time_seconds = new_order.fill_time_seconds
        self.side = new_order.side
        self.type = new_order.type
        self.time_in_force = new_order.time_in_force
        self.position_effect = new_order.position_effect
        self.strategy_type = new_order.strategy_type
        self.order_timeout = new_order.order_timeout
        self.stuck_timeout_mult = new_order.stuck_timeout_mult

    def update_bot_status(self):
        from .. import events
        # Reset timeout_date if the order transitions back to WORKING from something else or if a new fresh order comes in
        if self.status == 'WORKING':
            self.bot_status = 'Countdown'
            if not getattr(self, 'timeout_date', None):
                events.add_event(event_type="order_working", symbol=self.symbol, strategy_type=self.strategy_type, position_effect=self.position_effect)
                self.timeout_date = datetime.utcnow() + timedelta(milliseconds=self.order_timeout)
            if datetime.utcnow() >= self.timeout_date:
                self.bot_status = 'Timeout'
            if getattr(self, 'price_shift', False):
                self.bot_status = 'Shift'
            if getattr(self, 'timeout_date', None):
                self.timeout_seconds = int(round((self.timeout_date - datetime.utcnow()).total_seconds(), 0))

        #### Check for stuck AWAITING_PARENT_ORDER
        elif 'AWAITING_PARENT_ORDER' in self.status:
            self.bot_status = 'Waiting'
            if self.parent_status == 'FILLED':
                # Schwab takes time to convert AWAITING_PARENT_ORDER to WORKING. Give it seconds
                self.bot_status = 'Stuck'
                if not getattr(self, 'stuck_timeout_date', None):
                    self.stuck_timeout_date = datetime.utcnow() + timedelta(milliseconds=(self.order_timeout * self.stuck_timeout_mult))
                if getattr(self, 'stuck_timeout_date', None) and datetime.utcnow() >= self.stuck_timeout_date:
                    self.bot_status = 'Timeout'
                    events.add_event(event_type="order_stuck", symbol=self.symbol, strategy_type=self.strategy_type, position_effect=self.position_effect, order_type=self.type)

        elif 'REJECTED' in self.status:
            self.bot_status = 'Rejected'
            self.cancel_sent = False
            self.price_shift = False

        elif 'PENDING' in self.status or 'QUEUED' in self.status or 'AWAITING' in self.status or 'REPLACED' in self.status:
            self.bot_status = 'Waiting'

        elif self.status in ('CANCELED', 'FILLED',):
            self.bot_status = 'Ready'
            self.timeout_date = None # Clean up timers when done
            self.stuck_timeout_date = None
            self.cancel_sent = False
            self.price_shift = False
        else:
            self.bot_status = 'Unknown'

    def update_stats(self):
        if self.status in ['WORKING', 'AWAITING_PARENT_ORDER'] and self.order_placed_logged == False:
            self.order_placed = True
            
        if self.status == 'FILLED' and self.order_filled_logged == False:
            self.order_filled = True
            if self.order_placed == False and self.order_placed_logged == False:
                self.order_placed = True
                
        if self.status == 'CANCELED' and self.order_canceled_logged == False:
            self.order_canceled = True
            if self.order_placed == False and self.order_placed_logged == False:
                self.order_placed = True

class Orders:

    def __init__(self):
        self.orders = []

    def add_order(self, order):
        self.orders.append(order)

    def to_dict(self):
        if len(self.orders) == 0:
            return []
        else:
            #sorted_orders = sorted(self.orders, key=lambda o: o.entered_time or '', reverse=True)
            return [order.to_dict() for order in self.orders]