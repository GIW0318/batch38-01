import random

MAX_WEIGHT = 500
SPEED = 100.0  # distance units per hour
GUARD_RISK_FACTOR = 0.9
MIN_RISK = 0.05
MORALE_PENALTY = 1.1
ATTACK_LOSS_RATE = 0.20
SPOIL_AFTER_HOURS = 48.0
SPOIL_RATE_PER_HOUR = 0.05
REROUTE_PENALTY_HOURS = 2.0
REROUTE_FREIGHT_SURCHARGE = 0.10
PREMIUM_RATE = 0.05
CLAIM_COVER_RATE = 0.70
GUARD_COST_PER_GUARD = 100.0


class CaravanPlan:
    def __init__(self):
        self._reset()

    def _reset(self):
        self._route = []
        self._cargo = []
        self._guards = 0
        self._insurance = False
        self._seed = 0
        self._rng = random.Random(0)
        self._planned = False
        self._departed = False
        self._depart_ts = None
        self._arrived = False
        self._arrive_ts = None
        self._reroute_penalty_seconds = 0.0
        self._freight_factor = 1.0
        self._leg_losses = []
        self._spoilage_loss = 0.0
        self._claimed = False
        self._claim_amount = 0.0

    def plan(self, route, cargo, guards, insurance, seed):
        if seed < 0:
            raise ValueError("seed must be non-negative")
        if not cargo:
            raise ValueError("cargo must not be empty")
        if sum(item["weight"] for item in cargo) > MAX_WEIGHT:
            raise ValueError("cargo exceeds max weight")
        if guards < 0:
            raise ValueError("guards must be non-negative")
        if any(leg["closed"] for leg in route):
            raise ValueError("route contains a closed leg")
        self._reset()
        self._route = [dict(leg) for leg in route]
        self._cargo = [dict(item) for item in cargo]
        self._guards = guards
        self._insurance = insurance
        self._seed = seed
        self._rng = random.Random(seed)
        self._leg_losses = [0.0] * len(self._route)
        self._planned = True

    def depart(self, ts):
        if not self._planned:
            raise ValueError("no route planned")
        if self._departed:
            raise ValueError("caravan already departed")
        self._departed = True
        self._depart_ts = ts
        self._resolve_attacks()

    def reroute(self, leg_index, new_path, ts):
        if not self._departed or self._arrived:
            raise ValueError("cannot reroute now")
        if not 0 <= leg_index < len(self._route):
            raise ValueError("invalid leg index")
        if new_path["closed"]:
            raise ValueError("new path is closed")
        elapsed = ts - self._depart_ts
        leg_start = sum(
            self._leg_duration(self._route[i]) for i in range(leg_index)
        )
        if elapsed >= leg_start:
            raise ValueError("can only reroute legs not yet traveled")
        self._route[leg_index] = dict(new_path)
        self._leg_losses[leg_index] = 0.0
        if self._rng.random() < self._leg_risk(self._route[leg_index]):
            self._leg_losses[leg_index] = ATTACK_LOSS_RATE * self._cargo_value()
        self._reroute_penalty_seconds += REROUTE_PENALTY_HOURS * 3600.0
        self._freight_factor *= 1.0 + REROUTE_FREIGHT_SURCHARGE

    def arrive(self, ts):
        if not self._departed:
            raise ValueError("caravan has not departed")
        if self._arrived:
            raise ValueError("caravan already arrived")
        elapsed = ts - self._depart_ts
        if elapsed < self._duration():
            raise ValueError("arrival earlier than total duration")
        self._arrived = True
        self._arrive_ts = ts
        hours = elapsed / 3600.0
        if hours > SPOIL_AFTER_HOURS:
            perishable_value = sum(
                item["value"] for item in self._cargo if item["perishable"]
            )
            spoil_rate = (hours - SPOIL_AFTER_HOURS) * SPOIL_RATE_PER_HOUR
            self._spoilage_loss = perishable_value * min(spoil_rate, 1.0)

    def claim(self, ts):
        if not self._arrived:
            raise ValueError("cannot claim before arrival")
        if not self._insurance:
            raise ValueError("no insurance purchased")
        if self._claimed:
            raise ValueError("claim already settled for this trip")
        self._claimed = True
        self._claim_amount = CLAIM_COVER_RATE * self._total_loss()

    def manifest(self):
        value = self._cargo_value()
        loss = self._total_loss()
        premium = PREMIUM_RATE * value if self._insurance else 0.0
        guard_cost = GUARD_COST_PER_GUARD * self._guards
        claim = self._claim_amount if self._claimed else 0.0
        profit = value - value - guard_cost - premium - loss + claim
        return {
            "duration": self._duration(),
            "risk": self._overall_risk(),
            "loss": loss,
            "leg_losses": list(self._leg_losses),
            "guard_cost": guard_cost,
            "premium": premium,
            "claim": claim,
            "claimed": self._claimed,
            "profit": profit,
        }

    def _cargo_value(self):
        return sum(item["value"] for item in self._cargo)

    def _total_loss(self):
        return sum(self._leg_losses) + self._spoilage_loss

    def _leg_duration(self, leg):
        return leg["distance"] / SPEED * 3600.0

    def _duration(self):
        travel = sum(self._leg_duration(leg) for leg in self._route)
        return travel + self._reroute_penalty_seconds

    def _leg_risk(self, leg):
        return max(leg["risk"] * (GUARD_RISK_FACTOR ** self._guards), MIN_RISK)

    def _overall_risk(self):
        safe = 1.0
        for leg in self._route:
            safe *= 1.0 - self._leg_risk(leg)
        return 1.0 - safe

    def _resolve_attacks(self):
        morale = 1.0
        for i, leg in enumerate(self._route):
            risk = min(self._leg_risk(leg) * morale, 1.0)
            if self._rng.random() < risk:
                self._leg_losses[i] += ATTACK_LOSS_RATE * self._cargo_value()
                morale *= MORALE_PENALTY
