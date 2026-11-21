"""Wallet ledger with currency caps, escrow/refund and reconciliation."""

CURRENCIES = ("gold", "valor", "honor")

GOLD_CHAR_CAP = 100_000
GOLD_ACCOUNT_CAP = 1_000_000
VALOR_WEEKLY_CAP = 10_000
HONOR_DAILY_CAP = 5_000
TRANSFER_DAILY_LIMIT = 10_000

DAY_SECONDS = 86_400
RESET_OFFSET = 5 * 3600
EPOCH_WEEKDAY = 3

CATCH_UP_PER_MISSED_WEEK = 0.5
CATCH_UP_MAX_MULTIPLIER = 3.0
MAX_MISSED_WEEKS = 4


def _day_key(now):
    return (now - RESET_OFFSET) // DAY_SECONDS


def _week_key(now):
    day = (now - RESET_OFFSET) // DAY_SECONDS
    return (day + EPOCH_WEEKDAY) // 7


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class WalletLedger:
    def __init__(self):
        self._balances = {}
        self._frozen = {}
        self._mail = {}
        self._orders = {}
        self._journal = []
        self._seq = 0
        self._last_time = None
        self._transfer_out = {}
        self._valor_used = {}
        self._honor_used = {}
        self._missed_weeks = {}
        self._last_rollover_week = None

    def _wallet(self, player):
        return self._balances.setdefault(player, {c: 0 for c in CURRENCIES})

    def _check_time(self, now):
        if not _is_number(now):
            raise ValueError("invalid timestamp")
        if self._last_time is not None and now < self._last_time:
            raise ValueError("time moved backwards")

    def _validate(self, currency, amount, now):
        if currency not in CURRENCIES:
            raise ValueError("unknown currency: %r" % (currency,))
        if not _is_number(amount) or amount <= 0:
            raise ValueError("amount must be a positive number")
        self._check_time(now)

    def _append(self, op, **fields):
        self._seq += 1
        entry = {"seq": self._seq, "op": op}
        entry.update(fields)
        self._journal.append(entry)
        return entry

    def _catch_up_multiplier(self, player):
        missed = self._missed_weeks.get(player, 0)
        return min(1 + CATCH_UP_PER_MISSED_WEEK * missed, CATCH_UP_MAX_MULTIPLIER)

    def _credit(self, player, currency, amount, now):
        if currency == "gold":
            total = sum(w["gold"] for w in self._balances.values())
            if total + amount > GOLD_ACCOUNT_CAP:
                raise ValueError("account gold cap exceeded")
            wallet = self._wallet(player)
            room = max(0, GOLD_CHAR_CAP - wallet["gold"])
            if amount <= room:
                return amount, 0
            excess = amount - room
            mailed = excess // 2 if isinstance(excess, int) else excess / 2
            return amount - excess, mailed
        if currency == "valor":
            key = (player, _week_key(now))
            cap = VALOR_WEEKLY_CAP * self._catch_up_multiplier(player)
            room = max(0, cap - self._valor_used.get(key, 0))
            credited = min(amount, room)
            self._valor_used[key] = self._valor_used.get(key, 0) + credited
            return credited, 0
        key = (player, _day_key(now))
        room = max(0, HONOR_DAILY_CAP - self._honor_used.get(key, 0))
        credited = min(amount, room)
        self._honor_used[key] = self._honor_used.get(key, 0) + credited
        return credited, 0

    def _add_mail(self, player, currency, amount):
        if amount:
            box = self._mail.setdefault(player, {c: 0 for c in CURRENCIES})
            box[currency] += amount

    def earn(self, player, currency, amount, now, source):
        self._validate(currency, amount, now)
        credited, mailed = self._credit(player, currency, amount, now)
        self._wallet(player)[currency] += credited
        self._add_mail(player, currency, mailed)
        self._last_time = now
        self._append("earn", player=player, currency=currency, amount=amount,
                     credited=credited, mailed=mailed, source=source, ts=now)

    def spend(self, player, currency, amount, now):
        self._validate(currency, amount, now)
        wallet = self._wallet(player)
        if wallet[currency] < amount:
            raise ValueError("insufficient funds")
        wallet[currency] -= amount
        self._last_time = now
        self._append("spend", player=player, currency=currency, amount=amount, ts=now)

    def transfer(self, src, dst, currency, amount, now):
        self._validate(currency, amount, now)
        day = _day_key(now)
        key = (src, day)
        used = self._transfer_out.get(key, 0)
        if used + amount > TRANSFER_DAILY_LIMIT:
            raise ValueError("daily transfer limit exceeded")
        wallet = self._wallet(src)
        if wallet[currency] < amount:
            raise ValueError("insufficient funds")
        credited, mailed = self._credit(dst, currency, amount, now)
        wallet[currency] -= amount
        self._wallet(dst)[currency] += credited
        self._add_mail(dst, currency, mailed)
        self._transfer_out[key] = used + amount
        self._last_time = now
        self._append("transfer", src=src, dst=dst, currency=currency,
                     amount=amount, dst_credited=credited, dst_mailed=mailed, ts=now)

    def escrow(self, player, currency, amount, order_id, now):
        self._validate(currency, amount, now)
        if order_id in self._orders:
            raise ValueError("duplicate order id: %r" % (order_id,))
        wallet = self._wallet(player)
        if wallet[currency] < amount:
            raise ValueError("insufficient funds")
        wallet[currency] -= amount
        self._frozen[player] = self._frozen.get(player, 0) + amount
        self._orders[order_id] = {"player": player, "currency": currency,
                                  "amount": amount, "status": "open"}
        self._last_time = now
        self._append("escrow", player=player, currency=currency, amount=amount,
                     order_id=order_id, ts=now)

    def _open_order(self, order_id, now):
        self._check_time(now)
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError("unknown order id: %r" % (order_id,))
        if order["status"] != "open":
            raise ValueError("order %r already %s" % (order_id, order["status"]))
        return order

    def settle(self, order_id, now):
        order = self._open_order(order_id, now)
        order["status"] = "settled"
        self._frozen[order["player"]] -= order["amount"]
        self._last_time = now
        self._append("settle", order_id=order_id, player=order["player"],
                     currency=order["currency"], amount=order["amount"], ts=now)

    def refund(self, order_id, now):
        order = self._open_order(order_id, now)
        order["status"] = "refunded"
        self._frozen[order["player"]] -= order["amount"]
        self._wallet(order["player"])[order["currency"]] += order["amount"]
        self._last_time = now
        self._append("refund", order_id=order_id, player=order["player"],
                     currency=order["currency"], amount=order["amount"], ts=now)

    def rollover(self, now):
        self._check_time(now)
        week = _week_key(now)
        if self._last_rollover_week == week:
            self._last_time = now
            return
        previous = self._last_rollover_week
        self._last_rollover_week = week
        if previous is not None and week > previous:
            elapsed = week - previous
            players = set(self._balances)
            players.update(player for player, _ in self._valor_used)
            for player in players:
                if self._valor_used.get((player, previous), 0) > 0:
                    self._missed_weeks[player] = 0
                else:
                    self._missed_weeks[player] = min(
                        MAX_MISSED_WEEKS,
                        self._missed_weeks.get(player, 0) + elapsed)
        self._last_time = now
        self._append("rollover", week=week, ts=now)

    def _snapshot(self):
        players = set(self._balances) | set(self._frozen) | set(self._mail)
        snap = {}
        for player in players:
            info = dict(self._balances.get(player, {c: 0 for c in CURRENCIES}))
            info["frozen"] = self._frozen.get(player, 0)
            mail = self._mail.get(player)
            if mail:
                info["mail"] = sum(mail.values())
            snap[player] = info
        return snap

    def balance_check(self):
        replayed_bal = {}
        replayed_frozen = {}
        replayed_mail = {}

        def wallet(player):
            return replayed_bal.setdefault(player, {c: 0 for c in CURRENCIES})

        for entry in self._journal:
            op = entry["op"]
            if op == "earn":
                wallet(entry["player"])[entry["currency"]] += entry["credited"]
                if entry["mailed"]:
                    replayed_mail[entry["player"]] = (
                        replayed_mail.get(entry["player"], 0) + entry["mailed"])
            elif op == "spend":
                wallet(entry["player"])[entry["currency"]] -= entry["amount"]
            elif op == "transfer":
                wallet(entry["src"])[entry["currency"]] -= entry["amount"]
                wallet(entry["dst"])[entry["currency"]] += entry["dst_credited"]
                if entry["dst_mailed"]:
                    replayed_mail[entry["dst"]] = (
                        replayed_mail.get(entry["dst"], 0) + entry["dst_mailed"])
            elif op == "escrow":
                wallet(entry["player"])[entry["currency"]] -= entry["amount"]
                replayed_frozen[entry["player"]] = (
                    replayed_frozen.get(entry["player"], 0) + entry["amount"])
            elif op == "settle":
                replayed_frozen[entry["player"]] = (
                    replayed_frozen.get(entry["player"], 0) - entry["amount"])
            elif op == "refund":
                replayed_frozen[entry["player"]] = (
                    replayed_frozen.get(entry["player"], 0) - entry["amount"])
                wallet(entry["player"])[entry["currency"]] += entry["amount"]

        difference = 0
        divergent = set()
        players = (set(self._balances) | set(replayed_bal) | set(self._frozen)
                   | set(replayed_frozen) | set(self._mail) | set(replayed_mail))
        for player in players:
            actual = self._balances.get(player, {c: 0 for c in CURRENCIES})
            replay = replayed_bal.get(player, {c: 0 for c in CURRENCIES})
            for currency in CURRENCIES:
                delta = actual.get(currency, 0) - replay.get(currency, 0)
                if delta:
                    difference += abs(delta)
                    divergent.add(player)
            delta = self._frozen.get(player, 0) - replayed_frozen.get(player, 0)
            if delta:
                difference += abs(delta)
                divergent.add(player)
            actual_mail = sum(self._mail[player].values()) if player in self._mail else 0
            delta = actual_mail - replayed_mail.get(player, 0)
            if delta:
                difference += abs(delta)
                divergent.add(player)

        min_diff_seq = None
        if difference:
            seqs = []
            for entry in self._journal:
                involved = {entry.get("player"), entry.get("src"), entry.get("dst")}
                if involved & divergent:
                    seqs.append(entry["seq"])
            if seqs:
                min_diff_seq = min(seqs)

        return {"balances": self._snapshot(),
                "difference": difference,
                "min_diff_seq": min_diff_seq}

    def journal(self):
        return [dict(entry) for entry in self._journal]
