class BuffLedger:
    def __init__(self, groups):
        self.groups = groups

    def place(self, group, buffs):
        return None

    def refresh(self, now):
        return None

    def remove(self, group, buff_id):
        return None

    def recompute(self, now):
        return None

    def coverage(self, now):
        return {}
