class ScheduleBoard:
    def __init__(self):
        pass

    def assign_week(self, npc, week_plan):
        return None

    def override(self, npc, window, activity, priority, now):
        return None

    def status(self, npc, t):
        return {}

    def interrupt(self, npc, reason, t):
        return {}

    def resume(self, npc, t):
        return {}

    def export(self):
        return {}
