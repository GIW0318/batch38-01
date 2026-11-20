class VendorStock:
    def __init__(self, items, reputation=0):
        self.items = items
        self.reputation = reputation

    def quote(self, player, item, count, ts):
        return None

    def buy(self, player, item, count, quote_id, ts):
        return None

    def sell(self, player, item, count, ts):
        return None

    def restock(self, ts):
        return None

    def buyback(self, player, index, ts):
        return None

    def shelves(self):
        return {}
