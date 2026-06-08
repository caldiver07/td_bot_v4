import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
import pytz
from .common import utils
from .models.order import Orders, Order


if TYPE_CHECKING:
    from .client import Client
    from src import Event

class Bot:
    _threads_started = False
    
    def __init__(self, schwab_client: 'Client', events: 'Event'):
        self.schwab_client = schwab_client
        self.events = events

        self.search_limit = 300
        self.search_range_minutes = 15
        self.replace_order_flag = True

        ### Used to track and meter flat algo orders....
        self.max_flat_algo_orders = 3
        self.max_new_flat_algo_orders = 3

        self.active_flat_algo_orders = 0
        self.active_new_flat_algo_orders = 0

        self.exit_position_threshold = 1  ### The number of tries before we bail with a market order....

        ## Status to manage process.........
        
        self.phase = 'Ready'               # paused, opening, closing
        self.status = 'Ready'              # paused, opening_order, opening_order_fill, opening_triggers, opening_triggers_fill, closeing_order, closing_order_fill, closing_triggers, closing_triggers_fill, warning, error
        self.sub_status = 'Ready'          # paused, tbd
        self.message = ''

        self.opening_status = 'Ready' ## open / closed
        self.closing_status = 'Ready' ## open / closed
        self.position_status = 'closed' ## open / closed
        self.reject_count = 0
        self.reject_order_id = ''
        self._reject_alarm_stop_event = threading.Event()
        self._reject_alarm_thread = None
        self.market_exit = False

        self.cached_positions_data = {}
        self.cached_orders_data = []
        self.last_rtn_data = {
            "orders": {},
            "stream": [],
            "positions": [],
            "account": [],
            "stats": {
                "phase": "Ready",
                "status": "Ready",
                "sub_status": "Ready",
                "message": ""
            }
        }
        
        self._network_stop_event = threading.Event()
        self.pull_network_from_redis = False
        
        if self.pull_network_from_redis == False and not any(t.name == "NetworkFetcher" for t in threading.enumerate()):
            self._network_thread = threading.Thread(
                target=self._run_network_fetcher,
                daemon=True,
                name="NetworkFetcher"
            )
            self._network_thread.start()

        if not any(t.name == "AutomationLoop" for t in threading.enumerate()):
            self._automation_thread = threading.Thread(
                target=self._run_automation_loop,
                daemon=True,
                name="AutomationLoop"
            )
            self._automation_thread.start()

    def _startup_reconciliation(self, account_hash):
        """
        One-time independent boot sequence.
        Interrogates Schwab to find out what open positions and orders exist,
        and sets strict, clean slate for the Charts to use going forward.
        """
        print("DEBUG: Executing Clean State Startup Reconciliation...")
        
        # Pull latest orders and positions
        positions_data = self.schwab_client.account_positions(fields="positions")
        orders_data = self.schwab_client.account_orders(
            accountHash=account_hash, 
            maxResults=self.search_limit, 
            range_minutes=self.search_range_minutes, 
            status=None
        ) or []
        
        schwab_positions = {}
        if positions_data and isinstance(positions_data, dict):
            # account_positions returns {"positions": [...], "stream": {...}, "account": {...}}
            actual_positions = positions_data.get('positions', [])
            if actual_positions:
                for p in actual_positions:
                    sym = p.get('symbol')
                    qty = p.get('quantity', 0)
                    if sym:
                        schwab_positions[sym] = qty

        # Parse Schwab nested API orders into clean Order objects
        parsed_orders = []
        for o in orders_data:
            parsed_orders.append(self._fill_order_obj(o))
            for child in o.get("childOrderStrategies", []):
                parsed_orders.append(self._fill_order_obj(child, parent_order_id=o.get("orderId"), parent_status=o.get("status", "")))

        # Find any open working orders and cancel them 
        working_orders = [o for o in parsed_orders if o.status in ['WORKING', 'QUEUED', 'PENDING_ACTIVATION', 'AWAITING_PARENT_ORDER']]
        cancellations = []
        for ord_obj in working_orders:
            # Avoid duplicate cancellations for child orders if parent is canceled
            if not ord_obj.parent_order_id or not any(p.order_id == ord_obj.parent_order_id for p in cancellations):
                cancellations.append((account_hash, ord_obj.order_id))
                
        if cancellations:
            print(f"DEBUG: Found {len(cancellations)} lingering open orders on startup. Canceling them now for clean slate...")
            with ThreadPoolExecutor(max_workers=min(len(cancellations), 5)) as executor:
                futures = {executor.submit(self.schwab_client.order_cancel, acc, ord_id): ord_id for acc, ord_id in cancellations}
                for future in as_completed(futures):
                    try:
                        res = future.result()
                        print(f"DEBUG: Startup Cancel Result for {futures[future]}: {res}")
                    except Exception as e:
                        print(f"DEBUG: Startup Cancel Error: {e}")

        # Now set up the charts with clean default orders, and assign positions if they exist in Schwab
        for chart in self.schwab_client.stream.chart_list:
            
            # Wipe Redis state history for this session by starting with empty order objects
            time_stamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000')
            chart.order_opening = Order("", chart.symbol, 0, entered_time=time_stamp, order_timeout=self.schwab_client.order_timeout, stuck_timeout_mult=self.schwab_client.stuck_timeout_mult)
            chart.order_closing = Order("", chart.symbol, 0, entered_time=time_stamp, order_timeout=self.schwab_client.closing_timeout, stuck_timeout_mult=self.schwab_client.stuck_timeout_mult)
            chart.pending_open = False
            chart.pending_close = False
            
            # Rehydrate Position Reality completely from the broker
            if chart.symbol in schwab_positions:
                pos_qty = schwab_positions[chart.symbol]
                print(f"DEBUG: Startup Clean State found position for {chart.symbol} (Qty {pos_qty}).")
                from .models.position import Position
                chart.position = Position(chart.symbol, pos_qty, "LONG", 0, 0, 0)
                chart.has_position = True
            else:
                chart.has_position = False
                chart.position = None

        print("DEBUG: Clean State Reconciliation Complete.")

    def _run_automation_loop(self):
        # Wait for API token/account to load
        while not self._network_stop_event.is_set():
            if self.schwab_client.check_account_hash():
                break
            time.sleep(1)
            
        # Execute One-Time Boot Reconciliation
        if not self._network_stop_event.is_set():
            self._startup_reconciliation(self.schwab_client.account_hash)

        # Main Runtime Loop (Strict, NO guessing)
        while not self._network_stop_event.is_set():

            if self.schwab_client.charts_initialized:
                self.last_rtn_data = self.check_automation()
            
            time.sleep(0.01)

    def _run_network_fetcher(self):
        while not self._network_stop_event.is_set():
            
            account_hash = self.schwab_client.check_account_hash()
            if not account_hash:
                time.sleep(1)
                continue

            positions_data = self.schwab_client.account_positions(fields="positions")
            orders_data = self.schwab_client.account_orders(
                accountHash=account_hash, 
                maxResults=self.search_limit, 
                range_minutes=self.search_range_minutes, 
                status=None
            )

            self.cached_positions_data = positions_data if positions_data else {}
            self.cached_orders_data = orders_data if orders_data else []
                
            time.sleep(1)

    def check_automation(self):

        from src import bot_logs
        
        rtn_data = {}
        positions_data = {}
        orders_data = {}
        
        ### Check to see if charts are initialized....
        if not self.schwab_client.charts_initialized:
            assert False, "Charts not initialized"
        
        # Perform network IO bound operations concurrently
        account_hash = self.schwab_client.check_account_hash()
        
        # Use background thread cache for network IO
        if self.pull_network_from_redis == True and self.schwab_client.redis_client:
            positions_data = self.schwab_client.redis_client.get(f"account_positions:{account_hash}") or {}
            orders_data = self.schwab_client.redis_client.get(f"account_orders:{account_hash}") or []
            if orders_data: orders_data = json.loads(orders_data)
            if positions_data: positions_data = json.loads(positions_data)
        else:
            positions_data = self.cached_positions_data
            orders_data = self.cached_orders_data


        # Fast memory lookup
        self.schwab_client.stream.set_chart_data()

        if positions_data and positions_data.get('positions'):
            self.position_status = 'open'
        else:
            self.position_status = 'closed'

        # Safely integrate position data into Chart objects locally
        self._update_positions(positions_data)

        orders = self._update_orders(orders_data)

        self.calculate_status()

        # Process orders concurrently for all independent symbols
        self.place_opening_order()

        cancellations_open = self._cancellations_opening(account_hash)
        cancellations_closing = self._cancellations_closing(account_hash)

        # Perform cancellations concurrently
        if cancellations_open:
            self._place_cancel_opening_orders(cancellations_open)
        if cancellations_closing:
            self._place_cancel_closing_orders(cancellations_closing)

        ### Place closing orders for any straggling positions....
        self.place_closing_order()

        rtn_data = self._response_data(orders, positions_data)

        ## LOG DATA TO ELASTICSEARCH
        bot_logs.add_event(rtn_data)

        ## RETURN DATA FOR FRONTEND
        return rtn_data
    
    def _place_cancel_opening_orders(self, cancellations):
        with ThreadPoolExecutor(max_workers=min(len(cancellations), 5)) as executor:
            futures = {executor.submit(self.schwab_client.order_cancel, acc, ord_id): ord_id for acc, ord_id in cancellations}
            for future in as_completed(futures):
                ord_id = futures[future]
                failed = False
                try:
                    res_data = future.result()
                    # client.order_cancel returns a dict with 'status': 'ok' or 'error'
                    if res_data.get('status') != 'ok':
                        failed = True
                        print(f"DEBUG: Cancellation rejected for {ord_id}: {res_data.get('message', 'No message')}")
                except Exception as e:
                    failed = True
                    print(f"DEBUG: Cancellation exception {e} for {ord_id}")
                    
                if failed:
                    # If cancellation failed to network/limit, allow retry next loop!
                    for cht in self.schwab_client.stream.chart_list:
                        if getattr(cht.order_opening, 'order_id') == ord_id:
                            cht.order_opening.cancel_sent = False
                            cht.order_opening.bot_status = 'Shift' if getattr(cht.order_opening, 'price_shift', False) else 'Timeout'
                        elif getattr(cht.order_closing, 'order_id') == ord_id:
                            cht.order_closing.cancel_sent = False
                            cht.order_closing.bot_status = 'Shift' if getattr(cht.order_closing, 'price_shift', False) else 'Timeout'

    def _place_cancel_closing_orders(self, cancellations):

        #### Instead of cancelling, we will replace the order...
        if self.replace_order_flag:
            for acc, ord_id, cht in cancellations:
                #### if chart algo is flat....
                if cht.order_closing.side in ('BUY', 'BUY_TO_COVER'):
                    price = cht.bid 
                else:                    
                    price = cht.ask

                if cht.order_closing.replace_order_count > 1:
                    order_type = "MARKET"
                else:
                    order_type = "LIMIT"
                quantity = cht.position.quantity
                
                replace_payload = self.replace_order_payload(price=price, quantity=quantity, symbol=cht.symbol, instruction=cht.order_closing.side, orderType=order_type)
                
                self.schwab_client.replace_order(accountHash=acc, orderId=ord_id, order=replace_payload)
                cht.order_closing.replace_order_count += 1

        else:
            with ThreadPoolExecutor(max_workers=min(len(cancellations), 5)) as executor:
                futures = {executor.submit(self.schwab_client.order_cancel, acc, ord_id): ord_id for acc, ord_id, cht in cancellations}
                for future in as_completed(futures):
                    ord_id = futures[future]
                    failed = False
                    try:
                        res_data = future.result()
                        # client.order_cancel returns a dict with 'status': 'ok' or 'error'
                        if res_data.get('status') != 'ok':
                            failed = True
                            print(f"DEBUG: Cancellation rejected for {ord_id}: {res_data.get('message', 'No message')}")
                    except Exception as e:
                        failed = True
                        print(f"DEBUG: Cancellation exception {e} for {ord_id}")
                        
                    if failed:
                        # If cancellation failed to network/limit, allow retry next loop!
                        for cht in self.schwab_client.stream.chart_list:
                            if getattr(cht.order_opening, 'order_id') == ord_id:
                                cht.order_opening.cancel_sent = False
                                cht.order_opening.bot_status = 'Shift' if getattr(cht.order_opening, 'price_shift', False) else 'Timeout'
                            elif getattr(cht.order_closing, 'order_id') == ord_id:
                                cht.order_closing.cancel_sent = False
                                cht.order_closing.bot_status = 'Shift' if getattr(cht.order_closing, 'price_shift', False) else 'Timeout'

    def _cancellations_opening(self, account_hash):
        cancellations = []

        ### Cancel Timeout Opening Orders per chart....
        for cht in self.schwab_client.stream.chart_list:
            if cht.trade_order == False:
                continue
            
            is_vwap = getattr(cht.order_opening, 'algo_type', None) and 'vwap' in cht.order_opening.algo_type.lower()
            is_scalp = getattr(cht.order_opening, 'algo_type', None) and 'scalp' in cht.order_opening.algo_type.lower()
            is_flat = getattr(cht.order_opening, 'algo_type', None) and 'flat' in cht.order_opening.algo_type.lower()
            
            if cht.order_opening.bot_status == 'Countdown':
                try:
                    if is_vwap:
                        if cht.order_opening.side == 'BUY' and float(cht.ask) > float(cht.order_opening.price) + 0.15:
                            cht.order_opening.price_shift = True
                            cht.order_opening.bot_status = 'Shift'
                            print(f"DEBUG: VWAP Opening Shift Cancel for {cht.symbol} (Ask: {cht.ask} > Price: {float(cht.order_opening.price)} + 0.15)")
                        elif cht.order_opening.side in ['SELL', 'SELL_SHORT'] and float(cht.bid) < float(cht.order_opening.price) - 0.15:
                            cht.order_opening.price_shift = True
                            cht.order_opening.bot_status = 'Shift'
                            print(f"DEBUG: VWAP Opening Shift Cancel for {cht.symbol} (Bid: {cht.bid} < Price: {float(cht.order_opening.price)} - 0.15)")
                    elif is_scalp:
                        if cht.order_opening.side == 'BUY' and float(cht.bid) > float(cht.order_opening.price) + 0.10:
                            cht.order_opening.price_shift = True
                            cht.order_opening.bot_status = 'Shift'
                            print(f"DEBUG: Scalp Opening Shift Cancel for {cht.symbol} (Bid: {cht.bid} > Price: {cht.order_opening.price} + 0.10)")
                        elif cht.order_opening.side in ['SELL', 'SELL_SHORT'] and float(cht.ask) < float(cht.order_opening.price) - 0.10:
                            cht.order_opening.price_shift = True
                            cht.order_opening.bot_status = 'Shift'
                            print(f"DEBUG: Scalp Opening Shift Cancel for {cht.symbol} (Ask: {cht.ask} < Price: {cht.order_opening.price} - 0.10)")
                    else:
                        if cht.order_opening.side == 'BUY' and float(cht.bid) > float(cht.order_opening.price):
                            cht.order_opening.price_shift = True
                            cht.order_opening.bot_status = 'Shift'
                            print(f"DEBUG: Opening Shift Cancel for {cht.symbol} (Bid: {cht.bid} > Price: {cht.order_opening.price})")
                        elif cht.order_opening.side in ['SELL', 'SELL_SHORT'] and float(cht.ask) < float(cht.order_opening.price):
                            cht.order_opening.price_shift = True
                            cht.order_opening.bot_status = 'Shift'
                            print(f"DEBUG: Opening Shift Cancel for {cht.symbol} (Ask: {cht.ask} < Price: {cht.order_opening.price})")
                except (ValueError, TypeError):
                    pass

            is_timeout = cht.order_opening.bot_status == 'Timeout' and not is_vwap

            if (is_timeout or cht.order_opening.bot_status == 'Shift') and not getattr(cht.order_opening, 'cancel_sent', False):
                if cht.order_opening.order_id:
                    cht.order_opening.cancel_sent = True
                    cht.order_opening.bot_status = 'Canceling'  # Prevent multi-cancelling
                    cancellations.append((account_hash, cht.order_opening.order_id))

        return cancellations
    
    def _cancellations_closing(self, account_hash):

        cancellations = []

        #### Cancel Timout Closing Orders per chart....
        for cht in self.schwab_client.stream.chart_list:
            is_vwap = getattr(cht.order_closing, 'algo_type', None) and 'vwap' in cht.order_closing.algo_type.lower()
            is_scalp = getattr(cht.order_closing, 'algo_type', None) and 'scalp' in cht.order_closing.algo_type.lower()
            is_flat = getattr(cht.order_closing, 'algo_type', None) and 'flat' in cht.order_closing.algo_type.lower()

            if (getattr(cht.order_closing, 'algo_type', None) and 'vwap' in cht.order_closing.algo_type.lower()) or cht.trade_order == False:
                continue
            if cht.order_closing.bot_status == 'Countdown':
                try:
                    if is_scalp:
                        if cht.order_closing.side in ['BUY', 'BUY_TO_COVER'] and float(cht.bid) >= float(cht.order_opening.price):
                            cht.order_closing.price_shift = True
                            cht.order_closing.bot_status = 'Shift'
                            print(f"DEBUG: Scalp Closing {cht.order_closing.side} Shift Cancel for {cht.symbol} (Bid: {cht.bid} > Price: {cht.order_opening.price})")
                        elif cht.order_closing.side in ['SELL', 'SELL_SHORT'] and float(cht.ask) <= float(cht.order_opening.price):
                            cht.order_closing.price_shift = True
                            cht.order_closing.bot_status = 'Shift'
                            print(f"DEBUG: Scalp Closing {cht.order_closing.side} Shift Cancel for {cht.symbol} (Ask: {cht.ask} < Price: {cht.order_opening.price})")
                    else:
                        if cht.order_closing.side in ['BUY', 'BUY_TO_COVER'] and float(cht.bid) > float(cht.order_closing.price):
                            cht.order_closing.price_shift = True
                            cht.order_closing.bot_status = 'Shift'
                        elif cht.order_closing.side in ['SELL', 'SELL_SHORT'] and float(cht.ask) < float(cht.order_closing.price):
                            cht.order_closing.price_shift = True
                            cht.order_closing.bot_status = 'Shift'
                except (ValueError, TypeError):
                    pass

            # Only try to cancel and increment if we haven't already marked it as Canceling
            if (cht.order_closing.bot_status == 'Timeout' or cht.order_closing.bot_status == 'Shift') and not getattr(cht.order_closing, 'cancel_sent', False):
                if cht.order_closing.order_id:
                    cht.exit_position_count +=1
                    cht.order_closing.cancel_sent = True
                    cht.order_closing.bot_status = 'Canceling'  # Prevent double-counting on next loop
                    cancellations.append((account_hash, cht.order_closing.order_id, cht))

        return cancellations

    def _response_data(self, orders, positions_data):
        rtn_data = {}

        ## SET RESPONSE DATA
        rtn_data["orders"] = orders
        rtn_data["stream"] = self.schwab_client.stream.to_dict()
        rtn_data["positions"] = positions_data.get('positions', [])
        rtn_data["account"] = [positions_data.get('account', {})]
        rtn_data["stats"] = {
            "phase": self.phase,
            "status": self.status,
            "sub_status": self.sub_status,
            "message": self.message
        }
        return rtn_data

    def _update_positions(self, positions_data):
        from .models.position import Position
        
        # Parse the raw dictionary back into position objects to compare
        active_api_symbols = {}
        if positions_data and positions_data.get('positions'):
            for pos_dict in positions_data['positions']:
                symbol = pos_dict.get('symbol')
                if symbol:
                    qty = pos_dict.get('quantity', 0)
                    side = pos_dict.get('side', '')
                    active_api_symbols[symbol] = Position(
                        symbol=symbol,
                        quantity=qty,
                        side=side,
                        market_value=pos_dict.get('market_value', 0.0),
                        current_price=pos_dict.get('current_price', 0.0),
                        change_today=pos_dict.get('change_today', 0.0)
                    )

        for chart in self.schwab_client.stream.chart_list:
            api_pos = active_api_symbols.get(chart.symbol)
            is_assumed = getattr(chart.position, 'assumed', False)
            closing_filled = getattr(chart.order_closing, 'status', '') == 'FILLED'
            
            # Carry over algo_type from opening order
            current_algo_type = getattr(chart.order_opening, 'algo_type', None)

            # API is the single source of truth for positions.
            if api_pos:
                api_pos.algo_type = current_algo_type
                # We have a real position from the API.
                if is_assumed:
                    chart.position = api_pos
                    chart.position.assumed = False
                    chart.has_position = True
                    chart.pending_open = False
                elif chart.has_position or getattr(chart, 'pending_open', False):
                    # We expect this position
                    chart.position = api_pos
                    chart.has_position = True
                    chart.pending_open = False
                elif getattr(chart, 'pending_close', False):
                    # We are trying to close it, keep data updated until API says 0
                    chart.position = api_pos
                    chart.has_position = True
                else:
                    # Ignore phantom positions from other charts sharing this symbol
                    pass
            else:
                # API says NO position. Destroy it.
                if closing_filled or getattr(chart, 'pending_close', False):
                    chart.has_position = False
                    chart.position = None
                    chart.pending_close = False
                elif is_assumed and getattr(chart.position, 'position_age', lambda: 0)() > 30000:
                    # Assumed open position timed out without api confirmation
                    chart.has_position = False
                    chart.position = None
                    chart.pending_open = False
                elif not is_assumed:
                    chart.has_position = False
                    chart.position = None

    def _update_orders(self, orders_data):

        orders = Orders()

        self.schwab_client.stream.reset_chart_update_flags()
        
        ### Pre-sort orders to ensure the newest are processed FIRST
        orders_data = sorted(orders_data, key=lambda o: str(o.get('enteredTime', '')), reverse=True)

        ### Loop through the orders.....
        for order in orders_data:
            ord = self._fill_order_obj(order)
            orders.add_order(ord)
            self._update_charts(ord)

            #### check second leve...
            child_orders = order.get("childOrderStrategies", [])
            for child in child_orders:
                child_ord = self._fill_order_obj(child, parent_order_id=order.get("orderId"), parent_status=order.get("status", ""))
                orders.add_order(child_ord)
                self._update_charts(child_ord)

                ### Check third level......
                child_child_orders = child.get("childOrderStrategies", [])
                for cc in child_child_orders:
                    cc_ord = self._fill_order_obj(cc, parent_order_id=child.get("orderId"), parent_status=child.get("status", ""))
                    orders.add_order(cc_ord)
                    self._update_charts(cc_ord)
        
        self._update_Stats()
        return orders.to_dict()

    def _update_charts(self, order_data: dict):
        """
        Update internal chart symbols based on order data

        Args:
            order_data (dict): order data to update charts with
        """
        for chart in self.schwab_client.stream.chart_list:
            if chart.symbol == order_data.symbol:
                ord = order_data
                
                # Check for an exact ID match first. This prevents symbol crosstalk 
                # if the user adds the same symbol to multiple charts.
                exact_opening_match = (str(chart.order_opening.order_id) == str(ord.order_id)) if chart.order_opening.order_id else False
                exact_closing_match = (str(chart.order_closing.order_id) == str(ord.order_id)) if chart.order_closing.order_id else False
                
                if ord.position_effect == 'OPENING':
                    stale_capture = False
                    if getattr(chart.order_opening, 'entered_time', None) and getattr(ord, 'entered_time', None):
                        stale_capture = str(ord.entered_time) < str(chart.order_opening.entered_time)
                    
                    # For blank slots (like crash recovery), only adopt active orders OR filled orders ONLY IF we already possess the verified Schwab position
                    is_active_order = ord.status in ['WORKING', 'AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION']
                    is_verified_filled = ord.status == 'FILLED' and getattr(chart, 'has_position', False)
                    valid_blank_adoption = not chart.order_opening.order_id and chart.update_order_opening_flag == False and not stale_capture and (is_active_order or is_verified_filled)
                    
                    if exact_opening_match or valid_blank_adoption:
                        if exact_opening_match:
                            # Prevent Schwab's nested stale statuses from overwriting the real active status
                            stale_backtrack = chart.order_opening.status in ['WORKING', 'FILLED', 'CANCELED'] and ord.status in ['AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION']
                            if not stale_backtrack:
                                chart.order_opening.update_order(ord)
                        else:
                            ord.order_placed = chart.order_opening.order_placed
                            ord.order_placed_logged = chart.order_opening.order_placed_logged
                            ord.order_filled = chart.order_opening.order_filled
                            ord.order_filled_logged = chart.order_opening.order_filled_logged
                            ord.order_canceled = chart.order_opening.order_canceled
                            ord.order_canceled_logged = chart.order_opening.order_canceled_logged
                            ord.algo_type = getattr(chart.order_opening, 'algo_type', getattr(chart, 'algo_type', None))
                            ord.assumed_position_created = getattr(chart.order_opening, 'assumed_position_created', False)
                            chart.order_opening = ord
                            
                        chart.order_opening.update_bot_status()
                        chart.order_opening.update_stats()
                        
                        # ID-Based validation context: IF the open order fills, put in a local placeholder position
                        # waiting for Charles Schwab verification.
                        if chart.order_opening.status == 'FILLED' and not getattr(chart.order_opening, 'assumed_position_created', False):
                            chart.order_opening.assumed_position_created = True
                            if not getattr(chart.position, 'assumed', False) and not getattr(chart, 'has_position', False) and chart.order_closing.status != 'FILLED':
                                if chart.order_opening.side in ['BUY', 'BUY_TO_COVER']:
                                    pos_side = 'LONG'
                                else:
                                    pos_side = 'SHORT'
                                from .models.position import Position
                                chart.position = Position(chart.symbol, chart.order_opening.filled_qty, pos_side, 0, 0, 0, algo_type=getattr(chart.order_opening, 'algo_type', None))
                                chart.position.assumed = True
                                chart.has_position = True
                            
                        chart.update_order_opening_flag = True
                        break # Successfully mapped
                    elif chart.update_order_opening_flag == True:
                        if ord.status in ['WORKING', 'AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION'] and chart.order_opening.status not in ['WORKING', 'AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION']:
                            ord.order_placed = chart.order_opening.order_placed
                            ord.order_placed_logged = chart.order_opening.order_placed_logged
                            ord.order_filled = chart.order_opening.order_filled
                            ord.order_filled_logged = chart.order_opening.order_filled_logged
                            ord.order_canceled = chart.order_opening.order_canceled
                            ord.order_canceled_logged = chart.order_opening.order_canceled_logged
                            ord.algo_type = getattr(chart.order_opening, 'algo_type', getattr(chart, 'algo_type', None))
                            ord.assumed_position_created = getattr(chart.order_opening, 'assumed_position_created', False)
                            chart.order_opening = ord
                            chart.order_opening.update_bot_status()
                            chart.order_opening.update_stats()
                            
                            # ID-Based validation context: IF the open order fills, put in a local placeholder position
                            # waiting for Charles Schwab verification.
                            if chart.order_opening.status == 'FILLED' and not getattr(chart.order_opening, 'assumed_position_created', False):
                                chart.order_opening.assumed_position_created = True
                                if not getattr(chart.position, 'assumed', False) and not getattr(chart, 'has_position', False) and chart.order_closing.status != 'FILLED':
                                    if chart.order_opening.side in ['BUY', 'BUY_TO_COVER']:
                                        pos_side = 'LONG'
                                    else:
                                        pos_side = 'SHORT'
                                    from .models.position import Position
                                    chart.position = Position(chart.symbol, chart.order_opening.filled_qty, pos_side, 0, 0, 0, algo_type=getattr(chart.order_opening, 'algo_type', None))
                                    chart.position.assumed = True
                                    chart.has_position = True

                elif ord.position_effect == 'CLOSING':
                    # First check for an exact match to our tracked active closing order ID
                    if exact_closing_match:
                        # Prevent Schwab's nested stale statuses from overwriting the real active status
                        stale_backtrack = chart.order_closing.status in ['WORKING', 'FILLED', 'CANCELED'] and ord.status in ['AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION']
                        if not stale_backtrack:
                            chart.order_closing.update_order(ord)
                        chart.update_order_closing_flag = True
                        
                        # Wipe dead orders from the slot so the bot can place a crisp new fallback closing order
                        if chart.order_closing.status in ['REJECTED', 'CANCELED']:
                            # CRITICAL FIX: We MUST update the bot status to 'Ready'/'Rejected' BEFORE wiping the ID,
                            # otherwise the state machine freezes forever in 'Pending Verification'!
                            chart.order_closing.update_bot_status()
                            chart.order_closing.update_stats()
                            
                            chart.order_closing.order_id = ""
                            chart.order_closing.entered_time = None
                            chart.update_order_closing_flag = False
                            
                            if not self.reject_order_id or self.reject_order_id != ord.order_id:
                                self.reject_count +=1
                                self.reject_order_id = ord.order_id
                                
                        if chart.update_order_closing_flag:
                            chart.order_closing.update_bot_status()
                            chart.order_closing.update_stats()
                        break # Successfully mapped exactly what we were tracking

                    # If we don't have an exact ID match, ONLY map this order to our active tracker IF:
                    # 1. We are perfectly matched via the parent/child linkage of the current active trade.
                    parent_matches_active_trade = (str(ord.parent_order_id) == str(chart.order_opening.order_id)) if ord.parent_order_id and chart.order_opening.order_id else False
                    
                    # DETERMINISTIC PATH: Only adopt if natively linked to our opening ID.
                    # HOWEVER, Schwab sometimes flattens active child orders after the parent fills, stripping the parent link.
                    # If we possess the position, and we find an active working closing order for this symbol while we have a blank slot, adopt it.
                    orphaned_working_closing = (ord.status in ['WORKING', 'QUEUED'] and not chart.order_closing.order_id and getattr(chart, 'has_position', False))
                    orphaned_filled_closing = (ord.status == 'FILLED' and not chart.order_closing.order_id and getattr(chart.order_opening, 'entered_time', None) and str(ord.entered_time) > str(chart.order_opening.entered_time))

                    valid_blank_adoption_closing = parent_matches_active_trade or orphaned_working_closing or orphaned_filled_closing
                    
                    if not chart.update_order_closing_flag and valid_blank_adoption_closing:
                        
                        # Protect healthy tracking slots from being overwritten by delayed ghost messages 
                        # during a fuzzy match. Only allow exact ID matches to cancel a working/filled order.
                        if chart.order_closing.status in ['WORKING', 'FILLED', 'QUEUED', 'AWAITING_PARENT_ORDER', 'PENDING_ACTIVATION'] and ord.status in ['CANCELED', 'REJECTED']:
                            continue
                            
                        # CRITICAL FIX for the "ghosting" rejection loops:
                        # If our bot just placed a fresh closing order (bot_status == 'Pending Verification') but hasn't received 
                        # the specific order_id yet from the thread pool, we absolutely CANNOT allow an old CANCELED/REJECTED 
                        # order from earlier to blindly map into this empty slot and pretend to be the newest order!
                        if chart.order_closing.bot_status == 'Pending Verification' and ord.status in ['CANCELED', 'REJECTED']:
                            continue # Ignore ALL dead orders when we are explicitly waiting for a fresh live one
                            
                        # Safely inherit tracking flags before re-assigning so we don't duplicate stat counts
                        ord.order_placed = chart.order_closing.order_placed
                        ord.order_placed_logged = chart.order_closing.order_placed_logged
                        ord.order_filled = chart.order_closing.order_filled
                        ord.order_filled_logged = chart.order_closing.order_filled_logged
                        ord.order_canceled = chart.order_closing.order_canceled
                        ord.order_canceled_logged = chart.order_closing.order_canceled_logged
                        ord.algo_type = getattr(chart.order_closing, 'algo_type', getattr(chart, 'algo_type', None))
                        
                        chart.order_closing = ord
                        chart.update_order_closing_flag = True
                        
                        chart.order_closing.update_bot_status()
                        chart.order_closing.update_stats()
                        break # Successfully fuzzy mapped
                        
                    elif chart.update_order_closing_flag == True:
                        # Prioritize active working closing orders and FILLED orders over newer spam rejected/canceled ones
                        # ONLY if it belongs to the same parent order, or if it's the actual parent of the active trade
                        has_parent = bool(ord.parent_order_id) and bool(chart.order_opening.order_id)
                        same_family = has_parent and ((str(ord.parent_order_id) == str(chart.order_opening.order_id)) or (bool(chart.order_closing.parent_order_id) and str(ord.parent_order_id) == str(chart.order_closing.parent_order_id)))
                        
                        
                        if same_family and ord.status in ['WORKING', 'AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION', 'FILLED'] and chart.order_closing.status not in ['WORKING', 'AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION', 'FILLED']:
                            ord.order_placed = chart.order_closing.order_placed
                            ord.order_placed_logged = chart.order_closing.order_placed_logged
                            ord.order_filled = chart.order_closing.order_filled
                            ord.order_filled_logged = chart.order_closing.order_filled_logged
                            ord.order_canceled = chart.order_closing.order_canceled
                            ord.order_canceled_logged = chart.order_closing.order_canceled_logged
                            ord.algo_type = getattr(chart.order_closing, 'algo_type', getattr(chart, 'algo_type', None))
                            chart.order_closing = ord
                            chart.order_closing.update_bot_status()
                            chart.order_closing.update_stats()
                            break
                            
        # ENFORCE STRICT DETERMINISTIC RULES at the end of the update cycle
        for chart in self.schwab_client.stream.chart_list:
            if chart.symbol == order_data.symbol:
                # Boom Boom Clause: If Charles Schwab says the closing ID filled, the position is DEAD. Period.
                if chart.order_closing.status == 'FILLED':
                    chart.has_position = False
                            
        self._calculate_rank()

    def _fill_order_obj(self, order_data: dict, parent_order_id="", parent_status="") -> Order:
        
        filled_price = 0.0
        orderStrategyType = order_data.get("orderStrategyType", "")
        childOrderStrategies = order_data.get("childOrderStrategies", [])
        orderLegCollection = order_data.get("orderLegCollection", [])
        childOrderFirst = childOrderStrategies[0] if len(childOrderStrategies) > 0 else {}
        childOrderFirstOderStrategyType = childOrderFirst.get("orderStrategyType", "")

        if hasattr(order_data, 'orderLegCollection') and order_data['orderLegCollection'][0]['instruction'] in ['BUY', 'SELL_SHORT']:
            order_timeout = self.schwab_client.order_timeout
        else:
            order_timeout = self.schwab_client.closing_timeout
        
        if orderStrategyType and "oco" in orderStrategyType.lower():
            limitOrder = childOrderStrategies[1] if len(childOrderStrategies) > 1 else {}
            orderLegCollection = limitOrder.get("orderLegCollection", [])
            position_effect = orderLegCollection[0]['positionEffect']
            symbol = orderLegCollection[0]['instrument']['symbol']
            instruction = orderLegCollection[0]['instruction']
        elif orderStrategyType and "limit" in orderStrategyType.lower():
            position_effect = orderLegCollection[0]['positionEffect']
            symbol = orderLegCollection[0]['instrument']['symbol']
            instruction = orderLegCollection[0]['instruction']
        elif orderStrategyType and "single" in orderStrategyType.lower():
            position_effect = orderLegCollection[0]['positionEffect']
            symbol = orderLegCollection[0]['instrument']['symbol']
            instruction = orderLegCollection[0]['instruction']
            if order_data.get("orderType") == "MARKET":
                orderActivityCollection = order_data.get("orderActivityCollection", []) or []
                if orderActivityCollection and len(orderActivityCollection) > 0:
                    executionLegs = orderActivityCollection[0].get("executionLegs", []) or []
                    if executionLegs and len(executionLegs) > 0:
                        filled_price = executionLegs[0].get("price", 0.0)
                
        elif orderStrategyType and "trigger" in orderStrategyType.lower():
            position_effect = orderLegCollection[0]['positionEffect']
            symbol = orderLegCollection[0]['instrument']['symbol']
            instruction = orderLegCollection[0]['instruction']
        else:
            position_effect = orderLegCollection[0]['positionEffect']
            symbol = orderLegCollection[0]['instrument']['symbol']
            instruction = orderLegCollection[0]['instruction']

        ##if order_data.get("orderType") in ["MARKET","TRAILING_STOP","N/A"]:
        orderActivityCollection = order_data.get("orderActivityCollection", []) or []
        if orderActivityCollection and len(orderActivityCollection) > 0:
            executionLegs = orderActivityCollection[0].get("executionLegs", []) or []
            if executionLegs and len(executionLegs) > 0:
                filled_price = executionLegs[0].get("price", 0.0)
                
        price = order_data.get("price") or filled_price or 0.0
        order = Order(
            order_id=order_data.get("orderId"),
            position_effect=position_effect,
            strategy_type=order_data.get("orderStrategyType",""),
            parent_order_id=parent_order_id,
            parent_status=parent_status,
            symbol=symbol,
            qty=order_data.get("quantity"), 
            side=instruction,
            type=order_data.get("orderType"),
            time_in_force=order_data.get("timeInForce"),
            status=order_data.get("status"),
            filled_qty=order_data.get("filledQuantity"),
            price=price,
            entered_time=order_data.get("enteredTime"),
            close_time=order_data.get("closeTime"),
            order_timeout=order_timeout,
            stuck_timeout_mult=self.schwab_client.stuck_timeout_mult
        )
        return order
    
    def _update_Stats(self):
        for cnt, chart in enumerate(self.schwab_client.stream.chart_list):
            if not hasattr(chart, 'processed_events'):
                chart.processed_events = set()
                
            ### Opening Stats.....
            if chart.order_opening.order_placed and chart.order_opening.order_placed_logged == False:
                event_key = f"opening_placed_{chart.order_opening.order_id}"
                if event_key not in chart.processed_events:
                    chart.processed_events.add(event_key)
                    chart.stats.update_opening_order_count(chart)
                    self.events.add_event(event_type="opening_order_placed", symbol=chart.symbol, strategy_type=chart.order_opening.strategy_type, position_effect=chart.order_opening.position_effect, chart_number=f"chart-{cnt+1}", order_type=chart.order_opening.type, stream_id=chart.stream_id, time_to_clear=chart.time_to_clear)
                chart.order_opening.order_placed_logged = True
                
            if chart.order_opening.order_filled and chart.order_opening.order_filled_logged == False:
                event_key = f"opening_filled_{chart.order_opening.order_id}"
                if event_key not in chart.processed_events:
                    chart.processed_events.add(event_key)
                    chart.stats.update_opening_filled(chart)
                    self.events.add_event(event_type="opening_order_filled", symbol=chart.symbol, strategy_type=chart.order_opening.strategy_type, position_effect=chart.order_opening.position_effect, chart_number=f"chart-{cnt+1}", order_type=chart.order_opening.type, stream_id=chart.stream_id, time_to_clear=chart.time_to_clear)
                chart.order_opening.order_filled_logged = True
                
            if chart.order_opening.order_canceled and chart.order_opening.order_canceled_logged == False:
                event_key = f"opening_canceled_{chart.order_opening.order_id}"
                if event_key not in chart.processed_events:
                    chart.processed_events.add(event_key)
                    chart.stats.update_opening_canceled(chart)
                    self.events.add_event(event_type="opening_order_canceled", symbol=chart.symbol, strategy_type=chart.order_opening.strategy_type, position_effect=chart.order_opening.position_effect, chart_number=f"chart-{cnt+1}", order_type=chart.order_opening.type, stream_id=chart.stream_id, time_to_clear=chart.time_to_clear)
                chart.order_opening.order_canceled_logged = True
                
            #### Closing Stats...
            if chart.order_closing.order_placed and chart.order_closing.order_placed_logged == False:
                event_key = f"closing_placed_{chart.order_closing.order_id}"
                if event_key not in chart.processed_events:
                    chart.processed_events.add(event_key)
                    chart.stats.update_closing_order_count(chart)
                    self.events.add_event(event_type="closing_order_placed", symbol=chart.symbol, strategy_type=chart.order_closing.strategy_type, position_effect=chart.order_closing.position_effect, chart_number=f"chart-{cnt+1}", order_type=chart.order_closing.type, stream_id=chart.stream_id, time_to_clear=chart.time_to_clear)
                chart.order_closing.order_placed_logged = True
                
            if chart.order_closing.order_filled and chart.order_closing.order_filled_logged == False:
                event_key = f"closing_filled_{chart.order_closing.order_id}"
                if event_key not in chart.processed_events:
                    chart.processed_events.add(event_key)
                    chart.stats.update_closing_filled(chart)
                    chart.exit_position_count = 0  # Reset on successful fill
                    self.events.add_event(event_type="closing_order_filled", symbol=chart.symbol, strategy_type=chart.order_closing.strategy_type, position_effect=chart.order_closing.position_effect, chart_number=f"chart-{cnt+1}", order_type=chart.order_closing.type, stream_id=chart.stream_id, time_to_clear=chart.time_to_clear)
                chart.order_closing.order_filled_logged = True
                
            if chart.order_closing.order_canceled and chart.order_closing.order_canceled_logged == False:
                event_key = f"closing_canceled_{chart.order_closing.order_id}"
                if event_key not in chart.processed_events:
                    chart.processed_events.add(event_key)
                    chart.stats.update_closing_canceled(chart)
                    self.events.add_event(event_type="closing_order_canceled", symbol=chart.symbol, strategy_type=chart.order_closing.strategy_type, position_effect=chart.order_closing.position_effect, chart_number=f"chart-{cnt+1}", order_type=chart.order_closing.type, stream_id=chart.stream_id, time_to_clear=chart.time_to_clear)
                chart.order_closing.order_canceled_logged = True
    
    def place_opening_order(self):
        
        trade_orders = []
        account_hash = self.schwab_client.check_account_hash()

        #### Print Out Details...
        self.reject_count = 0
        self.reject_order_id = None

        self.market_exit = False

        ### SET ACTIVE FLAT ALGO COUNT
        self.active_flat_algo_orders = 0
        for track_chart in self.schwab_client.stream.chart_list:
            # Check if the chart is active: has an open position or currently working an order
            is_active = (track_chart.has_position or 
                         track_chart.order_opening.bot_status in ['Pending Verification', 'Working'] or
                         track_chart.order_opening.status in ['AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION', 'WORKING'])
            
            if is_active and track_chart.algo_type in ['flat_long', 'flat_short']:
                self.active_flat_algo_orders +=1

        ### Sort for highest percent filled.....
        if self.schwab_client.events.order_api_count > 100:
            sorted_charts = sorted(
                self.schwab_client.stream.chart_list,
                key=lambda chart: (chart.rank),reverse=False 
            )
        else:
            sorted_charts = self.schwab_client.stream.chart_list

        ##trade_order_count = sum(1 for chart in self.schwab_client.stream.chart_list if chart.trade_order)
        ##propect_flag = False

        self.active_new_flat_algo_orders = 0
        for cnt, chart in enumerate(sorted_charts):
           
            # Reset stale "Pending Verification" locks that never transitioned into an actual working order
            if chart.order_opening.bot_status == 'Pending Verification' and chart.order_opening.status not in ['AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION', 'REPLACED'] and (time.time() - chart.last_opening_order_time) > 30:
                print(f"DEBUG: Opening Stale Lock Reset for {chart.symbol}")
                chart.order_opening.bot_status = 'Ready'
                chart.pending_open = False
                
            # Prevent API race-condition spamming
            # Impose a strict 60-second penalty on REJECTED orders to break rejection spam loops.
            spam_guard = 0
            if chart.order_opening.status == 'REJECTED':
                spam_guard = 60
            if (time.time() - chart.last_opening_order_time) < spam_guard:
                continue
            
            # Independent tracking per chart: only place an opening order if the chart itself is Ready 
            # and doesn't already have an open position
            if 'scalp' in chart.algo_type and chart.paused_reason in ['opening','closing'] and getattr(chart, 'algo_scalp_enabled', True):
                is_paused = False
            else:
                is_paused = chart.pause_orders
            
            if chart.order_opening.bot_status in ['Ready', 'Unknown', 'Rejected'] and chart.has_position == False and chart.trade_order and is_paused == False:
                # Prevent placing a new prospect/opening order if the last one filled but Schwab's position API hasn't updated yet!
                # PROPOSAL 1: If the opening order is completely FILLED, do not allow a new opening order 
                # unless the closing order is explicitly FILLED. A canceled closing order does not mean we are flat.
                if chart.order_opening.status == 'FILLED' and getattr(chart.order_closing, 'status', None) != 'FILLED':
                    # SAFE ESCAPE HATCH: Guard against manual-close deadlocks
                    # Wait at least 120 seconds to ensure this is NOT just a temporary API lag waiting for the position to appear.
                    if getattr(chart.order_closing, 'status', None) in ['CANCELED', 'REJECTED'] \
                       and chart.has_position == False \
                       and (time.time() - chart.last_opening_order_time) > 120:
                        
                        print(f"DEBUG: Resolving manual close deadlock for {chart.symbol}. Resetting stale states.")
                        # Manually reset the status to force a clean slate on the NEXT loop iteration
                        chart.order_opening.status = ''
                        chart.order_closing.status = ''
                    continue
                    
                # Decide the logic
                if chart.algo_type == 'flat_long':
                    if self.active_flat_algo_orders >= self.max_flat_algo_orders:
                        print(f"DEBUG: Max active flat algo orders reached. Skipping new order for {chart.symbol}")
                        continue  # Skip placing new flat orders if we've reached the max active limit
                    instruction = 'BUY'
                elif chart.algo_type == 'flat_short':
                    if self.active_flat_algo_orders >= self.max_flat_algo_orders:
                        print(f"DEBUG: Max active flat algo orders reached. Skipping new order for {chart.symbol}")
                        continue  # Skip placing new flat orders if we've reached the max active limit
                    instruction = 'SELL_SHORT'
                elif chart.algo_type == 'vwap_long':
                    instruction = 'BUY'
                elif chart.algo_type == 'vwap_short':
                    instruction = 'SELL_SHORT'
                elif chart.algo_type == 'scalp_long':
                    instruction = 'BUY'
                elif chart.algo_type == 'scalp_short':
                    instruction = 'SELL_SHORT'
                else:
                    instruction = 'BUY'

                order_payload = self.place_order_payload(chart, instruction)
                if order_payload:
                    ### Keep a counter of active flat algo orders to prevent exceeding the max limit
                    if chart.algo_type in ['flat_long', 'flat_short']:
                        self.active_new_flat_algo_orders += 1

                    if self.active_new_flat_algo_orders >= self.max_new_flat_algo_orders:
                        print(f"DEBUG: Max new flat algo orders reached. Skipping new order for {chart.symbol}")
                        continue  # Skip placing new flat orders if we've reached the max new limit
                    
                    trade_orders.append((chart, order_payload))
                    time_stamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000')
                    chart.order_opening = Order("", chart.symbol, 0, entered_time=time_stamp, order_timeout=self.schwab_client.order_timeout, stuck_timeout_mult=self.schwab_client.stuck_timeout_mult, algo_type=chart.algo_type)
                    chart.order_opening.bot_status = 'Pending Verification' # Instantly prevent spamming next loop
                    chart.pending_open = True
                    chart.last_opening_order_time = time.time()
                    
                    # If this is a TRIGGER order, lock the closing order mechanism immediately 
                    # so we don't accidentally fire a duplicate closing sibling if the API is slow to update.
                    if order_payload.get("orderStrategyType") in ["TRIGGER", "TRIGGER_OCO"]:
                        chart.order_closing = Order("", chart.symbol, 0, entered_time=time_stamp, order_timeout=self.schwab_client.closing_timeout, stuck_timeout_mult=self.schwab_client.stuck_timeout_mult, algo_type=chart.algo_type)
                        chart.order_closing.bot_status = 'Pending Verification'
                        chart.last_closing_order_time = time.time()
                        
                    chart.exit_position_count = 0  # Reset for the new upcoming position

        ### Place Orders in parallel using threads....
        if trade_orders:
            with ThreadPoolExecutor(max_workers=len(trade_orders)) as executor:
                # Submit all orders simultaneously
                future_to_order = {executor.submit(self.schwab_client.order_place, account_hash, ord_payload): chart for chart, ord_payload in trade_orders}
                
                errors = []
                # Process results as they complete
                for future in as_completed(future_to_order):
                    chart = future_to_order[future]
                    try:
                        order_result = future.result()
                    except Exception as e:
                        order_result = {'status': 'error', 'message': f"Unexpected error during order placement: {str(e)}"}
                        
                    if order_result.get('status') == 'ok':
                        order_id = order_result.get('order_id')
                        if order_id:
                            chart.order_opening.order_id = order_id
                            self.events.add_event(event_type="opening_order_id_captured", symbol=chart.symbol)
                    else:
                        print(f"DEBUG: ORDER REJECTED/SKIPPED for {chart.symbol}. Reason: {order_result.get('message', 'No message')}")
                        chart.order_opening.bot_status = 'Ready' # Revert on error or warning
                        chart.pending_open = False
                        # If we pre-assumed a TRIGGER child order was going to happen but the parent failed, revert it!
                        if chart.order_closing.bot_status == 'Pending Verification' and not chart.has_position:
                            chart.order_closing.bot_status = 'Ready'
                            chart.pending_close = False
                        errors.append(order_result)
                
                if errors:
                    return errors[0]
                return {'status': 'ok', 'message': 'Orders placed successfully'}
        
        return {'status': 'ok', 'message': 'No orders to place'}

    def place_order_payload(self, chart, instruction):
        trigger_order = True

        if instruction in ['BUY']:
            if 'scalp' in chart.algo_type:
                price_gap = float(chart.ask) - float(chart.bid)
                price_offset_bid = price_gap * 0.20 if price_gap > 0.05 else 0.01
                price_offset_bid = round(price_offset_bid, 2)
                price_offset = price_gap * 0.30 if price_gap > 0.05 else 0.01
                price_offset = round(price_offset, 2)

                child_price = round(float(chart.ask) - price_offset, 2)  # For scalping longs, set child price below bid to ensure it doesn't execute immediately
                price = round(float(chart.bid) + price_offset_bid, 2)  # For scalping longs, price slightly above ask to increase fill probability
            else:
                child_price = float(chart.ask)
                price = float(chart.bid)

            # Enforce minimum 1-cent spread to avoid wash trades
            if child_price <= price:
                child_price = round(price + 0.01, 2)
                print(f"DEBUG: Adjusted child_price for {chart.symbol} to avoid wash trade: {child_price}")
                self.events.add_event(event_type="price_adjustment", symbol=chart.symbol)
        else:
            if 'scalp' in chart.algo_type:
                price_gap = float(chart.ask) - float(chart.bid)
                price_offset_ask = price_gap * 0.20 if price_gap > 0.05 else 0.01
                price_offset_ask = round(price_offset_ask, 2)
                price_offset = price_gap * 0.30 if price_gap > 0.05 else 0.01
                price_offset = round(price_offset, 2)

                child_price = round(float(chart.bid) + price_offset, 2)  # For scalping shorts, set child price above ask to ensure it doesn't execute immediately
                price = round(float(chart.ask) - price_offset_ask, 2)  # For scalping shorts, price slightly below bid to increase fill probability
            else:
                child_price = float(chart.bid)
                price = float(chart.ask)

            # Enforce minimum 1-cent spread to avoid wash trades
            if child_price >= price:
                child_price = round(price - 0.01, 2)
                print(f"DEBUG: Adjusted child_price for {chart.symbol} to avoid wash trade: {child_price}")
                self.events.add_event(event_type="price_adjustment", symbol=chart.symbol)

        if trigger_order and instruction in ['BUY', 'SELL_SHORT']:
            if chart.algo_type and 'vwap' in chart.algo_type:
                order_payload = self.limit_order_trigger_oco_payload(
                    symbol=chart.symbol,
                    quantity=chart.quantity,
                    instruction=instruction,
                    price=price,
                    child_price=child_price,
                    chart=chart
                )
            else:
                order_payload = self.limit_order_trigger_payload(
                    symbol=chart.symbol,
                    quantity=chart.quantity,
                    instruction=instruction,
                    price=price,
                    child_price=child_price,
                    chart=chart
                )
        else:
            order_payload = self.order_payload(
                symbol=chart.symbol,
                quantity=chart.quantity,
                instruction=instruction,
                price=price,
            )
        return order_payload
    
    def order_payload(self, price, quantity, symbol, instruction="BUY", orderType="LIMIT"):

        # Determine session based on current time
        session = utils.get_trading_session()

        order = {
            "orderType": orderType,
            "session": session,
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "price": price,
            "orderLegCollection": [
            {
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {
                    "symbol": symbol,
                    "assetType": "EQUITY"
                }
            }
            ]
        }
        return order
    
    def limit_order_trigger_oco_payload(self, price, child_price, quantity, symbol, instruction="BUY", duration="DAY", chart=None):
        session = utils.get_trading_session()
        if instruction == 'BUY':
            child_instruction = 'SELL'
        elif instruction == 'SELL_SHORT':
            child_instruction = 'BUY_TO_COVER'
        elif instruction == 'SELL':
            child_instruction = 'BUY'

        trailing_stop_offset = 0.10
        
        if chart and getattr(chart, 'avg_vwap_extension', None):
            vwap_ext = (chart.avg_vwap_extension or 0) * 0.01 ## Convert integer based cents to decimal dollars
            offset_dollars = abs(vwap_ext) * 0.50
            trailing_stop_offset = max(0.01, round(offset_dollars, 2))
            
            if getattr(chart, 'algo_type', '') and 'vwap' in chart.algo_type.lower():
                if instruction == 'BUY':
                    child_price = round(price + (vwap_ext) * 0.5, 2)
                elif instruction == 'SELL_SHORT':
                    child_price = round(price - (vwap_ext) * 0.5, 2)
                    
        child_limit_quantity = max(1, int(quantity / 2))
        remainder_quantity = quantity - child_limit_quantity

        child_strategies = [
            {
                "orderStrategyType": "OCO",
                "childOrderStrategies": [
                    {
                        "orderType": "LIMIT",
                        "session": session,
                        "price": child_price,
                        "duration": duration,
                        "orderStrategyType": "SINGLE",
                        "orderLegCollection": [
                            {
                                "instruction": child_instruction,
                                "quantity": child_limit_quantity,
                                "instrument": {
                                    "symbol": symbol,
                                    "assetType": "EQUITY"
                                }
                            }
                        ]
                    },
                    {
                        "orderType": "TRAILING_STOP",
                        "session": "NORMAL", # Stops generally only work in normal hours
                        "stopPriceLinkBasis": "MARK",
                        "stopPriceLinkType": "VALUE",
                        "stopPriceOffset": trailing_stop_offset,
                        "duration": duration,
                        "orderStrategyType": "SINGLE",
                        "orderLegCollection": [
                            {
                                "instruction": child_instruction,
                                "quantity": child_limit_quantity,
                                "instrument": {
                                    "symbol": symbol,
                                    "assetType": "EQUITY"
                                }
                            }
                        ]
                    }
                ]
            }
        ]

        if remainder_quantity > 0:
            child_strategies.append({
                "orderType": "TRAILING_STOP",
                "session": "NORMAL",
                "stopPriceLinkBasis": "MARK",
                "stopPriceLinkType": "VALUE",
                "stopPriceOffset": trailing_stop_offset,
                "duration": duration,
                "orderStrategyType": "SINGLE",
                "orderLegCollection": [
                    {
                        "instruction": child_instruction,
                        "quantity": remainder_quantity,
                        "instrument": {
                            "symbol": symbol,
                            "assetType": "EQUITY"
                        }
                    }
                ]
            })

        order = {
            "orderType": "LIMIT",
            "session": session,
            "duration": duration,
            "price": price,
            "orderStrategyType": "TRIGGER",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "EQUITY"
                    }
                }
            ],
            "childOrderStrategies": child_strategies
        }
        return order

    def limit_order_trigger_payload(self, price, child_price, quantity, symbol, instruction="BUY", duration="DAY", chart=None):  ### Old Duration "DAY, GOOD_TILL_CANCEL"

        # Determine session based on current time
        session = utils.get_trading_session()
        if instruction == 'BUY':
            child_instruction = 'SELL'
        elif instruction == 'SELL_SHORT':
            child_instruction = 'BUY_TO_COVER'
        elif instruction == 'SELL':
            child_instruction = 'BUY'

        order = {
            "orderType": "LIMIT",
            "session": session,
            "duration": duration,
            #"cancelTime": cancel_time,
            "price": price,
            "orderStrategyType": "TRIGGER",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "EQUITY"
                    }
                }
            ],
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": session,
                    "price": child_price,
                    "duration": duration,
                    #"cancelTime": cancel_time_close,
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": child_instruction,
                            "quantity": quantity,
                            "instrument": {
                                "symbol": symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                }
            ]
        }
        return order

    def calc_replace_closing_order(self, chart):
        ### Determine the price for the replacement order

        if chart.order_closing.instruction in ['BUY']:
            if 'scalp' in chart.algo_type:
                price_gap = float(chart.ask) - float(chart.bid)
                price_offset_bid = price_gap * 0.20 if price_gap > 0.05 else 0.01
                price_offset_bid = round(price_offset_bid, 2)
                price_offset = price_gap * 0.30 if price_gap > 0.05 else 0.01
                price_offset = round(price_offset, 2)

                child_price = round(float(chart.ask) - price_offset, 2)  # For scalping longs, set child price below bid to ensure it doesn't execute immediately
                price = round(float(chart.bid) + price_offset_bid, 2)  # For scalping longs, price slightly above ask to increase fill probability
            else:
                child_price = float(chart.ask)
                price = float(chart.bid)

            # Enforce minimum 1-cent spread to avoid wash trades
            if child_price <= price:
                child_price = round(price + 0.01, 2)
                print(f"DEBUG: Adjusted child_price for {chart.symbol} to avoid wash trade: {child_price}")
                self.events.add_event(event_type="price_adjustment", symbol=chart.symbol)
        else:
            if 'scalp' in chart.algo_type:
                price_gap = float(chart.ask) - float(chart.bid)
                price_offset_ask = price_gap * 0.20 if price_gap > 0.05 else 0.01
                price_offset_ask = round(price_offset_ask, 2)
                price_offset = price_gap * 0.30 if price_gap > 0.05 else 0.01
                price_offset = round(price_offset, 2)

                child_price = round(float(chart.bid) + price_offset, 2)  # For scalping shorts, set child price above ask to ensure it doesn't execute immediately
                price = round(float(chart.ask) - price_offset_ask, 2)  # For scalping shorts, price slightly below bid to increase fill probability
            else:
                child_price = float(chart.bid)
                price = float(chart.ask)

            # Enforce minimum 1-cent spread to avoid wash trades
            if child_price >= price:
                child_price = round(price - 0.01, 2)
                print(f"DEBUG: Adjusted child_price for {chart.symbol} to avoid wash trade: {child_price}")
                self.events.add_event(event_type="price_adjustment", symbol=chart.symbol)
        
        order_payload = self.replace_order_payload(price, chart.position.quantity, chart.symbol, instruction=chart.order_closing.instruction)
        return order_payload

    def replace_order_payload(self, price, quantity, symbol, instruction="BUY", orderType="LIMIT"):

        # Determine session based on current time
        session = utils.get_trading_session()

        order = {
            "orderType": orderType,
            "session": session,
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "price": price,
            "orderLegCollection": [
            {
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {
                    "symbol": symbol,
                    "assetType": "EQUITY"
                }
            }
            ]
        }
        if orderType == "MARKET":
            del order["price"]  # Remove price for market orders

        return order

    def place_closing_order(self):
        orders = []
        order = {}
        account_hash = self.schwab_client.check_account_hash()

        ### Sort for highest closing percentage.
        sorted_charts = sorted(
            self.schwab_client.stream.chart_list,
            key=lambda chart: chart.stats.closing_order_filled_percent,
            reverse=True  # Highest percentage first, remove for lowest first
        )

        for chart in sorted_charts:
            
            # Reset stale "Pending Verification" locks that never transitioned into an actual working order
            if chart.order_closing.bot_status == 'Pending Verification' and chart.order_closing.status not in ['AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION', 'REPLACED'] and (time.time() - chart.last_closing_order_time) > 30:
                print(f"DEBUG: Closing Stale Lock Reset for {chart.symbol}")
                chart.order_closing.bot_status = 'Ready'
                chart.pending_close = False
                
            # Prevent API rejection spamming loops
            # Impose a strict 60-second penalty on REJECTED orders
            spam_guard = 0
            if chart.order_closing.status == 'REJECTED':
                spam_guard = 60
            if (time.time() - chart.last_closing_order_time) < spam_guard:
                continue
                
            # Independent tracking per chart: only place closing order if chart has an open position
            # and there is no active closing order trying to close it!
            has_position = chart.has_position
            target_qty = chart.position.quantity if chart.position else 0
            
            if has_position and target_qty > 0 and chart.order_closing.bot_status in ['Ready', 'Unknown', 'Rejected'] and chart.order_closing.status != 'FILLED':
                # Prevent panicking on STALE canceled/rejected closing orders from past trades
                if getattr(chart.order_opening, 'entered_time', None) and getattr(chart.order_closing, 'entered_time', None):
                    if str(chart.order_closing.entered_time) < str(chart.order_opening.entered_time):
                        continue  # Wait for the API to return the current trade's closing order
                        
                # Check that we DO NOT ALREADY HAVE an active working closing order hiding in the parent trigger
                if chart.order_closing.status in ['WORKING', 'AWAITING_PARENT_ORDER', 'QUEUED']:
                    continue
                
                if chart.position:
                    instruction = 'BUY_TO_COVER' if chart.position.side == 'SHORT' else 'SELL'
                else:                    
                    instruction = 'BUY_TO_COVER' if chart.order_opening.side == 'SELL_SHORT' else 'SELL'
                     
                order_payload = self.place_closing_order_payload(chart, instruction=instruction, qty=target_qty)
                orders.append((chart, order_payload))
                time_stamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000')
                chart.order_closing = Order("", chart.symbol, 0, entered_time=time_stamp, order_timeout=self.schwab_client.closing_timeout, stuck_timeout_mult=self.schwab_client.stuck_timeout_mult)
                chart.order_closing.bot_status = 'Pending Verification' # Instantly prevent spamming
                chart.pending_close = True
                chart.last_closing_order_time = time.time()
                
            ### Check for partial fills that still need closing....
            elif chart.position and chart.quantity > chart.position.quantity and chart.order_closing.bot_status in ['Ready', 'Unknown', 'Rejected'] and chart.order_closing.status != 'FILLED':
                
                # Prevent acting on STALE canceled/rejected closing orders from past trades
                if getattr(chart.order_opening, 'entered_time', None) and getattr(chart.order_closing, 'entered_time', None):
                    if str(chart.order_closing.entered_time) < str(chart.order_opening.entered_time):
                        continue
                        
                if chart.order_closing.status in ['WORKING', 'AWAITING_PARENT_ORDER', 'QUEUED']:
                    continue
                    
                if chart.position.side == 'SHORT':
                    instruction = 'BUY_TO_COVER'
                else:                    
                    instruction = 'SELL' 
                order_payload = self.place_closing_order_payload(chart, instruction=instruction)
                orders.append((chart, order_payload))
                time_stamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000')
                chart.order_closing = Order("", chart.symbol, 0, entered_time=time_stamp, order_timeout=self.schwab_client.closing_timeout, stuck_timeout_mult=self.schwab_client.stuck_timeout_mult)
                chart.order_closing.bot_status = 'Pending Verification' # Instantly prevent spamming
                chart.pending_close = True
                chart.last_closing_order_time = time.time()
                
            elif chart.position and chart.order_closing.status == 'FILLED':
                # Schwab API position lags behind order status. Do nothing, wait for position to clear.
                pass

        ### Place Orders in parallel using threads for each individual symbol....
        if orders:
            with ThreadPoolExecutor(max_workers=min(len(orders), 5)) as executor:
                # Submit all independent closing orders simultaneously
                future_to_order = {executor.submit(self.schwab_client.order_place, account_hash, ord_payload): chart for chart, ord_payload in orders}
                
                errors = []
                # Process results as they complete
                for future in as_completed(future_to_order):
                    chart = future_to_order[future]
                    try:
                        order_result = future.result()
                    except Exception as e:
                        order_result = {'status': 'error', 'message': f"Unexpected error during closing order placement: {str(e)}"}
                        
                    if order_result.get('status') == 'ok':
                        order_id = order_result.get('order_id')
                        if order_id:
                            chart.order_closing.order_id = order_id
                            self.events.add_event(event_type="closing_order_id_captured", symbol=chart.symbol)
                    else:
                        chart.order_closing.bot_status = 'Ready' # Revert on error or warning
                        chart.pending_close = False
                        errors.append(order_result)
                
                if errors:
                    return errors[0]
                return {'status': 'ok', 'message': 'Closing orders placed successfully'}
        
        return {'status': 'ok', 'message': 'No closing orders placed'}
    
    def place_closing_order_payload(self, chart, instruction, qty=None):

        is_scalp = 'scalp' in chart.position.algo_type if chart.position and chart.position.algo_type else False

        print(f"DEBUG: Preparing closing order payload for {chart.symbol} with instruction {instruction} and qty {qty}. Scalp condition: {is_scalp}")

        if instruction == 'BUY_TO_COVER':
            if is_scalp:
                price_gap = float(chart.ask) - float(chart.bid)
                price_offset_bid = price_gap * 0.10 if price_gap > 0.05 else 0.01
                price_offset_bid = round(price_offset_bid, 2)
                price = round(float(chart.bid) + price_offset_bid, 2)  # For scalping longs, price slightly above ask to increase fill probability
            else:
                price = chart.bid
        else:
            if is_scalp:
                price_gap = float(chart.ask) - float(chart.bid)
                price_offset_ask = price_gap * 0.10 if price_gap > 0.05 else 0.01
                price_offset_ask = round(price_offset_ask, 2)
                price = round(float(chart.ask) - price_offset_ask, 2)  # For scalping shorts, price slightly below bid to increase fill probability
            else:         
                price = chart.ask

        # Smart fallback to opening filled quantity if API position endpoint lags
        use_qty = qty if qty else (chart.position.quantity if getattr(chart, 'position', None) else chart.order_opening.filled_qty)
        
        order_payload = self.limit_closing_order_payload(
            symbol=chart.symbol,
            quantity=use_qty,
            instruction=instruction,
            price=price,
        )
        
        # If we failed to exit the position enough times, bail with a MARKET order.
        if chart.exit_position_count > self.exit_position_threshold:
            order_payload['orderType'] = 'MARKET'
            if 'price' in order_payload:
                del order_payload['price']
            self.market_exit = True
            print(f"DEBUG: Escaping to MARKET order for {chart.symbol} after {chart.exit_position_count} failed exits.")
            
        return order_payload
    
    def limit_closing_order_payload(self, price, quantity, symbol, instruction="BUY", duration="DAY"): ###FILL_OR_KILL

        # Determine session based on current time
        session = utils.get_trading_session()

        # Calculate cancel time
        cancel_time = self._get_cancel_time(self.schwab_client.closing_timeout)

        order = {
            "orderType": "LIMIT",
            "session": session,
            "duration": duration,
            #"cancelTime": cancel_time,
            "orderStrategyType": "SINGLE",
            "price": price,
            "orderLegCollection": [
            {
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {
                    "symbol": symbol,
                    "assetType": "EQUITY"
                }
            }
            ]
        }
        return order

    
    def calculate_status(self):
        ### Check to see were we are at...
        self.opening_status = 'closed' 
        self.closing_status = 'closed'

        #### Check Opeing Orders......
        for cht in self.schwab_client.stream.chart_list:
            if cht.order_opening.bot_status == 'Cancel':
                self.opening_status = 'Cancel'
                break
            elif cht.order_opening.bot_status == 'Timeout' or cht.order_opening.bot_status == 'Shift':
                self.opening_status = 'Timeout'
            elif cht.order_opening.bot_status == 'Countdown' and not self.opening_status in ('Cancel', 'Timeout'):
                self.opening_status = 'Countdown'
            elif cht.order_opening.bot_status == 'Pending Verification' and not self.opening_status in ('Cancel', 'Timeout', 'Countdown'):
                self.opening_status = 'Pending Verification'
            elif cht.order_opening.bot_status == 'Ready' and not self.opening_status in ('Cancel', 'Timeout', 'Countdown', 'Pending Verification'):
                self.opening_status = 'Ready'
        #print(f"Opening Status: {self.opening_status}")

        #### Check Closing Orders....
        for cht in self.schwab_client.stream.chart_list:
            
            # SANITY CHECK: If chart holds no position, and the opening order is completely dead/done, 
            # there is mathematically zero reason for the closing order to be Pending Verification. Reset it.
            if not cht.has_position and cht.order_opening.bot_status in ['Ready', 'Canceled', 'Rejected', 'Unknown']:
                if cht.order_closing.bot_status == 'Pending Verification':
                    # Allow 5 additional seconds to ensure the API wasn't catching up
                    import time
                    if (time.time() - getattr(cht, 'last_closing_order_time', 0)) > 5:
                        if cht.order_closing.status not in ['AWAITING_PARENT_ORDER', 'QUEUED', 'PENDING_ACTIVATION', 'REPLACED']:
                            cht.order_closing.bot_status = 'Ready'
                        
            if cht.order_closing.bot_status == 'Cancel':
                self.closing_status = 'Cancel'
                break
            elif cht.order_closing.bot_status == 'Timeout' or cht.order_closing.bot_status == 'Shift':
                self.closing_status = 'Timeout'
            elif cht.order_closing.bot_status == 'Countdown' and not self.closing_status in ('Cancel', 'Timeout'):
                self.closing_status = 'Countdown'
            elif cht.order_closing.bot_status == 'Pending Verification' and not self.closing_status in ('Cancel', 'Timeout', 'Countdown'):
                self.closing_status = 'Pending Verification'
            elif cht.order_closing.bot_status == 'Ready' and not self.closing_status in ('Cancel', 'Timeout', 'Countdown', 'Pending Verification'):
                self.closing_status = 'Ready'
        #print(f"Closing Status: {self.closing_status}")

        #### Opensing Sequence....
        if self.opening_status == "Ready" and self.closing_status == "Ready" and self.position_status == "closed":
            self.phase = 'Opening'
            self.status = 'Ready'
            self.sub_status = 'Place Order'
            self.message = 'No open positions or orders'
        elif self.opening_status == 'Pending Verification':
            self.phase = 'Opening'
            self.status = 'Pending Verification'
            self.sub_status = ''
            self.message = 'Waiting on Schwab ID Verification'
        elif self.opening_status == 'Countdown':
            self.phase = 'Opening'
            self.status = 'Countdown'
            self.sub_status = ''
            self.message = 'Countdown in progress'
        elif self.opening_status == 'Timeout':
            self.phase = 'Opening'
            self.status = 'Timeout'
            self.sub_status = 'Cancel Order'
            self.message = 'Order timed out, canceling'

        #### Closing Sequence......
        elif self.opening_status == "Ready" and self.closing_status == 'Pending Verification':
            self.phase = 'Closing'
            self.status = 'Pending Verification'
            self.sub_status = ''
            self.message = 'Waiting on Schwab ID Verification'
        elif self.opening_status == 'Ready' and self.closing_status == 'Countdown':
            self.phase = 'Closing'
            self.status = 'Countdown'
            self.sub_status = ''
            self.message = 'Countdown in progress'
        elif self.opening_status == 'Ready' and self.closing_status == 'Timeout':
            self.phase = 'Closing'
            self.status = 'Timeout'
            self.sub_status = 'Cancel Order'
            self.message = 'Order timed out, canceling'
        elif self.opening_status == 'Ready' and self.closing_status == 'Ready' and self.position_status == "open":
            self.phase = 'Closing'
            self.status = 'Ready'
            self.sub_status = 'Place Order'
            self.message = 'Open positions'

    def _get_cancel_time(self, milliseconds=20000):
        """Get cancel time in ISO 8601 format based on milliseconds from now"""
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        cancel_time = now + timedelta(milliseconds=milliseconds)
        
        # Returns format like: "2025-12-22T10:30:00.020000-05:00"
        return cancel_time.isoformat()
    
    def _calculate_rank(self):
        ### Calculate rank based on weighted chart stats....
        weights = {
            'opening_order_filled_percent_rolling': 0.10,
            'opening_order_filled_percent': 0.40,
            'closing_order_filled_percent_rolling': 0.10,
            'closing_order_filled_percent': 0.40
        }
        # Calculate weighted score for each chart
        def calculate_score(chart):
            # Use 0 as default if value is None
            if chart.stats.opening_order_count_rolling == 0:
                opening_rolling = chart.stats.opening_order_filled_percent_rolling or 100
            else:
                opening_rolling = chart.stats.opening_order_filled_percent_rolling or 0

            opening = chart.stats.opening_order_filled_percent or 0
            
            if chart.stats.closing_order_count_rolling == 0:
                closing_rolling = chart.stats.closing_order_filled_percent_rolling or 100
            else:
                closing_rolling = chart.stats.closing_order_filled_percent_rolling or 0
            
            closing = chart.stats.closing_order_filled_percent or 0
            
            score = (
                opening_rolling * weights['opening_order_filled_percent_rolling'] +
                opening * weights['opening_order_filled_percent'] +
                closing_rolling * weights['closing_order_filled_percent_rolling'] +
                closing * weights['closing_order_filled_percent']
            )
            return score
        
        ranked_charts = sorted(
            self.schwab_client.stream.chart_list,
            key=calculate_score,
            reverse=True  # Highest weighted score first
        )

        for rank, chart in enumerate(ranked_charts, start=1):
            chart.rank = rank

