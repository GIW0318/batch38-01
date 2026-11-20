CLAIM_TTL = 600
MAX_ACTIVE_CLAIMS_PER_PLAYER = 3


def _player_info(player):
    if isinstance(player, dict):
        name = player["name"]
        level = player.get("level", 1)
        party = list(player.get("party") or [name])
    else:
        name = player
        level = 1
        party = [name]
    return name, level, party


class BountyBoard:
    def __init__(self):
        self._contracts = {}

    def post(self, contract, now):
        record = dict(contract)
        record["claims"] = {}
        record["completions"] = 0
        record["expired"] = now > record["expires_at"]
        self._contracts[record["id"]] = record
        return None

    def _get(self, contract_id):
        record = self._contracts.get(contract_id)
        if record is None:
            raise ValueError(f"unknown contract: {contract_id}")
        return record

    def _release_stale_claims(self, now):
        for record in self._contracts.values():
            stale = [
                name
                for name, claimed_at in record["claims"].items()
                if now - claimed_at > CLAIM_TTL
            ]
            for name in stale:
                del record["claims"][name]

    def _active_claims_of(self, name):
        return sum(
            1 for record in self._contracts.values() if name in record["claims"]
        )

    def claim(self, player, contract_id, now):
        name, level, _party = _player_info(player)
        self._release_stale_claims(now)
        record = self._get(contract_id)
        if record["expired"] or now > record["expires_at"]:
            raise ValueError("contract expired")
        if name == record["poster"]:
            raise ValueError("cannot claim own contract")
        if level < record["min_level"]:
            raise ValueError("level too low")
        if name in record["claims"]:
            raise ValueError("already claimed")
        if len(record["claims"]) + record["completions"] >= record["max_claims"]:
            raise ValueError("max claims reached")
        if self._active_claims_of(name) >= MAX_ACTIVE_CLAIMS_PER_PLAYER:
            raise ValueError("too many active claims")
        record["claims"][name] = now
        return None

    def complete(self, player, contract_id, now):
        name, _level, party = _player_info(player)
        self._release_stale_claims(now)
        record = self._get(contract_id)
        if record["expired"] or now > record["expires_at"]:
            raise ValueError("contract expired")
        if name not in record["claims"]:
            raise ValueError("only the claimant can complete")
        del record["claims"][name]
        record["completions"] += 1
        reward = record["reward"]
        share = reward // len(party)
        shares = {member: share for member in party}
        shares[party[0]] += reward - share * len(party)
        return {"reward": reward, "shares": shares}

    def expire(self, now):
        self._release_stale_claims(now)
        for record in self._contracts.values():
            if now > record["expires_at"]:
                record["expired"] = True
        return None

    def board_view(self):
        view = {"open": 0, "in_progress": 0, "completed": 0, "expired": 0}
        for record in self._contracts.values():
            if record["expired"]:
                view["expired"] += 1
            elif record["claims"]:
                view["in_progress"] += 1
            elif record["completions"]:
                view["completed"] += 1
            else:
                view["open"] += 1
        return view
