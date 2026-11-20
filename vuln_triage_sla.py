class VulnTriage:
    def __init__(self, holidays=None):
        self.holidays = set(holidays or [])

    def ingest(self, findings, now):
        return None

    def assign(self, vuln_id, owner, now):
        return None

    def request_exception(self, vuln_id, until, approver, now):
        return None

    def approve_exception(self, vuln_id, approver, now):
        return None

    def close(self, vuln_id, now, reason):
        return None

    def sla(self, vuln_id, now):
        return {}

    def queue(self):
        return {}
