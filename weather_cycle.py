class WeatherEngine:
    def __init__(self, world_seed, biome, temp_base=10.0):
        self.world_seed = world_seed
        self.biome = biome
        self.temp_base = temp_base

    def advance(self, now):
        return None

    def at(self, t):
        return {}

    def forecast(self, t, horizon):
        return []

    def warning(self, t):
        return None

    def history(self, start, end):
        return []
