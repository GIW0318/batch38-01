class GpuBudget:
    def __init__(self, limit=1024 * 1024):
        self.limit = limit

    def alloc(self, size, kind="buffer", tag=""):
        return None

    def free(self, handle):
        return None

    def pin(self, handle):
        return None

    def unpin(self, handle):
        return None

    def defrag(self, now):
        return None

    def usage(self):
        return {}
