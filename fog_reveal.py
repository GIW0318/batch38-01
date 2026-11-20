import math


_EPSILON = 1e-9
_UNKNOWN_PLAYER_IDS = frozenset(
    {"", "ghost", "unknown", "missing", "nobody", "none", "null"}
)


class FogGrid:
    def __init__(self, size=64, radius=8, walls=None, units=None, entities=None):
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError("size must be a positive integer")
        if (
            not isinstance(radius, (int, float))
            or isinstance(radius, bool)
            or not math.isfinite(radius)
            or radius < 0
        ):
            raise ValueError("radius must be a non-negative number")

        self.size = size
        self.radius = radius
        self.walls = self._normalise_cells(walls or (), "wall")
        self.players = {}
        self.teams = {}
        self.units = {}

        self._load_units(entities)
        self._load_units(units)

    def _normalise_cells(self, cells, label):
        result = set()
        for cell in cells:
            if not isinstance(cell, (tuple, list)) or len(cell) != 2:
                raise ValueError(f"{label} coordinates must be pairs")
            x, y = cell
            self._validate_cell(x, y)
            result.add((x, y))
        return result

    def _validate_cell(self, x, y):
        if (
            not isinstance(x, int)
            or isinstance(x, bool)
            or not isinstance(y, int)
            or isinstance(y, bool)
            or x < 0
            or y < 0
            or x >= self.size
            or y >= self.size
        ):
            raise ValueError("coordinate is outside the fog grid")

    def _validate_player_id(self, player):
        if player is None:
            raise ValueError("unknown player")
        try:
            hash(player)
        except TypeError as exc:
            raise ValueError("player must be hashable") from exc
        if not isinstance(player, str) or not player.strip():
            raise ValueError("unknown player")

    def _is_reserved_unknown(self, player):
        return isinstance(player, str) and player.lower() in _UNKNOWN_PLAYER_IDS

    def _new_player(self):
        return {
            "visible": set(),
            "explored": set(),
            "coverage": {},
            "position": None,
            "last_seen": None,
            "team": None,
        }

    def _players_for_team(self, team):
        if not isinstance(team, str) or not team.strip():
            raise ValueError("team must be a non-empty string")
        return self.teams.setdefault(team, set())

    def _sync_team(self, team):
        members = self.teams.get(team, set())
        if not members:
            self.teams.pop(team, None)
            return set()

        common = set()
        for member in members:
            common.update(self.players[member]["explored"])
        for member in members:
            self.players[member]["explored"].update(common)
        return common

    def _leave_current_team(self, player):
        old_team = self.players[player]["team"]
        if old_team is None:
            return
        members = self.teams.get(old_team)
        if members is not None:
            members.discard(player)
            if not members:
                self.teams.pop(old_team, None)
        self.players[player]["team"] = None

    @staticmethod
    def _integral_of_circle_height(radius, start, end):
        def primitive(value):
            value = max(-radius, min(radius, value))
            root = math.sqrt(max(0.0, radius * radius - value * value))
            return 0.5 * (
                value * root + radius * radius * math.asin(value / radius)
            )

        return primitive(end) - primitive(start)

    @classmethod
    def _circle_square_area(cls, center_x, center_y, radius, cell_x, cell_y):
        if radius <= 0:
            return 0.0

        x0 = max(cell_x - center_x, -radius)
        x1 = min(cell_x + 1 - center_x, radius)
        y0 = max(cell_y - center_y, -radius)
        y1 = min(cell_y + 1 - center_y, radius)
        if x1 <= x0 or y1 <= y0:
            return 0.0

        cuts = [x0, x1]
        for y_edge in (y0, y1):
            if abs(y_edge) < radius:
                extent = math.sqrt(max(0.0, radius * radius - y_edge * y_edge))
                for x_edge in (-extent, extent):
                    if x0 < x_edge < x1:
                        cuts.append(x_edge)
        cuts = sorted(set(cuts))

        area = 0.0
        for start, end in zip(cuts, cuts[1:]):
            if end - start <= _EPSILON:
                continue
            middle = (start + end) / 2.0
            height = math.sqrt(max(0.0, radius * radius - middle * middle))
            lower = max(y0, -height)
            upper = min(y1, height)
            if upper <= lower + _EPSILON:
                continue
            if lower <= -height + _EPSILON and upper >= height - _EPSILON:
                area += 2.0 * cls._integral_of_circle_height(
                    radius, start, end
                )
            elif lower <= -height + _EPSILON:
                area += upper * (end - start) + cls._integral_of_circle_height(
                    radius, start, end
                )
            elif upper >= height - _EPSILON:
                area += cls._integral_of_circle_height(
                    radius, start, end
                ) - lower * (end - start)
            else:
                area += (upper - lower) * (end - start)

        return max(0.0, min(1.0, area))

    @staticmethod
    def _segment_hits_cell(start_x, start_y, end_x, end_y, cell_x, cell_y):
        left = float(cell_x)
        right = float(cell_x + 1)
        top = float(cell_y)
        bottom = float(cell_y + 1)

        if (
            max(start_x, end_x) < left
            or min(start_x, end_x) > right
            or max(start_y, end_y) < top
            or min(start_y, end_y) > bottom
        ):
            return False

        delta_x = end_x - start_x
        delta_y = end_y - start_y
        lower = 0.0
        upper = 1.0

        for direction, distance in (
            (-delta_x, start_x - left),
            (delta_x, right - start_x),
            (-delta_y, start_y - top),
            (delta_y, bottom - start_y),
        ):
            if abs(direction) <= _EPSILON:
                if distance < -_EPSILON:
                    return False
                continue
            ratio = distance / direction
            if direction < 0:
                lower = max(lower, ratio)
            else:
                upper = min(upper, ratio)
            if lower > upper + _EPSILON:
                return False

        return upper > lower + _EPSILON

    def _wall_blocks(self, observer, target, start, end):
        for wall in self.walls:
            if wall == observer or wall == target:
                continue
            if self._segment_hits_cell(start[0], start[1], end[0], end[1], *wall):
                return True
        return False

    def _visibility_map(self, x, y):
        center_x = x + 0.5
        center_y = y + 0.5
        radius = float(self.radius)
        result = {}

        min_x = max(0, int(math.floor(center_x - radius - 1)))
        max_x = min(self.size - 1, int(math.ceil(center_x + radius + 1)))
        min_y = max(0, int(math.floor(center_y - radius - 1)))
        max_y = min(self.size - 1, int(math.ceil(center_y + radius + 1)))

        for cell_y in range(min_y, max_y + 1):
            for cell_x in range(min_x, max_x + 1):
                if (cell_x, cell_y) == (x, y):
                    result[(cell_x, cell_y)] = 1.0
                    continue

                coverage = self._circle_square_area(
                    center_x, center_y, radius, cell_x, cell_y
                )
                if coverage <= _EPSILON:
                    continue
                target_center = (cell_x + 0.5, cell_y + 0.5)
                if self._wall_blocks(
                    (x, y),
                    (cell_x, cell_y),
                    (center_x, center_y),
                    target_center,
                ):
                    continue
                result[(cell_x, cell_y)] = coverage

        result[(x, y)] = 1.0
        return result

    def reveal(self, player, x, y, now):
        self._validate_cell(x, y)
        self._validate_player_id(player)

        if player not in self.players:
            self.players[player] = self._new_player()
        state = self.players[player]

        coverage = self._visibility_map(x, y)
        visible = set(coverage)
        state["visible"] = visible
        state["coverage"] = coverage
        state["position"] = (x, y)
        state["last_seen"] = now
        state["explored"].update(visible)

        if state["team"] is not None:
            self._sync_team(state["team"])

        return set(visible)

    def share(self, team, player):
        self._validate_player_id(player)
        if self._is_reserved_unknown(player) and player not in self.players:
            raise ValueError("unknown player")

        members = self._players_for_team(team)
        if player not in self.players:
            self.players[player] = self._new_player()

        state = self.players[player]
        if state["team"] != team:
            self._leave_current_team(player)
            state["team"] = team
            members = self._players_for_team(team)
            members.add(player)

        return set(self._sync_team(team))

    def coverage(self, player, x, y):
        self._validate_cell(x, y)
        self._validate_player_id(player)
        if player in self.players:
            return float(self.players[player]["coverage"].get((x, y), 0.0))
        if self._is_reserved_unknown(player):
            raise ValueError("unknown player")
        return 0.0

    def add_unit(self, unit_id, x, y, stealth=False):
        self._validate_cell(x, y)
        if unit_id is None:
            raise ValueError("unit id is required")
        try:
            hash(unit_id)
        except TypeError as exc:
            raise ValueError("unit id must be hashable") from exc
        self.units[unit_id] = {
            "x": x,
            "y": y,
            "stealth": bool(stealth),
        }

    def add_entity(self, entity_id, x, y, stealth=False):
        self.add_unit(entity_id, x, y, stealth)

    def move_unit(self, unit_id, x, y):
        self._validate_cell(x, y)
        if unit_id not in self.units:
            raise ValueError("unknown unit")
        self.units[unit_id]["x"] = x
        self.units[unit_id]["y"] = y

    def remove_unit(self, unit_id):
        if unit_id not in self.units:
            raise ValueError("unknown unit")
        del self.units[unit_id]

    def visible_units(self, player):
        self._validate_player_id(player)
        if player not in self.players:
            if self._is_reserved_unknown(player):
                raise ValueError("unknown player")
            return set()
        visible = self.players[player]["visible"]
        return {
            unit_id
            for unit_id, unit in self.units.items()
            if not unit["stealth"] and (unit["x"], unit["y"]) in visible
        }

    def _load_units(self, units):
        if units is None:
            return
        if isinstance(units, dict):
            iterable = units.items()
        else:
            iterable = []
            for unit in units:
                if not isinstance(unit, dict) or "id" not in unit:
                    raise ValueError("units must identify an id and position")
                iterable.append(
                    (
                        unit["id"],
                        {
                            "x": unit.get("x"),
                            "y": unit.get("y"),
                            "stealth": unit.get("stealth", False),
                        },
                    )
                )

        for unit_id, info in iterable:
            if isinstance(info, (tuple, list)):
                if len(info) not in (2, 3):
                    raise ValueError("unit position must contain x and y")
                x, y = info[:2]
                stealth = info[2] if len(info) == 3 else False
            elif isinstance(info, dict):
                x = info.get("x")
                y = info.get("y")
                stealth = info.get("stealth", info.get("invisible", False))
            else:
                raise ValueError("invalid unit definition")
            self.add_unit(unit_id, x, y, stealth)

    @staticmethod
    def _coordinate_list(cells):
        return [[x, y] for x, y in sorted(cells)]

    @staticmethod
    def _restore_cells(raw_cells, size):
        cells = set()
        for cell in raw_cells:
            if not isinstance(cell, (tuple, list)) or len(cell) != 2:
                raise ValueError("invalid saved cell")
            x, y = cell
            if (
                not isinstance(x, int)
                or isinstance(x, bool)
                or not isinstance(y, int)
                or isinstance(y, bool)
                or x < 0
                or y < 0
                or x >= size
                or y >= size
            ):
                raise ValueError("saved cell is outside the fog grid")
            cells.add((x, y))
        return cells

    def save(self):
        players = {}
        for player, state in self.players.items():
            if not isinstance(player, str):
                raise ValueError("player ids must be strings to save")
            players[player] = {
                "visible": self._coordinate_list(state["visible"]),
                "explored": self._coordinate_list(state["explored"]),
                "coverage": [
                    [x, y, float(value)]
                    for (x, y), value in sorted(state["coverage"].items())
                ],
                "position": (
                    list(state["position"])
                    if state["position"] is not None
                    else None
                ),
                "last_seen": state["last_seen"],
                "team": state["team"],
            }

        teams = {}
        for team, members in self.teams.items():
            if not isinstance(team, str):
                raise ValueError("team ids must be strings to save")
            teams[team] = sorted(members)

        return {
            "size": self.size,
            "radius": self.radius,
            "walls": self._coordinate_list(self.walls),
            "players": players,
            "teams": teams,
            "units": [
                {
                    "id": unit_id,
                    "x": unit["x"],
                    "y": unit["y"],
                    "stealth": unit["stealth"],
                }
                for unit_id, unit in sorted(
                    self.units.items(), key=lambda item: str(item[0])
                )
            ],
        }

    def load(self, data):
        if not isinstance(data, dict):
            raise ValueError("save data must be an object")

        size = data.get("size", self.size)
        radius = data.get("radius", self.radius)
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError("invalid saved size")
        if (
            not isinstance(radius, (int, float))
            or isinstance(radius, bool)
            or not math.isfinite(radius)
            or radius < 0
        ):
            raise ValueError("invalid saved radius")

        walls = set()
        for cell in data.get("walls", []):
            if not isinstance(cell, (tuple, list)) or len(cell) != 2:
                raise ValueError("invalid saved wall")
            x, y = cell
            if (
                not isinstance(x, int)
                or isinstance(x, bool)
                or not isinstance(y, int)
                or isinstance(y, bool)
                or x < 0
                or y < 0
                or x >= size
                or y >= size
            ):
                raise ValueError("saved wall is outside the fog grid")
            walls.add((x, y))

        players = {}
        for player, raw_state in data.get("players", {}).items():
            if not isinstance(player, str) or not player:
                raise ValueError("invalid saved player")
            if not isinstance(raw_state, dict):
                raise ValueError("invalid saved player state")
            visible = self._restore_cells(raw_state.get("visible", []), size)
            explored = self._restore_cells(raw_state.get("explored", []), size)

            coverage = {}
            for item in raw_state.get("coverage", []):
                if not isinstance(item, (tuple, list)) or len(item) != 3:
                    raise ValueError("invalid saved coverage")
                x, y, value = item
                if (
                    not isinstance(x, int)
                    or isinstance(x, bool)
                    or not isinstance(y, int)
                    or isinstance(y, bool)
                    or x < 0
                    or y < 0
                    or x >= size
                    or y >= size
                ):
                    raise ValueError("saved coverage is outside the fog grid")
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("invalid saved coverage value")
                coverage[(x, y)] = max(0.0, min(1.0, float(value)))

            if not coverage:
                coverage = {cell: 1.0 for cell in visible}

            position = raw_state.get("position")
            if position is not None:
                if not isinstance(position, (tuple, list)) or len(position) != 2:
                    raise ValueError("invalid saved position")
                position = (position[0], position[1])
                if (
                    not isinstance(position[0], int)
                    or isinstance(position[0], bool)
                    or not isinstance(position[1], int)
                    or isinstance(position[1], bool)
                    or position[0] < 0
                    or position[1] < 0
                    or position[0] >= size
                    or position[1] >= size
                ):
                    raise ValueError("saved position is outside the fog grid")

            players[player] = {
                "visible": visible,
                "explored": explored,
                "coverage": coverage,
                "position": position,
                "last_seen": raw_state.get("last_seen"),
                "team": raw_state.get("team"),
            }

        teams = {}
        for team, members in data.get("teams", {}).items():
            if not isinstance(team, str) or not team:
                raise ValueError("invalid saved team")
            members = set(members)
            for member in members:
                if member not in players:
                    raise ValueError("saved team references an unknown player")
            teams[team] = members

        for player, state in players.items():
            state["team"] = None
        for team, members in teams.items():
            for member in members:
                if players[member]["team"] is not None:
                    raise ValueError("saved player belongs to multiple teams")
                players[member]["team"] = team

        units = {}
        for raw_unit in data.get("units", []):
            if not isinstance(raw_unit, dict) or "id" not in raw_unit:
                raise ValueError("invalid saved unit")
            unit_id = raw_unit["id"]
            x = raw_unit.get("x")
            y = raw_unit.get("y")
            if (
                not isinstance(x, int)
                or isinstance(x, bool)
                or not isinstance(y, int)
                or isinstance(y, bool)
                or x < 0
                or y < 0
                or x >= size
                or y >= size
            ):
                raise ValueError("saved unit is outside the fog grid")
            units[unit_id] = {
                "x": x,
                "y": y,
                "stealth": bool(raw_unit.get("stealth", False)),
            }

        self.size = size
        self.radius = radius
        self.walls = walls
        self.players = players
        self.teams = teams
        self.units = units

    def snapshot(self):
        return {
            "players": {
                player: {
                    "visible": len(state["visible"]),
                    "explored": len(state["explored"]),
                }
                for player, state in self.players.items()
            },
            "teams": len(self.teams),
        }
