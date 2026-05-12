class Account:
    def __init__(self, account_id, balance, buying_power, currency, day_change=0):
        self.account_id = account_id
        self.balance = balance
        self.buying_power = buying_power
        self.currency = currency
        self.day_change = day_change

    def to_dict(self):
        return {
            'account_id': self.account_id,
            'balance': self.balance,
            'buying_power': self.buying_power,
            'currency': self.currency,
            'day_change':self.day_change
        }