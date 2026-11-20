import copy
import secrets


class VaultQuorum:
    REQUEST_TTL = 120
    APPROVAL_TTL = 60
    MIN_THRESHOLD = 3
    FAILURE_LIMIT = 5
    LOCK_SECONDS = 300

    RECOVERY_ACTIONS = {
        "admin_recovery",
        "admin_reset",
        "clear_failures",
        "clear_lockout",
        "recover",
        "recover_lockout",
        "recovery",
        "lockout",
        "lockout_recovery",
        "lockout_reset",
        "reset",
        "reset_failures",
        "reset_lockout",
        "restore",
        "restore_lockout",
        "supervisor_recovery",
        "supervisor_reset",
    }

    def __init__(self, vaults, operators):
        self.vaults = copy.deepcopy(vaults)
        self.operators = copy.deepcopy(operators)
        self.requests = {}
        self._vault_state = {
            name: {
                "failures": 0,
                "locked_until": None,
                "recovered": False,
            }
            for name in self.vaults
        }
        self._recovery_approvals = {}
        self._events = []
        self._sequence = 0

    def open_request(self, vault, action, operators, ttl, now):
        if vault not in self.vaults:
            self._reject("open", "unknown_vault", now=now, vault=vault)

        state = self._vault_state[vault]
        if self._is_locked(state, now):
            self._reject("open", "vault_locked", now=now, vault=vault)
        if self._recovery_required(state, now) and not self._is_recovery_action(action):
            self._reject("open", "recovery_required", now=now, vault=vault, action=action)

        if not isinstance(action, str) or not action.strip():
            self._reject("open", "invalid_action", now=now, vault=vault)
        if not isinstance(operators, list) or not operators:
            self._reject("open", "empty_operators", now=now, vault=vault, action=action)
        if not isinstance(ttl, (int, float)) or isinstance(ttl, bool) or ttl <= 0:
            self._reject("open", "invalid_ttl", now=now, vault=vault, action=action)

        names = list(operators)
        if (
            len(names) != len(set(names))
            or any(not isinstance(name, str) or not name.strip() for name in names)
        ):
            self._reject("open", "duplicate_or_empty_operator", now=now, vault=vault, action=action)

        threshold = self._threshold(vault, action)
        if len(names) < threshold:
            self._reject("open", "insufficient_operators", now=now, vault=vault, action=action)

        seen_credentials = set()
        seen_identities = set()
        for name in names:
            record = self._eligible_operator(
                name,
                vault,
                action,
                now=now,
                operation="open",
            )
            credential = record["credential"]
            identity = self._identity(name, record)
            if credential in seen_credentials or identity in seen_identities:
                self._reject(
                    "open",
                    "operators_are_not_distinct",
                    now=now,
                    vault=vault,
                    action=action,
                    operator=name,
                )
            seen_credentials.add(credential)
            seen_identities.add(identity)

        request_id = secrets.token_hex(16)
        expires_at = now + min(ttl, self.REQUEST_TTL)
        request = {
            "request_id": request_id,
            "vault": vault,
            "action": action,
            "operators": names,
            "threshold": threshold,
            "created_at": now,
            "expires_at": expires_at,
            "status": "open",
            "approvals": {},
            "unlocked_at": None,
            "denied_at": None,
        }
        self.requests[request_id] = request
        self._append(
            "open",
            now,
            request_id=request_id,
            vault=vault,
            action=action,
            operators=names,
            threshold=threshold,
            expires_at=expires_at,
        )
        return self._public_request(request)

    def approve(self, request_id, operator, credential, now):
        request = self.requests.get(request_id)
        if request is None:
            self._reject(
                "approve",
                "unknown_request",
                now=now,
                request_id=request_id,
                operator=operator,
            )

        vault = request["vault"]
        state = self._vault_state[vault]
        if self._is_locked(state, now):
            self._reject(
                "approve",
                "vault_locked",
                now=now,
                request_id=request_id,
                vault=vault,
                operator=operator,
            )
        if (
            self._recovery_required(state, now)
            and not self._is_recovery_action(request["action"])
        ):
            self._reject(
                "approve",
                "recovery_required",
                now=now,
                request_id=request_id,
                vault=vault,
                operator=operator,
            )
        if request["status"] != "open":
            self._reject(
                "approve",
                "request_not_open",
                now=now,
                request_id=request_id,
                vault=vault,
                operator=operator,
            )
        if not self._request_is_live(request, now):
            self._reject(
                "approve",
                "request_expired",
                now=now,
                request_id=request_id,
                vault=vault,
                operator=operator,
            )
        if not isinstance(operator, str) or not operator.strip():
            self._reject(
                "approve",
                "empty_operator",
                now=now,
                request_id=request_id,
                vault=vault,
            )
        if operator not in request["operators"]:
            self._reject(
                "approve",
                "operator_not_authorized",
                now=now,
                request_id=request_id,
                vault=vault,
                action=request["action"],
                operator=operator,
            )

        record = self._eligible_operator(
            operator,
            vault,
            request["action"],
            now=now,
            request_id=request_id,
            operation="approve",
        )
        if credential != record["credential"]:
            self._reject(
                "approve",
                "wrong_credential",
                now=now,
                request_id=request_id,
                vault=vault,
                action=request["action"],
                operator=operator,
            )

        existing = request["approvals"].get(operator)
        if existing is not None:
            self._append(
                "conflict",
                now,
                request_id=request_id,
                vault=vault,
                action=request["action"],
                operator=operator,
                reason="duplicate_approval",
            )
            raise ValueError("duplicate approval")

        identity = self._identity(operator, record)
        for approved_operator, approval in request["approvals"].items():
            approved_record = self.operators.get(approved_operator, {})
            if (
                self._identity(approved_operator, approved_record) == identity
                or approval["credential"] == credential
            ):
                self._append(
                    "conflict",
                    now,
                    request_id=request_id,
                    vault=vault,
                    action=request["action"],
                    operator=operator,
                    reason="duplicate_key_or_identity",
                )
                raise ValueError("duplicate approval")

        approval_expires = min(now + self.APPROVAL_TTL, request["expires_at"])
        approval = {
            "request_id": request_id,
            "vault": vault,
            "action": request["action"],
            "operator": operator,
            "identity": identity,
            "credential": credential,
            "approved_at": now,
            "expires_at": approval_expires,
            "used": False,
        }
        request["approvals"][operator] = approval

        if self._is_recovery_action(request["action"]):
            self._recovery_approvals.setdefault(vault, []).append(
                {
                    "request_id": request_id,
                    "vault": vault,
                    "operator": operator,
                    "identity": identity,
                    "credential": credential,
                    "approved_at": now,
                    "expires_at": approval_expires,
                }
            )

        live = self._live_approvals(request, now)
        self._append(
            "approve",
            now,
            request_id=request_id,
            vault=vault,
            action=request["action"],
            operator=operator,
            approvals=len(live),
            remaining=max(request["threshold"] - len(live), 0),
            expires_at=approval_expires,
        )
        recovered = self._maybe_complete_recovery(vault, now)
        return {
            "ok": True,
            "request_id": request_id,
            "vault": vault,
            "action": request["action"],
            "approvals": len(live),
            "remaining": max(request["threshold"] - len(live), 0),
            "ready": len(live) >= request["threshold"],
            "expires_at": approval_expires,
            "recovered": recovered,
        }

    def unlock(self, request_id, credential, now):
        request = self.requests.get(request_id)
        if request is None:
            self._reject("unlock", "unknown_request", now=now, request_id=request_id)

        vault = request["vault"]
        state = self._vault_state[vault]
        if self._is_locked(state, now):
            self._reject(
                "unlock",
                "vault_locked",
                now=now,
                request_id=request_id,
                vault=vault,
            )
        if self._recovery_required(state, now):
            self._reject(
                "unlock",
                "recovery_required",
                now=now,
                request_id=request_id,
                vault=vault,
            )
        if self._is_recovery_action(request["action"]):
            self._reject(
                "unlock",
                "recovery_request_not_unlockable",
                now=now,
                request_id=request_id,
                vault=vault,
            )
        if request["status"] != "open":
            self._reject(
                "unlock",
                "request_not_open",
                now=now,
                request_id=request_id,
                vault=vault,
            )
        if not self._request_is_live(request, now):
            self._failed_unlock(request, state, now, "request_expired")
        if not isinstance(credential, str) or not credential:
            self._failed_unlock(request, state, now, "empty_credential")

        caller = self._operator_for_credential(credential)
        if caller is None:
            self._failed_unlock(request, state, now, "unknown_credential")
        eligibility = self._operator_problem(caller, vault, request["action"])
        if eligibility is not None:
            self._failed_unlock(request, state, now, eligibility, operator=caller)
        if caller not in request["operators"]:
            self._failed_unlock(request, state, now, "operator_not_authorized", operator=caller)

        live = self._live_approvals(request, now)
        caller_approval = live.get(caller)
        if caller_approval is None or caller_approval["credential"] != credential:
            self._failed_unlock(request, state, now, "credential_not_approved", operator=caller)
        if len(live) < request["threshold"]:
            self._failed_unlock(
                request,
                state,
                now,
                "insufficient_live_approvals",
                operator=caller,
                approvals=len(live),
            )

        for operator, approval in live.items():
            if not self._approval_is_valid(request, approval, now):
                self._failed_unlock(
                    request,
                    state,
                    now,
                    "invalid_approval",
                    operator=operator,
                )

        request["status"] = "consumed"
        request["unlocked_at"] = now
        for approval in request["approvals"].values():
            approval["used"] = True

        state["failures"] = 0
        if state["locked_until"] is not None and now >= state["locked_until"]:
            state["locked_until"] = None
            state["recovered"] = True

        self._append(
            "unlock",
            now,
            request_id=request_id,
            vault=vault,
            action=request["action"],
            operator=caller,
            approvals=list(live),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "vault": vault,
            "action": request["action"],
            "operator": caller,
            "unlocked_at": now,
            "approvals": len(live),
        }

    def deny(self, request_id, operator, now):
        request = self.requests.get(request_id)
        if request is None:
            self._reject("deny", "unknown_request", now=now, request_id=request_id, operator=operator)

        vault = request["vault"]
        state = self._vault_state[vault]
        if self._is_locked(state, now):
            self._reject(
                "deny",
                "vault_locked",
                now=now,
                request_id=request_id,
                vault=vault,
                operator=operator,
            )
        if self._recovery_required(state, now):
            self._reject(
                "deny",
                "recovery_required",
                now=now,
                request_id=request_id,
                vault=vault,
                operator=operator,
            )
        if request["status"] != "open":
            self._reject(
                "deny",
                "request_not_open",
                now=now,
                request_id=request_id,
                vault=vault,
                operator=operator,
            )
        if not isinstance(operator, str) or not operator.strip():
            self._reject(
                "deny",
                "empty_operator",
                now=now,
                request_id=request_id,
                vault=vault,
            )
        if operator not in request["operators"]:
            self._reject(
                "deny",
                "operator_not_authorized",
                now=now,
                request_id=request_id,
                vault=vault,
                action=request["action"],
                operator=operator,
            )
        self._eligible_operator(
            operator,
            vault,
            request["action"],
            now=now,
            request_id=request_id,
            operation="deny",
        )

        request["status"] = "denied"
        request["denied_at"] = now
        self._append(
            "deny",
            now,
            request_id=request_id,
            vault=vault,
            action=request["action"],
            operator=operator,
        )
        return {
            "ok": True,
            "request_id": request_id,
            "vault": vault,
            "action": request["action"],
            "status": "denied",
        }

    def lockout(self, vault, now):
        if vault not in self.vaults:
            self._reject("lockout", "unknown_vault", now=now, vault=vault)

        state = self._vault_state[vault]
        locked = self._is_locked(state, now)
        recovery_pending = (
            state["failures"] >= self.FAILURE_LIMIT and not state["recovered"]
        )
        return {
            "vault": vault,
            "locked": locked,
            "until": state["locked_until"],
            "failures": state["failures"],
            "recovery_pending": recovery_pending,
        }

    def trail(self):
        return copy.deepcopy(self._events)

    def audit(self):
        return self.trail()

    def _threshold(self, vault, action=None):
        if self._is_recovery_action(action):
            return 1
        configured = self.vaults[vault].get("threshold", self.MIN_THRESHOLD)
        if not isinstance(configured, int) or isinstance(configured, bool):
            return self.MIN_THRESHOLD
        return max(configured, self.MIN_THRESHOLD)

    def _eligible_operator(
        self,
        name,
        vault,
        action,
        now=None,
        request_id=None,
        operation="operator",
    ):
        record = self.operators.get(name)
        reason = self._operator_problem(name, vault, action)
        if reason is not None:
            self._reject(
                operation,
                reason,
                now=now,
                vault=vault,
                action=action,
                operator=name,
                request_id=request_id,
            )
        return record

    def _operator_problem(self, name, vault, action):
        record = self.operators.get(name)
        if not isinstance(name, str) or not name.strip() or record is None:
            return "unknown_or_empty_operator"
        if record.get("revoked"):
            return "operator_revoked"
        credential = record.get("credential")
        if not isinstance(credential, str) or not credential:
            return "invalid_credential"
        if vault not in record.get("vaults", []):
            return "vault_not_permitted"
        if action not in record.get("actions", []):
            return "action_not_permitted"
        return None

    def _operator_for_credential(self, credential):
        matches = [
            name
            for name, record in self.operators.items()
            if record.get("credential") == credential
        ]
        if len(matches) != 1:
            return None
        return matches[0]

    def _identity(self, name, record):
        for key in ("person", "identity", "owner", "principal", "subject", "user"):
            value = record.get(key)
            if value is not None:
                return value
        return name

    def _request_is_live(self, request, now):
        return request["created_at"] <= now < request["expires_at"]

    def _approval_is_valid(self, request, approval, now):
        if approval["request_id"] != request["request_id"]:
            return False
        if approval["vault"] != request["vault"]:
            return False
        if approval["action"] != request["action"]:
            return False
        if approval["approved_at"] > now:
            return False
        if now >= approval["expires_at"]:
            return False
        if approval["used"]:
            return False

        operator = approval["operator"]
        record = self.operators.get(operator)
        if record is None or record.get("revoked"):
            return False
        if record.get("credential") != approval["credential"]:
            return False
        if request["vault"] not in record.get("vaults", []):
            return False
        if request["action"] not in record.get("actions", []):
            return False
        return True

    def _live_approvals(self, request, now):
        return {
            operator: approval
            for operator, approval in request["approvals"].items()
            if self._approval_is_valid(request, approval, now)
        }

    def _is_locked(self, state, now):
        return state["locked_until"] is not None and now < state["locked_until"]

    def _recovery_required(self, state, now):
        return (
            state["locked_until"] is not None
            and now >= state["locked_until"]
            and state["failures"] >= self.FAILURE_LIMIT
            and not state["recovered"]
        )

    def _failed_unlock(self, request, state, now, reason, **fields):
        self._append(
            "reject",
            now,
            operation="unlock",
            reason=reason,
            request_id=request["request_id"],
            vault=request["vault"],
            action=request["action"],
            **fields,
        )
        state["failures"] += 1
        if state["failures"] >= self.FAILURE_LIMIT:
            state["locked_until"] = now + self.LOCK_SECONDS
            state["recovered"] = False
            self._append(
                "lockout",
                now,
                vault=request["vault"],
                until=state["locked_until"],
                failures=state["failures"],
            )
        raise ValueError(reason)

    def _maybe_complete_recovery(self, vault, now):
        state = self._vault_state[vault]
        if (
            self._is_locked(state, now)
            or state["failures"] < self.FAILURE_LIMIT
            or state["recovered"]
        ):
            return False

        recovery = self._valid_recovery_approvals(vault, now)
        identities = {item["identity"] for item in recovery}
        request_ids = {item["request_id"] for item in recovery}
        if len(identities) < 2 or len(request_ids) < 2:
            return False

        state["failures"] = 0
        state["locked_until"] = None
        state["recovered"] = True
        for item in recovery:
            request = self.requests[item["request_id"]]
            request["status"] = "consumed"
            request["approvals"][item["operator"]]["used"] = True
        self._append(
            "recover",
            now,
            vault=vault,
            operators=[item["operator"] for item in recovery],
            request_ids=sorted(request_ids),
        )
        return True

    def _valid_recovery_approvals(self, vault, now):
        records = self._recovery_approvals.get(vault, [])
        valid = []
        for item in records:
            if item["approved_at"] > now or now >= item["expires_at"]:
                continue
            operator = item["operator"]
            record = self.operators.get(operator)
            if record is None or record.get("revoked"):
                continue
            if record.get("credential") != item["credential"]:
                continue
            request = self.requests.get(item["request_id"])
            if request is None or request["vault"] != vault:
                continue
            if request["status"] != "open":
                continue
            if not self._is_recovery_action(request["action"]):
                continue
            valid.append(item)
        return valid

    def _is_recovery_action(self, action):
        if not isinstance(action, str):
            return False
        return action.strip().lower() in self.RECOVERY_ACTIONS

    def _append(self, event_type, now, **fields):
        self._sequence += 1
        event = {"seq": self._sequence, "type": event_type, "at": now}
        event.update(fields)
        self._events.append(event)
        return copy.deepcopy(event)

    def _reject(self, operation, reason, now=None, **fields):
        self._append("reject", now, operation=operation, reason=reason, **fields)
        raise ValueError(reason)

    def _public_request(self, request):
        return {key: copy.deepcopy(value) for key, value in request.items()}
