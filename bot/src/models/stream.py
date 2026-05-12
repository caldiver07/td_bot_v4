from typing import TYPE_CHECKING

from flask import json
from .chart import Chart
from datetime import datetime

if TYPE_CHECKING:
    from src.models.events import Event
    
class Stream():
    def __init__(self, events:'Event' = None, redis_client=None):
        self.redis_client = redis_client

        ### Charts.....................
        self.chart_1 = Chart(redis_client=self.redis_client)
        self.chart_2 = Chart(redis_client=self.redis_client)
        self.chart_3 = Chart(redis_client=self.redis_client)
        self.chart_4 = Chart(redis_client=self.redis_client)
        self.chart_5 = Chart(redis_client=self.redis_client)
        self.chart_6 = Chart(redis_client=self.redis_client)
        self.chart_7 = Chart(redis_client=self.redis_client)
        self.chart_8 = Chart(redis_client=self.redis_client)
        self.chart_9 = Chart(redis_client=self.redis_client)
        self.chart_10 = Chart(redis_client=self.redis_client)
        self.chart_11 = Chart(redis_client=self.redis_client)
        self.chart_12 = Chart(redis_client=self.redis_client)
        self.chart_13 = Chart(redis_client=self.redis_client)
        self.chart_14 = Chart(redis_client=self.redis_client)
        self.chart_15 = Chart(redis_client=self.redis_client)
        self.chart_16 = Chart(redis_client=self.redis_client)
        self.chart_17 = Chart(redis_client=self.redis_client)
        self.chart_18 = Chart(redis_client=self.redis_client)
        self.chart_19 = Chart(redis_client=self.redis_client)
        self.chart_20 = Chart(redis_client=self.redis_client)
        self.chart_21 = Chart(redis_client=self.redis_client)
        self.chart_22 = Chart(redis_client=self.redis_client)
        self.chart_23 = Chart(redis_client=self.redis_client)
        self.chart_24 = Chart(redis_client=self.redis_client)
        self.chart_25 = Chart(redis_client=self.redis_client)
        self.chart_26 = Chart(redis_client=self.redis_client)
        self.chart_27 = Chart(redis_client=self.redis_client)
        self.chart_28 = Chart(redis_client=self.redis_client)
        self.chart_29 = Chart(redis_client=self.redis_client)
        self.chart_30 = Chart(redis_client=self.redis_client)
        self.chart_31 = Chart(redis_client=self.redis_client)
        self.chart_32 = Chart(redis_client=self.redis_client)
        self.chart_33 = Chart(redis_client=self.redis_client)
        self.chart_34 = Chart(redis_client=self.redis_client)
        self.chart_35 = Chart(redis_client=self.redis_client)
        self.chart_36 = Chart(redis_client=self.redis_client)
        self.chart_37 = Chart(redis_client=self.redis_client)
        self.chart_38 = Chart(redis_client=self.redis_client)
        self.chart_39 = Chart(redis_client=self.redis_client)
        self.chart_40 = Chart(redis_client=self.redis_client)
        self.chart_41 = Chart(redis_client=self.redis_client)
        self.chart_42 = Chart(redis_client=self.redis_client)
        self.chart_43 = Chart(redis_client=self.redis_client)
        self.chart_44 = Chart(redis_client=self.redis_client)
        self.chart_45 = Chart(redis_client=self.redis_client)
        self.chart_46 = Chart(redis_client=self.redis_client)
        self.chart_47 = Chart(redis_client=self.redis_client)
        self.chart_48 = Chart(redis_client=self.redis_client)
        self.chart_49 = Chart(redis_client=self.redis_client)
        self.chart_50 = Chart(redis_client=self.redis_client)
        
        self.chart_list = [self.chart_1, self.chart_2, self.chart_3, self.chart_4, self.chart_5, self.chart_6, self.chart_7, self.chart_8, self.chart_9, self.chart_10, self.chart_11, self.chart_12, self.chart_13, self.chart_14, self.chart_15, self.chart_16, self.chart_17, self.chart_18, self.chart_19, self.chart_20, self.chart_21, self.chart_22, self.chart_23, self.chart_24, self.chart_25, self.chart_26, self.chart_27, self.chart_28, self.chart_29, self.chart_30, self.chart_31, self.chart_32, self.chart_33, self.chart_34, self.chart_35, self.chart_36, self.chart_37, self.chart_38, self.chart_39, self.chart_40, self.chart_41, self.chart_42, self.chart_43, self.chart_44, self.chart_45, self.chart_46, self.chart_47, self.chart_48, self.chart_49, self.chart_50]

        ### Thresholds and parameters.........
        self.pause_threshold = 8                
        self.pause_threshold_2 = 12
        self.current_change_threshold = 1

        self.opening_fill_threshold = 55
        self.closing_fill_threshold = 55
        self.opening_order_threshold = 10

        self.paused_charts_timeout = 5

        #### Stat........
        self.paused_charts = 0

        self.last_day = None

        ### Event Data...
        if events:
            self.events = events

    def _init_vars(self):
        self.__init__(redis_client=self.redis_client)
        
    def set_chart_symbols(self, charts):
        
        for cnt, chart in enumerate(self.chart_list):
            chart.symbol = chart.stats.symbol = charts[cnt]

    def set_chart_data(self):
        for chart in self.chart_list:
            chart_data = self.redis_client.get(chart.symbol)
            chart_data = json.loads(chart_data) if chart_data else None
            if chart_data:
                chart.load_from_dict(chart_data)
                self.calculate_chart_change(chart)
                chart.stats.update_date_durations(chart)

        self.calclate_paused_charts()

    def calculate_chart_change(self, chart:Chart):
        def determine_will_pause(percent, target_percent, count, target_count):
            rtn = False
            cnt_remaining = target_count - count
            cnt_mid = target_count // 2
            pct_remaining = target_percent - percent
            
            # Determine if the remaining count where to all fill would we meet the target percent, if not return true
            if count > 1 and cnt_remaining > 0:
                # Calculate what the percent would be if all remaining orders filled
                projected_percent = ((percent/100) * count + cnt_remaining) / target_count
                if projected_percent < (target_percent/100):
                    return True
            
            # If we've met the count threshold but not the percent threshold, pause
            if percent < target_percent and count >= target_count:
                return True
            
            return rtn
        
        change_count = 0
        previous_bid = None
        # for bid in chart.bids_list:
        #     if isinstance(bid, (int, float)):
        #         if previous_bid is not None and bid != previous_bid:
        #             change_count += 1
        #         previous_bid = bid
        # chart.stats.chart_change = change_count

        # if chart.trade_order == False or (change_count <= self.pause_threshold) or (change_count <= self.pause_threshold_2 and chart.stats.current_change <= self.current_change_threshold):
        #     chart.pause_orders = False
        #     chart.paused_reason = ""
        # else:
        #     chart.pause_orders = True
        #     chart.paused_reason = "volatility"

        ### pause if filled percent is low
        ##if(chart.stats.opening_order_filled_percent_rolling < self.opening_fill_threshold and chart.stats.opening_order_count_rolling >= self.opening_order_threshold):
        if determine_will_pause(chart.stats.opening_order_filled_percent_rolling, self.opening_fill_threshold, chart.stats.opening_order_count_rolling, self.opening_order_threshold):
            chart.pause_orders = True
            chart.paused_reason = "opening"
            if chart.stats.paused > self.paused_charts_timeout:
                chart.stats.reset_stats()
        
        ### pause if canceled percent is high
        if(chart.stats.closing_order_filled_percent_rolling < self.closing_fill_threshold and chart.stats.closing_order_count_rolling >= self.opening_order_threshold):
        ##if determine_will_pause(chart.stats.closing_order_filled_percent_rolling, self.closing_fill_threshold, chart.stats.closing_order_count_rolling, self.opening_order_threshold):
            chart.pause_orders = True
            chart.paused_reason = "closing"
            if chart.stats.paused > self.paused_charts_timeout:
                chart.stats.reset_stats()

        # if chart.trade_order:
        #     chart.pause_orders = False
        #     chart.paused_reason = ""

        ### Rest all chart data if day change. this gives us clean charts and stats for the new day.
        current_day = datetime.utcnow().day
        if self.last_day and self.last_day != current_day:
            self.last_day = current_day
            chart.stats.reset_all_stats()
        else:
            self.last_day = current_day

    def calclate_paused_charts(self):
        paused_count = 0
        for chart in self.chart_list:
            if chart.trade_order == True and chart.pause_orders:
                paused_count += 1
        self.paused_charts = paused_count


    def to_dict(self):
        rtn = {
            'chart_1': self.chart_1.to_dict(),
            'chart_2': self.chart_2.to_dict(),
            'chart_3': self.chart_3.to_dict(),
            'chart_4': self.chart_4.to_dict(),
            'chart_5': self.chart_5.to_dict(),
            'chart_6': self.chart_6.to_dict(),
            'chart_7': self.chart_7.to_dict(),
            'chart_8': self.chart_8.to_dict(),
            'chart_9': self.chart_9.to_dict(),
            'chart_10': self.chart_10.to_dict(),
            'chart_11': self.chart_11.to_dict(),
            'chart_12': self.chart_12.to_dict(),
            'chart_13': self.chart_13.to_dict(),
            'chart_14': self.chart_14.to_dict(),
            'chart_15': self.chart_15.to_dict(),
            'chart_16': self.chart_16.to_dict(),
            'chart_17': self.chart_17.to_dict(),
            'chart_18': self.chart_18.to_dict(),
            'chart_19': self.chart_19.to_dict(),
            'chart_20': self.chart_20.to_dict(),
            'chart_21': self.chart_21.to_dict(),
            'chart_22': self.chart_22.to_dict(),
            'chart_23': self.chart_23.to_dict(),
            'chart_24': self.chart_24.to_dict(),
            'chart_25': self.chart_25.to_dict(),
            'chart_26': self.chart_26.to_dict(),
            'chart_27': self.chart_27.to_dict(),
            'chart_28': self.chart_28.to_dict(),
            'chart_29': self.chart_29.to_dict(),
            'chart_30': self.chart_30.to_dict(),
            'chart_31': self.chart_31.to_dict(),
            'chart_32': self.chart_32.to_dict(),
            'chart_33': self.chart_33.to_dict(),
            'chart_34': self.chart_34.to_dict(),
            'chart_35': self.chart_35.to_dict(),
            'chart_36': self.chart_36.to_dict(),
            'chart_37': self.chart_37.to_dict(),
            'chart_38': self.chart_38.to_dict(),
            'chart_39': self.chart_39.to_dict(),
            'chart_40': self.chart_40.to_dict(),
            'chart_41': self.chart_41.to_dict(),
            'chart_42': self.chart_42.to_dict(),
            'chart_43': self.chart_43.to_dict(),
            'chart_44': self.chart_44.to_dict(),
            'chart_45': self.chart_45.to_dict(),
            'chart_46': self.chart_46.to_dict(),
            'chart_47': self.chart_47.to_dict(),
            'chart_48': self.chart_48.to_dict(),
            'chart_49': self.chart_49.to_dict(),
            'chart_50': self.chart_50.to_dict(),
        }
        ### Order output by chart.rank
        # Sort charts by rank
        chart_items = sorted(rtn.items(), key=lambda item: getattr(self, item[0]).rank if hasattr(self, item[0]) else float('inf'))
        
        # Add non-chart items at the end
        sorted_rtn = dict(chart_items)
        sorted_rtn['paused_charts'] = self.paused_charts
        sorted_rtn['order_count'] = self.events.order_api_count if self.events else 0
        
        return sorted_rtn
    
    def reset_chart_update_flags(self):
        for chart in self.chart_list:
            chart.update_order_opening_flag = False
            chart.update_order_closing_flag = False