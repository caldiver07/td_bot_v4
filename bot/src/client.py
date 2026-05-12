"""
This file contains functions to create a client class that accesses the Schwab api
Coded by Tyler Bowers
Github: https://github.com/tylerebowers/Schwab-API-Python
"""
from flask import current_app

import time
import logging
import datetime
import requests
import threading
import pytz
import urllib.parse
from time import sleep
from datetime import datetime, timedelta
from .models.stream import Stream
from .token import Tokens
from .models.account import Account
from .models.order import Order, Orders
from .models.position import Position, Positions
from .common import utils

class Client:

    def __init__(self, app_key, app_secret, callback_url="https://127.0.0.1", tokens_file="", timeout=30, capture_callback=True, use_session=True, call_on_notify=None, events=None, redis_client=None):
        """
        Initialize a client to access the Schwab API.
        Args:
            app_key (str): App key credential.
            app_secret (str): App secret credential.
            callback_url (str): URL for callback.
            tokens_file (str): Path to tokens file.
            timeout (int): Request timeout in seconds - how long to wait for a response.
            capture_callback (bool): Use a webserver with self-signed cert to capture callback with code (no copy/pasting urls during auth).
            use_session (bool): Use a requests session for requests instead of creating a new session for each request.
            call_on_notify (function | None): Function to call when user needs to be notified (e.g. for input)
        """
        logging.getLogger('elastic_transport').setLevel(logging.CRITICAL)
        logging.getLogger('elasticsearch').setLevel(logging.CRITICAL)
        
        self.version = "Schwabdev 2.5.0"                                    # version of the client
        self._base_api_url = "https://api.schwabapi.com"                   # base url for the api
        self.timeout = timeout                                              # timeout to use in requests
        self.logger = logging.getLogger("Schwabdev")  # init the logger
        self._session = requests.Session() if use_session else requests  # session to use in requests
        self.tokens = Tokens(self, app_key, app_secret, callback_url, tokens_file, capture_callback, call_on_notify)
        self.stream = Stream(events, redis_client=redis_client)
        self.events = events
        self.redis_client = redis_client

        self.account_hash = None

        ##### Settings....
        self.auto_trading = False           # enable/disable auto trading
        self.charts_initialized = False    # flag to indicate if charts have been initialized
        self.order_timeout = 8000              # timeout for orders in milliseconds
        self.closing_timeout = 6000            # timeout for closing orders in milliseconds
        self.closing_order_multiplier = 2.0   # multiplier for closing orders
        self.group_order_multiplier = 1.5     # multiplier for group orders

        self.paused_charts_threshold = 50        # threshold for paused charts
        self.stuck_timeout_mult = 10              # multiplier for stuck timeout
        self.order_api_count_limit = 3700
        self.is_short = False
        
        # Spawns a thread to check the tokens and updates if necessary, also updates the session
        def checker():
            while True:
                try:
                    if self.tokens.update_tokens() and use_session:
                        self._session = requests.Session() #make a new session if the access token was updated
                    time.sleep(30)
                except requests.exceptions.ReadTimeout:
                    self.logger.warning("Token refresh timed out - will retry on next cycle")
                    time.sleep(30)  # Wait before retrying
                except requests.exceptions.ConnectionError:
                    self.logger.warning("Connection error during token refresh - will retry on next cycle")
                    time.sleep(30)
                except Exception as e:
                    self.logger.error(f"Error refreshing token: {e}")
                    time.sleep(30)

        # Check if TokenChecker is already running
        if not any(t.name == "TokenChecker" for t in threading.enumerate()):
            threading.Thread(target=checker, daemon=True, name="TokenChecker").start()

        self.logger.info("Client Initialization Complete")

    def account_linked(self) -> requests.Response:
        """
        Account numbers in plain text cannot be used outside of headers or request/response bodies.
        As the first step consumers must invoke this service to retrieve the list of plain text/encrypted value pairs, and use encrypted account values for all subsequent calls for any accountNumber request.

        Return:
            request.Response: All linked account numbers and hashes
        """
        res_data = self._session.get(f'{self._base_api_url}/trader/v1/accounts/accountNumbers', headers={'Authorization': f'Bearer {self.tokens.access_token}'}, timeout=self.timeout)
        #events.add_event(event_type="account_linked", platform=self.platform, write_to_es=self.write_to_es)
        return res_data

    def account_details_all(self, fields: str = None, timeout: int = None) -> requests.Response:
        """
        All the linked account information for the user logged in. The balances on these accounts are displayed by default however the positions on these accounts will be displayed based on the "positions" flag.

        Args:
            fields (str | None): fields to return (options: "positions")

        Returns:
            request.Response: details for all linked accounts
        """
        api_start_time = datetime.now()
        account_details = self._session.get(f'{self._base_api_url}/trader/v1/accounts/', headers={'Authorization': f'Bearer {self.tokens.access_token}'}, params=self._params_parser({'fields': fields}), timeout=timeout or self.timeout)
        api_response_time = (datetime.now() - api_start_time).total_seconds() * 1000  # Convert to milliseconds

        self.events.add_event(event_type=f"account_details", response_time=api_response_time)
        data = account_details.json()
        # if self.write_to_es:
        #     events.refresh_counters_from_es()
        day_change = data[0]['securitiesAccount']['currentBalances']['liquidationValue'] - data[0]['securitiesAccount']['initialBalances']['liquidationValue']
        acct = Account(account_id=data[0]['securitiesAccount']['accountNumber'], balance=data[0]['securitiesAccount']['currentBalances']['liquidationValue'], buying_power=data[0]['securitiesAccount']['currentBalances']['buyingPower'], currency='USD', day_change=day_change)
        acct_dict = acct.to_dict()
        # events.add_event(event_type="account_info", platform=self.platform, write_to_es=self.write_to_es)
        return acct_dict

    def _params_parser(self, params: dict):
        """
        Removes None (null) values

        Args:
            params (dict): params to remove None values from

        Returns:
            dict: params without None values

        Example:
            params = {'a': 1, 'b': None}
            client._params_parser(params)
            {'a': 1}
        """
        for key in list(params.keys()):
            if params[key] is None: del params[key]
        return params

    def _time_convert(self, dt = None, form="8601"):
        """
        Convert time to the correct format, passthrough if a string, preserve None if None for params parser

        Args:
            dt (datetime.datetime): datetime object to convert
            form (str): format to convert to (check source for options)

        Returns:
            str | None: converted time (or None passed through)
        """
        if dt is None or not isinstance(dt, datetime):
            return dt
        elif form == "8601":  # assume datetime object from here on
            return f"{dt.isoformat().split('+')[0][:-3]}Z"
        elif form == "epoch":
            return int(dt.timestamp())
        elif form == "epoch_ms":
            return int(dt.timestamp() * 1000)
        elif form == "YYYY-MM-DD":
            return dt.strftime("%Y-%m-%d")
        else:
            return dt

    def _format_list(self, l: list | str | None):
        """
        Convert python list to string or passthough if a string or None

        Args:
            l (list | str | None): list to convert

        Returns:
            str | None: converted string or passthrough

        Example:
            l = ["a", "b"]
            client._format_list(l)
            "a,b"
        """
        if l is None:
            return None
        elif isinstance(l, list):
            return ",".join(l)
        else:
            return l
        
    def account_orders(self, accountHash: str,  maxResults: int = None, status: str = None, range_minutes: int = 30) -> requests.Response:
        """
        All orders for a specific account. Orders retrieved can be filtered based on input parameters below. Maximum date range is 1 year.

        Args:
            accountHash (str): account hash from account_linked()
            fromEnteredTime (datetime.datetime | str): start date
            toEnteredTime (datetime.datetime | str): end date
            maxResults (int | None): maximum number of results (set to None for default 3000)
            status (str | None): status of order

        Returns:
            request.Response: orders for one linked account
        """
        orders_dict = {}
        orders = Orders()
        rtn = {}
        orders_data = {}

        ### from date is yesterday to today
        to_date = datetime.utcnow()
        fromm_date = to_date - timedelta(minutes=range_minutes)
        fromm_date = fromm_date.strftime('%Y-%m-%dT%H:%M:00.000Z')
        to_date = datetime.utcnow().strftime('%Y-%m-%dT23:59:59.000Z')

        api_start_time = datetime.now()
        orders_res =  self._session.get(f'{self._base_api_url}/trader/v1/orders',
                            headers={"Accept": "application/json", 'Authorization': f'Bearer {self.tokens.access_token}'},
                            params=self._params_parser({'maxResults': maxResults,'fromEnteredTime': self._time_convert(fromm_date, "8601"), 'toEnteredTime': self._time_convert(to_date, "8601"), 'status': status}),
                            timeout=self.timeout)
        
        api_response_time = (datetime.now() - api_start_time).total_seconds() * 1000  # Convert to milliseconds

        if orders_res.status_code == 200:
            orders_data = orders_res.json()

        self.events.add_event(event_type=f"account_orders", response_time=api_response_time)
        return orders_data
    
    def account_positions(self, fields: str = None) -> requests.Response:
        """
        All the linked account information for the user logged in. The balances on these accounts are displayed by default however the positions on these accounts will be displayed based on the "positions" flag.

        Args:
            fields (str | None): fields to return (options: "positions")

        Returns:
            request.Response: details for all linked accounts
        """
        rtn = {}
        positions = Positions()

        api_start_time = datetime.now()
        account_details = self._session.get(f'{self._base_api_url}/trader/v1/accounts/', headers={'Authorization': f'Bearer {self.tokens.access_token}'}, params=self._params_parser({'fields': fields}), timeout=self.timeout)
        api_response_time = (datetime.now() - api_start_time).total_seconds() * 1000  # Convert to milliseconds
        
        ### if it fails try again once
        if account_details.status_code != 200:
            api_start_time = datetime.now()
            account_details = self._session.get(f'{self._base_api_url}/trader/v1/accounts/', headers={'Authorization': f'Bearer {self.tokens.access_token}'}, params=self._params_parser({'fields': fields}), timeout=self.timeout)
            api_response_time = (datetime.now() - api_start_time).total_seconds() * 1000  # Convert to milliseconds

        self.events.add_event(event_type=f"account_positions", response_time=api_response_time)

        data = account_details.json()
        if not data or 'securitiesAccount' not in data[0]:
            return {"positions": {}, "stream": {}, "account": {}}

        ### get account info
        day_change = data[0]['securitiesAccount']['currentBalances']['liquidationValue'] - data[0]['securitiesAccount']['initialBalances']['liquidationValue']
        acct = Account(account_id=data[0]['securitiesAccount']['accountNumber'], balance=data[0]['securitiesAccount']['currentBalances']['liquidationValue'], buying_power=data[0]['securitiesAccount']['currentBalances']['buyingPower'], currency='USD', day_change=day_change)
        acct_dict = acct.to_dict()

        ##### get positions
        securitiesAccount = data[0]['securitiesAccount']    
        positions_data = securitiesAccount.get('positions', [])
        ### clear postions in charts
        for chart in self.stream.chart_list:
            chart.has_position = False

        if positions_data:
            for pos in positions_data:
                if pos['instrument']['assetType'] != 'EQUITY':
                    continue
                quantity = 0
                side = ''
                if pos.get('longQuantity', 0) > 0:
                    side = 'LONG'
                    quantity = pos.get('longQuantity', 0)
                elif pos.get('shortQuantity', 0) > 0:
                    side = 'SHORT'
                    quantity = pos.get('shortQuantity', 0)
                else:
                    # Quantity is 0 (closed position still listed for P&L), skip it!
                    continue
                
                position = Position(
                    symbol=pos.get('instrument', {}).get('symbol', 'N/A'),
                    quantity=quantity,
                    side=side,
                    market_value=pos.get('marketValue', 0.0),
                    current_price=pos.get('currentPrice', 0.0),
                    change_today=pos.get('changeToday', 0.0)
                )

                for chart in self.stream.chart_list:
                    if chart.symbol == position.symbol:
                        chart.position = position
                        chart.has_position = True
                        break

                positions.add_position(position)

        ### Now clear positions for charts that no longer have a matching position
        for chart in self.stream.chart_list:
            if chart.has_position == False:
                chart.position = None

        position_dict = positions.to_dict()
        stream_dict = self.stream.to_dict()

        rtn = {"positions": position_dict, "stream": stream_dict, "account": acct_dict}
        
        return rtn
    
    def check_account_hash(self):
        if self.account_hash:
            account_hash = self.account_hash
        else:
            linked_account = self.account_linked()
            data = linked_account.json()
            account_hash = data[0]['hashValue']
            self.account_hash = account_hash
        return self.account_hash
        
    def order_cancel(self, accountHash: str, orderId: int | str) -> requests.Response:
        """
        Cancel a specific order by its ID, for a specific account
        """
        rtn = {
            'status': 'ok',  ### ok,error
            'message': ''
        }

        resp_data = self._session.delete(f'{self._base_api_url}/trader/v1/accounts/{accountHash}/orders/{orderId}', headers={'Authorization': f'Bearer {self.tokens.access_token}'}, timeout=self.timeout)
        #### ADD EVENT FOR ALL CALLS REGUARDLESS OF SUCCESS.....
        self.events.add_event(event_type=f"order_api_limit_cnt")

        if resp_data.status_code in (200, 201):
            rtn['status'] = 'ok'
            rtn['message'] = 'Order placed successfully'
        else:
            rtn['status'] = 'error'
            rtn['message'] = f'Failed to cancel order: HTTP {resp_data.status_code}'
            self.events.add_event(event_type=f"cancel_order_failed")

        return rtn
    
    def order_place(self, accountHash: str, order: dict) -> requests.Response:
        """
        Place an order for a specific account.

        Args:
            accountHash (str): account hash from account_linked()
            order (dict): order dictionary (format examples in github documentation)

        Returns:
            request.Response: order number in response header (if immediately filled then order number not returned)
        """
        rtn = {
            'status': 'ok',  ### ok,error
            'message': ''
        }

        ### Check the market status
        market_status = utils.get_market_status()
        order_instruction = order['orderLegCollection'][0]['instruction']

        if self.auto_trading == False and order_instruction in ["BUY", "SELL_SHORT"]:
            rtn['message'] = "Auto trading is disabled"
            rtn['status'] = 'warning'
            sleep(1)
            return rtn
        
        ## If the market has closed do not open any new buy orders......
        if market_status == "CLOSED" and order_instruction in ["BUY", "SELL_SHORT"]:
            rtn['message'] = "MARKET_CLOSED"
            rtn['status'] = 'warning'
            sleep(60)
            return rtn
        
        ###### If at limit do not place any more orders... But just for buy orders... let system finish open positions...
        if self.events.order_api_count > self.order_api_count_limit and order_instruction in ["BUY", "SELL_SHORT"]:
            rtn['message'] = "ORDER_LIMIT_REACHED"
            rtn['status'] = 'warning'
            sleep(5)
            return rtn
        
        #### IF paused charts are greater then threshold....
        if self.stream.paused_charts >= self.paused_charts_threshold and order_instruction in ["BUY", "SELL_SHORT"]:
            rtn['message'] = "PAUSED_CHARTS_THRESHOLD"
            rtn['status'] = 'warning'
            self.events.add_event(event_type=f"paused_charts")
            sleep(1)
            return rtn
        
        ### PLACE ORDER.....
        api_start_time = datetime.now()
        res_data = self._session.post(f'{self._base_api_url}/trader/v1/accounts/{accountHash}/orders',headers={"Accept": "application/json",'Authorization': f'Bearer {self.tokens.access_token}',"Content-Type":"application/json"},json=order,timeout=self.timeout)
        api_response_time = (datetime.now() - api_start_time).total_seconds() * 1000  # Convert to milliseconds
        #### ADD EVENT FOR ALL CALLS REGUARDLESS OF SUCCESS.....
        self.events.add_event(event_type=f"order_api_limit_cnt", response_time=api_response_time)

        ### if we are getting limited sleep and try again once...
        if res_data.status_code == 429:
            self.events.add_event(event_type="rate_limit")
            sleep(10)
            res_data = self._session.post(f'{self._base_api_url}/trader/v1/accounts/{accountHash}/orders',headers={"Accept": "application/json",'Authorization': f'Bearer {self.tokens.access_token}',"Content-Type":"application/json"},json=order,timeout=self.timeout)
            if res_data.status_code == 429:
                self.events.add_event(event_type="rate_limit_2x")

        if res_data.status_code in (200, 201):
            rtn['status'] = 'ok'
            rtn['message'] = 'Order placed successfully'
            location = res_data.headers.get('Location') or res_data.headers.get('location')
            if location:
                try:
                    rtn['order_id'] = location.split('/')[-1]
                except Exception:
                    pass
        else:
            rtn['status'] = 'error'
            rtn['message'] = 'Failed to place order'
            self.events.add_event(event_type=f"place_order_failed")

        return rtn
    
    def _load_history(self):
        """
        Load historical data for all charts
        """
        for chart in self.stream.chart_list:
            chart.stats.load_dict()