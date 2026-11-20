class RequestBudget:
    def __init__(self, max_per_ip=8, max_total=100):
        self.max_per_ip = max_per_ip
        self.max_total = max_total

    def open(self, conn, ip, ts):
        return None

    def recv_headers(self, conn, size, ts):
        return None

    def recv_body(self, conn, size, ts):
        return None

    def finish(self, conn, ts):
        return None

    def profile(self):
        return {}
