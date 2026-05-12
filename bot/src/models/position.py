from datetime import datetime

class Position:
    def __init__(self, symbol, quantity, side, market_value, current_price, change_today):
        self.symbol = symbol
        self.quantity = quantity
        self.side = side
        self.market_value = market_value
        self.current_price = current_price
        self.change_today = change_today
        self.position_date = datetime.utcnow()
        self.order_cancelled = False
        

    def position_age(self) -> int:
        """Returns the age of the position in milliseconds."""
        delta = datetime.utcnow() - self.position_date
        return int(delta.total_seconds() * 1000)
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'side': self.side,
            'market_value': self.market_value,
            'current_price': self.current_price,
            'change_today': self.change_today,
            'position_date': self.position_date.isoformat(),
            'order_cancelled': self.order_cancelled,
            'position_age': self.position_age()
        }

class Positions:

    def __init__(self):
        self.positions = []

    def add_position(self, position):
        self.positions.append(position)

    def to_dict(self):
        if len(self.positions) == 0:
            return []
        else:
            return [vars(pos) for pos in self.positions]