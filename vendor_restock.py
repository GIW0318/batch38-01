class VendorStock:
    QUOTE_TTL = 30
    BUYBACK_TTL = 300
    BUYBACK_MAX = 12
    DAY_RESET_SECONDS = 5 * 3600
    REPUTATION_DISCOUNTS = (0.0, 0.02, 0.05, 0.08, 0.12, 0.15)

    def __init__(self, items, reputation=0):
        self.items = items
        self.reputation = reputation
        self.gold = {}
        self._quotes = {}
        self._quote_seq = 0
        self._sold = {}
        self._item_sold = {}
        self._buyback = {}

    def set_gold(self, player, amount):
        self.gold[player] = amount

    @staticmethod
    def _item_id(item):
        return item["id"] if isinstance(item, dict) else item

    @staticmethod
    def _check_count(count):
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ValueError("count must be a positive integer")

    def _item(self, item_id):
        entry = self.items.get(item_id)
        if entry is None:
            raise ValueError("unknown item: %s" % item_id)
        return entry

    @classmethod
    def _day_key(cls, ts):
        return (ts - cls.DAY_RESET_SECONDS) // 86400

    def _sold_today(self, player, item_id, ts):
        entry = self._sold.get((player, item_id))
        if entry is None or entry[0] != self._day_key(ts):
            return 0
        return entry[1]

    def _record_sale(self, player, item_id, count, ts):
        day = self._day_key(ts)
        key = (player, item_id)
        entry = self._sold.get(key)
        if entry is None or entry[0] != day:
            self._sold[key] = [day, count]
        else:
            entry[1] += count
        total = self._item_sold.get(item_id)
        if total is None or total[0] != day:
            self._item_sold[item_id] = [day, count]
        else:
            total[1] += count

    def _check_daily_limit(self, player, item_id, entry, count, ts):
        limit = entry.get("daily_limit")
        if limit is not None and self._sold_today(player, item_id, ts) + count > limit:
            raise ValueError("daily limit exceeded for %s" % item_id)

    def _unit_price(self, entry):
        price = float(entry["base_price"])
        max_stock = entry.get("max_stock") or entry["stock"] or 1
        ratio = entry["stock"] / max_stock
        if ratio < 0.2:
            price *= 1.2
        elif 0.8 < ratio < 1.0:
            price *= 0.9
        level = min(max(int(self.reputation), 0), len(self.REPUTATION_DISCOUNTS) - 1)
        price *= 1 - self.REPUTATION_DISCOUNTS[level]
        return int(round(price))

    def quote(self, player, item, count, ts):
        self._check_count(count)
        item_id = self._item_id(item)
        entry = self._item(item_id)
        if entry["stock"] < count:
            raise ValueError("insufficient stock for %s" % item_id)
        self._check_daily_limit(player, item_id, entry, count, ts)
        price = self._unit_price(entry)
        self._quote_seq += 1
        quote_id = "q%d" % self._quote_seq
        self._quotes[quote_id] = {
            "quote_id": quote_id,
            "player": player,
            "item": item_id,
            "count": count,
            "price": price,
            "stock": entry["stock"],
            "expires_at": ts + self.QUOTE_TTL,
        }
        return {"quote_id": quote_id, "price": price, "expires_at": ts + self.QUOTE_TTL}

    def buy(self, player, item, count, quote_id, ts):
        self._check_count(count)
        item_id = self._item_id(item)
        entry = self._item(item_id)
        quote = self._quotes.get(quote_id)
        if quote is None:
            raise ValueError("unknown or consumed quote: %s" % quote_id)
        if ts > quote["expires_at"]:
            raise ValueError("quote expired")
        if quote["player"] != player or quote["item"] != item_id or quote["count"] != count:
            raise ValueError("quote does not match purchase")
        if entry["stock"] != quote["stock"] or self._unit_price(entry) != quote["price"]:
            raise ValueError("quote invalidated by stock or price change")
        if entry["stock"] < count:
            raise ValueError("insufficient stock for %s" % item_id)
        self._check_daily_limit(player, item_id, entry, count, ts)
        total = quote["price"] * count
        balance = self.gold.get(player)
        if balance is not None and balance < total:
            raise ValueError("insufficient gold")
        del self._quotes[quote_id]
        entry["stock"] -= count
        self._record_sale(player, item_id, count, ts)
        if balance is not None:
            self.gold[player] = balance - total
        return {"item": item_id, "count": count, "total": total}

    def sell(self, player, item, count, ts):
        self._check_count(count)
        item_id = self._item_id(item)
        entry = self._item(item_id)
        if entry.get("bound"):
            raise ValueError("bound items cannot be sold")
        price = self._unit_price(entry) // 2
        gold = price * count
        self.gold[player] = self.gold.get(player, 0) + gold
        backlog = self._buyback.setdefault(player, [])
        backlog.append({
            "item": item_id,
            "count": count,
            "price": price,
            "ts": ts,
        })
        del backlog[:-self.BUYBACK_MAX]
        return {"item": item_id, "count": count, "gold": gold}

    def restock(self, ts):
        for entry in self.items.values():
            entry["stock"] = entry.get("max_stock", entry["stock"])

    def buyback(self, player, index, ts):
        backlog = self._buyback.get(player)
        if not backlog or not 0 <= index < len(backlog):
            raise ValueError("no such buyback entry: %s" % index)
        entry = backlog[index]
        if ts - entry["ts"] > self.BUYBACK_TTL:
            raise ValueError("buyback entry expired")
        total = entry["price"] * entry["count"]
        balance = self.gold.get(player)
        if balance is not None and balance < total:
            raise ValueError("insufficient gold")
        if balance is not None:
            self.gold[player] = balance - total
        del backlog[index]
        return dict(entry)

    def shelves(self):
        items = {}
        for item_id, entry in self.items.items():
            sold = self._item_sold.get(item_id)
            items[item_id] = {
                "id": item_id,
                "stock": entry["stock"],
                "max_stock": entry.get("max_stock"),
                "sold_today": sold[1] if sold else 0,
                "buyback": sum(
                    1
                    for backlog in self._buyback.values()
                    for record in backlog
                    if record["item"] == item_id
                ),
            }
        return {
            "items": items,
            "buyback": sum(len(backlog) for backlog in self._buyback.values()),
        }
