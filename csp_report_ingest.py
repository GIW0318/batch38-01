class CspReportSink:
    def __init__(self, sample_rate=1.0, per_host_limit=100):
        self.sample_rate = sample_rate
        self.per_host_limit = per_host_limit

    def ingest(self, reports, now):
        return None

    def summary(self, top=5):
        return []

    def violations(self):
        return {}
