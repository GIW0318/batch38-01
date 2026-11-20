"""Layered raid damage pipeline.

Settlement order: redirect -> penetration -> resist -> armor -> shield -> hp.

- Redirect moves at most 50% of a hit to another target; redirected damage
  cannot be redirected again, and chains or cycles are rejected.
- Resist is capped at 70%; armor reduction is armor/(armor+100) capped at 75%.
- Penetration: 40% of the remaining damage bypasses shields, so shields can
  absorb at most 60% of a single hit. Shields only absorb their own damage
  type; same-type shields are consumed by priority, then by expiry.
- Dots snapshot their per-tick mitigated value at application time; later
  stat changes do not affect them, and invulnerability does not block them.
- Invulnerability blocks direct hits only. Overkill is clamped to current
  hp and counted separately.
"""

KNOWN_DTYPES = frozenset({"physical", "fire", "frost", "nature", "shadow", "arcane"})

RESIST_CAP = 0.7
ARMOR_CAP = 0.75
REDIRECT_CAP = 0.5
SHIELD_PENETRATION = 0.4
SHIELD_ABSORB_CAP = 1.0 - SHIELD_PENETRATION


class DamagePipeline:
    def __init__(self, targets):
        self.targets = targets
        self.now = 0
        self._shields = {name: [] for name in targets}
        self._redirects = {}
        self._dots = {name: [] for name in targets}
        self.overkill = {name: 0 for name in targets}

    def _target(self, name):
        if name not in self.targets:
            raise ValueError("unknown target: %r" % (name,))
        return self.targets[name]

    @staticmethod
    def _check_amount(amount):
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not amount > 0:
            raise ValueError("amount must be a positive number")

    @staticmethod
    def _check_dtype(dtype):
        if dtype not in KNOWN_DTYPES:
            raise ValueError("unknown damage type: %r" % (dtype,))

    def _mitigated(self, t, amount, dtype):
        resist = t.get("resist", {}).get(dtype, 0)
        resist = min(max(resist, 0), RESIST_CAP)
        amount *= 1 - resist
        armor = max(t.get("armor", 0), 0)
        reduction = min(armor / (armor + 100), ARMOR_CAP)
        return amount * (1 - reduction)

    def _absorb(self, name, dtype, absorbable):
        shields = [
            s for s in self._shields[name]
            if s["until"] > self.now and (s["dtype"] == dtype or s["dtype"] is None)
        ]
        shields.sort(key=lambda s: (-s["priority"], s["until"]))
        absorbed = 0.0
        for s in shields:
            if absorbed >= absorbable:
                break
            take = min(s["amount"], absorbable - absorbed)
            s["amount"] -= take
            absorbed += take
        self._shields[name] = [s for s in self._shields[name] if s["amount"] > 0]
        return absorbed

    def _deal(self, name, damage, dtype, result):
        t = self._target(name)
        damage = self._mitigated(t, damage, dtype)
        absorbed = self._absorb(name, dtype, damage * SHIELD_ABSORB_CAP)
        result["absorbed"] += absorbed
        damage -= absorbed
        dealt = min(damage, t["hp"])
        overkill = damage - dealt
        t["hp"] -= dealt
        result["dealt"] += dealt
        result["overkill"] += overkill
        self.overkill[name] += overkill

    def hit(self, target, amount, dtype, source=None):
        t = self._target(target)
        self._check_amount(amount)
        self._check_dtype(dtype)
        result = {"blocked": False, "dealt": 0.0, "overkill": 0.0,
                  "absorbed": 0.0, "redirected": 0.0}
        if t.get("invuln_until", 0) > self.now:
            result["blocked"] = True
            return result
        remaining = amount
        red = self._redirects.get(target)
        if red and red["until"] > self.now:
            portion = remaining * red["pct"]
            remaining -= portion
            result["redirected"] = portion
            self._deal(red["to"], portion, dtype, result)
        self._deal(target, remaining, dtype, result)
        return result

    def shield(self, target, amount, until, dtype, priority=0):
        self._target(target)
        self._check_amount(amount)
        self._check_dtype(dtype)
        if until <= self.now:
            raise ValueError("shield is already expired")
        entry = {"amount": amount, "until": until, "dtype": dtype, "priority": priority}
        self._shields[target].append(entry)
        return dict(entry)

    def redirect(self, target, to, pct, until):
        self._target(target)
        self._target(to)
        if to == target:
            raise ValueError("cannot redirect to self")
        if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not 0 < pct <= 1:
            raise ValueError("redirect pct must be in (0, 1]")
        if until <= self.now:
            raise ValueError("redirect is already expired")
        current = self._redirects.get(target)
        if current and current["until"] > self.now:
            raise ValueError("target already has an active redirect")
        for red in self._redirects.values():
            if red["until"] > self.now and red["to"] == target:
                raise ValueError("redirect chains are not allowed")
        seen = {target}
        node = to
        while node in self._redirects and self._redirects[node]["until"] > self.now:
            node = self._redirects[node]["to"]
            if node in seen:
                raise ValueError("redirect cycle detected")
            seen.add(node)
        entry = {"to": to, "pct": min(pct, REDIRECT_CAP), "until": until}
        self._redirects[target] = entry
        return dict(entry)

    def dot(self, target, amount, dtype, ticks, interval, now):
        t = self._target(target)
        self._check_amount(amount)
        self._check_dtype(dtype)
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks <= 0:
            raise ValueError("ticks must be a positive integer")
        if not interval > 0:
            raise ValueError("interval must be positive")
        self.now = max(self.now, now)
        entry = {
            "dtype": dtype,
            "per_tick": self._mitigated(t, amount, dtype),
            "remaining": ticks,
            "interval": interval,
            "next_at": now + interval,
        }
        self._dots[target].append(entry)
        return dict(entry)

    def tick(self, ts):
        self.now = ts
        for name in self._shields:
            self._shields[name] = [s for s in self._shields[name] if s["until"] > ts]
        self._redirects = {
            k: r for k, r in self._redirects.items() if r["until"] > ts
        }
        result = {"ticks": 0, "dealt": 0.0, "overkill": 0.0}
        for name, dots in self._dots.items():
            t = self.targets[name]
            for d in dots:
                while d["remaining"] > 0 and d["next_at"] <= ts:
                    dealt = min(d["per_tick"], t["hp"])
                    overkill = d["per_tick"] - dealt
                    t["hp"] -= dealt
                    self.overkill[name] += overkill
                    result["ticks"] += 1
                    result["dealt"] += dealt
                    result["overkill"] += overkill
                    d["remaining"] -= 1
                    d["next_at"] += d["interval"]
            self._dots[name] = [d for d in dots if d["remaining"] > 0]
        return result

    def snapshot(self, target):
        t = self._target(target)
        armor = max(t.get("armor", 0), 0)
        red = self._redirects.get(target)
        return {
            "hp": t["hp"],
            "shields": [dict(s) for s in self._shields[target] if s["until"] > self.now],
            "dots": [dict(d) for d in self._dots[target]],
            "mitigation": {
                "resist": {
                    k: min(max(v, 0), RESIST_CAP) for k, v in t.get("resist", {}).items()
                },
                "armor_reduction": min(armor / (armor + 100), ARMOR_CAP),
                "redirect": dict(red) if red and red["until"] > self.now else None,
                "invulnerable": t.get("invuln_until", 0) > self.now,
                "overkill": self.overkill[target],
            },
        }
