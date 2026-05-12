

import datetime

import pytz


def get_trading_session():
    """
    Determine the appropriate trading session based on Eastern Time

    Returns:
        str: "NORMAL", "AM", or "PM"
    """
    # Get current time in Eastern timezone (where US markets operate)
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.datetime.now(eastern)
    current_time = now_et.time()

    # Define market hours (Eastern Time)
    market_open = datetime.time(9, 30)  # 9:30 AM ET
    market_close = datetime.time(15, 59)  # 3:59 PM ET
    pre_market_start = datetime.time(4, 0)  # 4:00 AM ET
    after_market_end = datetime.time(20, 0)  # 8:00 PM ET

    # Check if it's a weekday (Monday=0, Sunday=6)
    if now_et.weekday() >= 5:  # Weekend
        return "NORMAL"  # Default to normal session

    if pre_market_start <= current_time < market_open:
        session = "AM"  # Pre-market
    elif market_open <= current_time < market_close:
        session = "NORMAL"  # Regular market hours
    elif market_close <= current_time < after_market_end:
        session = "PM"  # After-market
    else:
        session = "NORMAL"  # Outside trading hours, default to NORMAL

    ##self.logger.info(f"Trading session determined: {session} at {current_time} ET")
    return session

def get_market_status():
    """
    Determine the appropriate trading session based on Eastern Time

    Returns:
        str: "NORMAL", "AM", or "PM"
    """
    # Get current time in Eastern timezone (where US markets operate)
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.datetime.now(eastern)
    current_time = now_et.time()

    # Define market hours (Eastern Time)
    market_open = datetime.time(9, 30)  # 9:30 AM ET
    market_close = datetime.time(15, 55)  # 3:55 PM ET
    pre_market_start = datetime.time(4, 0)  # 4:00 AM ET
    after_market_end = datetime.time(20, 0)  # 8:00 PM ET

    # Check if it's a weekday (Monday=0, Sunday=6)
    if now_et.weekday() >= 5:  # Weekend
        return "CLOSED"  # Default to normal session

    if pre_market_start <= current_time < market_open:
        session = "CLOSED"  # Pre-market
    elif market_open <= current_time < market_close:
        session = "OPEN"  # Regular market hours
    elif market_close <= current_time < after_market_end:
        session = "CLOSED"  # After-market
    else:
        session = "CLOSED"  # Outside trading hours, default to CLOSED

    ##self.logger.info(f"Trading session determined: {session} at {current_time} ET")
    return session