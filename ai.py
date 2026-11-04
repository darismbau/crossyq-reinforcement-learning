"""Pilote autonome à règles simples, fondé sur l'état réel du jeu."""

from settings import COL_MAX, HOP_T, WRAP
from utils import pd


class CrossyAI:
    """Choisit des déplacements sûrs et privilégie la progression vers l'avant."""

    def choose_action(self, game):
        player = game.p
        if player.hop is not None:
            return None

        actions = ((0, 1), (-1, 0), (1, 0), (0, -1))
        choices = []
        for dx, dy in actions:
            target = self._target(game, dx, dy)
            if target is None:
                continue
            x, y, row = target
            if not self._valid_landing(game, row, x, HOP_T):
                continue

            safe, clearance = self._path_is_safe(game, x, y, HOP_T)
            if not safe:
                continue

            progress = dy * 100
            safety = min(clearance, 2.0) * 3 if clearance != float("inf") else 0
            coins = 0.2 if round(x) in row.coins else 0
            center = -abs(x) * 0.15
            choices.append((progress + safety + coins + center, (dx, dy)))

        return max(choices, default=(0, None))[1]

    def _target(self, game, dx, dy):
        player = game.p
        y = round(player.y + dy)
        row = game.world.rows.get(y)
        if row is None:
            return None

        if dy:
            x = player.x if row.kind == "river" else float(round(player.x))
        else:
            x = player.x + dx
            ride = player.ride
            if row.kind == "river":
                if ride is None or ride["row"] is not row:
                    return None
                offset = ride["off"] + dx
                length = row.logs[ride["idx"]][1]
                if abs(offset) > (length - 1) / 2 + 1e-6:
                    return None
                x = self._log_center(row, ride["idx"], ride["k"], HOP_T) + offset

        if abs(x) > COL_MAX + 0.5:
            return None
        return x, y, row

    def _valid_landing(self, game, row, x, elapsed):
        column = round(x)
        if row.kind == "grass":
            return column not in row.trees
        if row.kind == "pads":
            return column in row.pads
        if row.kind == "river":
            shift = row.shift + row.dir * row.speed * elapsed
            return any(
                abs(pd(x, shift + center)) <= length / 2 + 0.1
                for center, length in row.logs
            )
        return True

    def _path_is_safe(self, game, target_x, target_y, duration):
        player = game.p
        clearance = float("inf")
        for sample in range(1, 9):
            fraction = sample / 8
            elapsed = duration * fraction
            x = player.x + (target_x - player.x) * fraction
            y = player.y + (target_y - player.y) * fraction
            row = game.world.rows.get(round(y))
            if row is None:
                continue

            if row.kind == "road":
                margin = self._road_clearance(row, x, elapsed)
                clearance = min(clearance, margin)
                if margin <= 0.12:
                    return False, clearance
            elif row.kind == "rail":
                margin = self._rail_clearance(row, x, elapsed)
                clearance = min(clearance, margin)
                if margin <= 0.12:
                    return False, clearance

        return True, clearance

    @staticmethod
    def _road_clearance(row, x, elapsed):
        shift = row.shift + row.dir * row.speed * elapsed
        nearest = float("inf")
        for vehicle in row.items:
            if vehicle.get("gone"):
                continue
            center = shift + vehicle["off"]
            nearest = min(nearest, abs(pd(x, center)) - vehicle["len"] / 2 - 0.3)
        for cop in row.cops:
            center = cop["x"] + row.dir * cop["spd"] * elapsed
            nearest = min(nearest, abs(pd(x, center)) - 1.05)
        return nearest

    @staticmethod
    def _rail_clearance(row, x, elapsed):
        if row.state == "pass":
            train_time = elapsed
        elif row.state == "warn" and elapsed >= row.timer:
            train_time = elapsed - row.timer
        elif row.state == "idle" and elapsed >= row.timer + row.warn:
            train_time = elapsed - row.timer - row.warn
        else:
            return float("inf")

        front = (-34.0 if row.dir > 0 else 34.0) + row.dir * 30 * train_time
        back = front - row.dir * 16
        low, high = min(front, back), max(front, back)
        low -= 0.3
        high += 0.3
        if low <= x <= high:
            return -0.3
        return low - x if x < low else x - high

    @staticmethod
    def _log_center(row, index, copy, elapsed):
        return row.shift + row.logs[index][0] + copy * WRAP + row.dir * row.speed * elapsed
