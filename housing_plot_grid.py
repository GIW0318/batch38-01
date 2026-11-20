class PlotGrid:
    INITIAL_SIZE = 8
    MAX_SIZE = 16
    EXPAND_STEP = 4
    MAX_ITEMS = 50
    VALID_ROTATIONS = (0, 90, 180, 270)
    EXPAND_DIRECTIONS = ("east", "south")
    _DOOR_VECTORS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}

    def __init__(self):
        self._plots = {}

    def _get_plot(self, plot):
        if plot not in self._plots:
            raise ValueError(f"unknown plot: {plot}")
        return self._plots[plot]

    def _ensure_plot(self, plot):
        return self._plots.setdefault(
            plot,
            {"width": self.INITIAL_SIZE, "height": self.INITIAL_SIZE, "items": []},
        )

    @staticmethod
    def _overlaps(a, b):
        return (
            a["x"] < b["x"] + b["w"]
            and b["x"] < a["x"] + a["w"]
            and a["y"] < b["y"] + b["h"]
            and b["y"] < a["y"] + a["h"]
        )

    def _check_bounds(self, state, rect):
        if (
            rect["x"] < 0
            or rect["y"] < 0
            or rect["x"] + rect["w"] > state["width"]
            or rect["y"] + rect["h"] > state["height"]
        ):
            raise ValueError("item out of plot bounds")

    def _check_overlap(self, state, rect, exclude_id=None):
        for other in state["items"]:
            if other["id"] == exclude_id:
                continue
            if self._overlaps(rect, other):
                raise ValueError(f"item overlaps with {other['id']}")

    def _check_door(self, state, rect, exclude_id=None):
        door = rect["door"]
        if door not in self._DOOR_VECTORS:
            raise ValueError(f"invalid door direction: {door}")
        dx, dy = self._DOOR_VECTORS[door]
        if dy:
            edge_y = rect["y"] - 1 if dy < 0 else rect["y"] + rect["h"]
            cells = [(rect["x"] + i, edge_y) for i in range(rect["w"])]
        else:
            edge_x = rect["x"] - 1 if dx < 0 else rect["x"] + rect["w"]
            cells = [(edge_x, rect["y"] + i) for i in range(rect["h"])]
        for cx, cy in cells:
            for other in state["items"]:
                if other["id"] == exclude_id:
                    continue
                if (
                    other["x"] <= cx < other["x"] + other["w"]
                    and other["y"] <= cy < other["y"] + other["h"]
                ):
                    raise ValueError("door must face an empty cell")

    def place(self, plot, item, x, y, rot):
        if rot not in self.VALID_ROTATIONS:
            raise ValueError(f"invalid rotation: {rot}")
        state = self._ensure_plot(plot)
        if len(state["items"]) >= self.MAX_ITEMS:
            raise ValueError("plot item capacity reached")
        if any(existing["id"] == item["id"] for existing in state["items"]):
            raise ValueError(f"duplicate item id: {item['id']}")
        w, h = item["w"], item["h"]
        if w < 1 or h < 1:
            raise ValueError("item dimensions must be positive")
        if rot in (90, 270):
            w, h = h, w
        rect = {"id": item["id"], "x": x, "y": y, "w": w, "h": h, "door": item["door"]}
        self._check_bounds(state, rect)
        self._check_overlap(state, rect)
        self._check_door(state, rect)
        state["items"].append(rect)

    def move(self, plot, item, x, y):
        state = self._get_plot(plot)
        rect = next((i for i in state["items"] if i["id"] == item), None)
        if rect is None:
            raise ValueError(f"unknown item: {item}")
        candidate = dict(rect, x=x, y=y)
        self._check_bounds(state, candidate)
        self._check_overlap(state, candidate, exclude_id=rect["id"])
        self._check_door(state, candidate, exclude_id=rect["id"])
        rect["x"] = x
        rect["y"] = y

    def remove(self, plot, item):
        state = self._get_plot(plot)
        for index, rect in enumerate(state["items"]):
            if rect["id"] == item:
                del state["items"][index]
                return
        raise ValueError(f"unknown item: {item}")

    def expand(self, plot, direction):
        if direction not in self.EXPAND_DIRECTIONS:
            raise ValueError(f"invalid expand direction: {direction}")
        state = self._ensure_plot(plot)
        key = "width" if direction == "east" else "height"
        state[key] = min(self.MAX_SIZE, state[key] + self.EXPAND_STEP)

    def plot_view(self, plot):
        state = self._get_plot(plot)
        return {
            "width": state["width"],
            "height": state["height"],
            "occupied": sum(i["w"] * i["h"] for i in state["items"]),
            "items": [dict(i) for i in state["items"]],
        }
