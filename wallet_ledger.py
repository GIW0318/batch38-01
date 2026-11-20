class WalletLedger:
    def __init__(self):
        pass

    def earn(self, player, currency, amount, now, source):
        return None

    def spend(self, player, currency, amount, now):
        return None

    def transfer(self, src, dst, currency, amount, now):
        return None

    def escrow(self, player, currency, amount, order_id, now):
        return None

    def settle(self, order_id, now):
        return None

    def refund(self, order_id, now):
        return None

    def rollover(self, now):
        return None

    def balance_check(self):
        return {}

    def journal(self):
        return []
