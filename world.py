"""Le monde : les rangées (herbe, route, rivière, rails, nénuphars) et leur génération."""
import random

from settings import (COL_MAX, WRAP, ZT, LOG_H, CAR_COLORS, TRAILERS,
                      GRASS_C, ROAD_C, RAIL_C, LOG_C, PAD_C, LOG1_CHANCE_START, LOG1_CHANCE_END,
                      SMALL_LANE_START, SMALL_LANE_END, SMALL_SPEED_MUL, SMALL_SPEED_MAX,
                      ROAD_RUN_MIN, ROAD_RUN_MAX_HARD, REST_START, REST_PEAK, REST_GAP, REST_LEN,
                      TREE_CENTER_FACTOR, LOG_SPEED, CUT_LOG_START, CUT_LOG_END)
from utils import difficulty


def ground_z(row):
    """Hauteur sur laquelle se tient le joueur pour une rangée donnée."""
    if row is None:
        return 0
    if row.kind == "river":
        return ZT["river"] + LOG_H
    if row.kind == "pads":
        return ZT["pads"] + 2
    return ZT[row.kind]


def ground_color(row):
    k = row.kind
    if k == "grass":
        return GRASS_C[row.y % 2]
    if k == "road":
        return ROAD_C[row.y % 2]
    if k == "rail":
        return RAIL_C
    if k == "river":
        return LOG_C
    return PAD_C


class Row:
    def __init__(self, y, kind, seed, direction):
        self.y = y
        self.kind = kind
        self.seed = seed
        self.dir = direction
        self.speed = 0.0
        self.shift = 0.0
        self.trees = {}
        self.coins = set()
        self.pads = set()
        self.items = []     # véhicules
        self.logs = []      # (centre, longueur)
        self.state = "idle"
        self.timer = 0.0
        self.front = 0.0
        self.cops = []             # voitures de police en cours de passage
        self.cop_state = None      # None | clearing | active | restoring
        self.dips = {}             # bûche -> instant où le joueur a atterri dessus
        self.idle = (2.0, 5.0)     # pause entre deux trains (s)
        self.warn = 1.4            # durée de l'avertissement (s)

    def train_extent(self):
        a = self.front
        b = self.front - self.dir * 16
        return min(a, b), max(a, b)

    def update(self, dt, rng):
        if self.kind in ("road", "river"):
            self.shift += self.dir * self.speed * dt
            if self.cops:
                for c in self.cops:
                    c["x"] += self.dir * c["spd"] * dt
                self.cops = [c for c in self.cops if abs(c["x"]) < 26]
        elif self.kind == "rail":
            self.timer -= dt
            if self.state == "idle" and self.timer <= 0:
                self.state, self.timer = "warn", self.warn
            elif self.state == "warn" and self.timer <= 0:
                self.state = "pass"
                self.front = -34.0 if self.dir > 0 else 34.0
            elif self.state == "pass":
                self.front += self.dir * 30 * dt
                if (self.dir > 0 and self.front > 42) or (self.dir < 0 and self.front < -42):
                    self.state, self.timer = "idle", rng.uniform(*self.idle)


class World:
    # poids des types de rangée pour les sections "chaos" (mélange libre, rangée par rangée)
    EASY = {"grass": 3.0, "road": 4.0, "river": 1.0, "rail": 1.0, "pads": 0.5}
    HARD = {"grass": 1.1, "road": 4.6, "river": 3.4, "rail": 1.9, "pads": 1.6}
    LIMITS = {"grass": 2, "road": 4, "river": 3, "rail": 1, "pads": 3}
    # poids des SECTIONS (blocs de plusieurs rangées d'un même thème) : début -> difficulté maximale
    #   meadow = 1-2 rangées d'herbe | road = 4 à 8 routes | river = groupe de bûches | lilies = groupe de nénuphars
    #   mixed = eau mélangée | rail = voie ferrée | crossing = rail + 2-3 routes + rail | chaos = mélange libre
    SECTION_EASY = dict(meadow=4.0, road=1.5, chaos=3.2, river=0.5, lilies=0.35, rail=0.7, crossing=0.0, mixed=0.0)
    SECTION_HARD = dict(meadow=1.2, road=3.6, chaos=2.0, river=3.6, lilies=1.9, rail=1.5, crossing=1.3, mixed=2.1)

    def __init__(self):
        self.rng = random.Random()
        self.rows = {}
        self.last, self.run = "grass", 0
        self.plan = ["grass"]                 # rangées déjà planifiées ("rest" = herbe de repos) ; départ en douceur
        self.last_section, self.last_rest = "start", 0
        self.reach = set(range(-COL_MAX, COL_MAX + 1))   # colonnes atteignables sur la dernière rangée
        self.reach_groups = [set(self.reach)]            # ... réparties en groupes de cases qui communiquent sur les côtés
        for y in range(-16, 2):
            self.rows[y] = self.make(y, "grass", start=True)
        self.top = 2

    # ---- planification par sections ----
    def pick(self, last, run):
        """Type d'une rangée "chaos" (pondéré par la difficulté, avec limite de répétition)."""
        r = self.rng
        d = difficulty(self.top)
        kinds = list(self.EASY)
        weights = [self.EASY[k] + (self.HARD[k] - self.EASY[k]) * d for k in kinds]
        while True:
            k = r.choices(kinds, weights)[0]
            if k == last and run >= self.LIMITS[k]:
                continue
            return k

    def plan_section(self):
        """Prépare le prochain bloc de rangées (self.plan)."""
        r, y = self.rng, self.top
        d = difficulty(y)
        # zone de repos : 4-5 rangées d'herbe, de temps en temps (surtout autour de la rangée 100)
        if y >= REST_START and y - self.last_rest >= REST_GAP and self.last_section not in ("meadow", "rest"):
            t = min(1.0, (y - REST_START) / max(1, REST_PEAK - REST_START))
            p = 0.12 + 0.33 * t if y <= REST_PEAK + 60 else 0.16
            if r.random() < p:
                self.last_section, self.last_rest = "rest", y
                self.plan = ["rest"] * r.randint(*REST_LEN)
                return
        names = list(self.SECTION_EASY)
        weights = [self.SECTION_EASY[n] + (self.SECTION_HARD[n] - self.SECTION_EASY[n]) * d for n in names]
        name = self.last_section
        while name == self.last_section:              # jamais deux fois la même section d'affilée
            name = r.choices(names, weights)[0]
        if name == "meadow":
            kinds = ["grass"] * r.randint(1, 2)
        elif name == "road":                           # 4 routes au début, jusqu'à 8 plus loin
            hi = ROAD_RUN_MIN + int(round((ROAD_RUN_MAX_HARD - ROAD_RUN_MIN) * d))
            kinds = ["road"] * r.randint(ROAD_RUN_MIN, max(ROAD_RUN_MIN, hi))
        elif name == "river":                          # groupe de bûches : court au début, long ensuite
            lo = 1 + int(d * 2.5)
            kinds = ["river"] * r.randint(lo, max(lo, 2 + int(d * 4)))
        elif name == "lilies":                         # groupe de nénuphars
            lo = 1 + int(d * 2)
            kinds = ["pads"] * r.randint(lo, max(lo, 2 + int(d * 3)))
        elif name == "mixed":                          # eau mélangée : bûches et nénuphars
            kinds = []
            for _ in range(r.randint(2, 3 + int(3 * d))):
                k = r.choice(("river", "pads"))
                if len(kinds) >= 2 and kinds[-1] == kinds[-2] == k:
                    k = "pads" if k == "river" else "river"
                kinds.append(k)
        elif name == "rail":
            kinds = ["rail"]
        elif name == "crossing":                       # voie ferrée, 2-3 routes, voie ferrée
            kinds = ["rail"] + ["road"] * r.randint(2, 3) + ["rail"]
        else:                                          # chaos : 3 à 6 rangées tirées librement
            kinds, last, run = [], self.last, self.run
            for _ in range(r.randint(3, 6)):
                k = self.pick(last, run)
                run = run + 1 if k == last else 1
                last = k
                kinds.append(k)
        water = ("river", "pads")
        if (kinds[0] == self.last and self.last != "grass") or (kinds[0] in water and self.last in water):
            kinds.insert(0, "grass")                          # une berge sépare deux blocs identiques / deux groupes d'eau
        self.last_section, self.plan = name, kinds

    def make(self, y, kind, start=False, rest=False):
        r = self.rng
        d = difficulty(y)
        m = 1 + 0.9 * d                      # multiplicateur de vitesse
        prev = self.rows.get(y - 1)
        direction = r.choice((-1, 1))
        if prev is not None and prev.kind == kind and kind in ("road", "river") and r.random() < 0.65:
            direction = -prev.dir            # voies voisines : plutôt en sens contraire
        row = Row(y, kind, r.randint(0, 999), direction)
        if kind == "grass":
            for c in range(-COL_MAX, COL_MAX + 1):
                if c == 0 and y <= 1:
                    continue
                if start:
                    p = 0.1 if y < -1 else 0.0
                else:
                    p = 0.19 + 0.11 * d                                   # un peu moins d'arbres qu'avant (0.20 + 0.12 d)
                    if abs(c) <= 1:
                        p *= TREE_CENTER_FACTOR                           # couloir central plus dégagé
                    elif abs(c) == 2:
                        p *= 0.9
                    if rest:
                        p *= 0.35                                         # zone de repos : très peu d'arbres
                if r.random() < p:
                    row.trees[c] = (r.randint(1, 3), r.randint(0, 2))
            if not start:
                for _ in range(2 if rest else 1):
                    if r.random() < (0.30 if rest else 0.12 - 0.06 * d):
                        free = [c for c in range(-COL_MAX, COL_MAX + 1) if c not in row.trees and c not in row.coins]
                        if free:
                            row.coins.add(r.choice(free))
        elif kind == "road":
            small = r.random() < SMALL_LANE_START + (SMALL_LANE_END - SMALL_LANE_START) * d   # voie de petites voitures
            row.speed = r.uniform(1.6, 3.8) * m
            if small:
                row.speed = min(row.speed * SMALL_SPEED_MUL, SMALL_SPEED_MAX)
            n = min(5, 2 + int(round(2 * d)) + r.choice((0, 1)))     # 2-3 au début, 4-5 plus loin
            jit = 1.2 - 0.5 * d
            sp, o = WRAP / n, r.uniform(0, WRAP)
            for i in range(n):
                truck = (not small) and r.random() < min(0.15 + 0.30 * d, 0.45 if n < 5 else 0.3)
                row.items.append(dict(off=(o + i * sp + r.uniform(-jit, jit)) % WRAP,
                                      len=3.2 if truck else (1.05 if small else 1.5),
                                      truck=truck, small=small,
                                      color=r.choice(CAR_COLORS), color2=r.choice(TRAILERS)))
        elif kind == "river":
            row.speed = r.uniform(*LOG_SPEED) * m                    # un peu plus rapide qu'avant
            if prev is not None and prev.kind == "river" and prev.dir == row.dir:
                # deux rivières voisines dans le même sens : vitesses nettement différentes
                gap, lo_s, hi_s = 0.55 * m, LOG_SPEED[0] * 0.85 * m, LOG_SPEED[1] * 1.12 * m
                options = []
                if prev.speed - gap >= lo_s:
                    options.append(r.uniform(lo_s, prev.speed - gap))
                if prev.speed + gap <= hi_s:
                    options.append(r.uniform(prev.speed + gap, hi_s))
                row.speed = r.choice(options) if options else prev.speed + gap
            cut = r.random() < CUT_LOG_START + (CUT_LOG_END - CUT_LOG_START) * d    # rivière de "bûches coupées"
            pos, centers = r.uniform(0, 2), []
            while pos < WRAP - 3:
                p1 = LOG1_CHANCE_START + (LOG1_CHANCE_END - LOG1_CHANCE_START) * d      # bûche d'1 case
                if cut:
                    ln = r.choice((1, 1, 2, 2))
                    gap = r.uniform(0.8 + 0.5 * d, 1.6 + 0.7 * d)
                elif r.random() < p1:
                    ln, gap = 1, r.uniform(1.0 + 0.7 * d, 2.2 + 0.9 * d)
                else:
                    ln = r.choice((2, 2, 3, 3, 4) if r.random() > d else (2, 2, 2, 3))
                    gap = r.uniform(1.0 + 0.7 * d, 2.2 + 0.9 * d)
                centers.append([pos + ln / 2, ln])
                pos += ln + gap
            scale = WRAP / pos
            row.logs = [(c * scale, ln) for c, ln in centers]
        elif kind == "pads":
            if prev is not None and prev.kind == "pads":
                # groupe de nénuphars : on garde une partie de la rangée précédente et on en ajoute de nouveaux
                cols = {c for c in prev.pads if r.random() < 0.72}
                if not cols:
                    cols = {r.choice(sorted(prev.pads))}
                cols |= {c for c in range(-COL_MAX, COL_MAX + 1) if r.random() < 0.30 - 0.10 * d}
            else:
                cols = {c for c in range(-COL_MAX, COL_MAX + 1) if r.random() < 0.55 - 0.15 * d}
            while len(cols) < 3:
                cols.add(r.randint(-COL_MAX, COL_MAX))
            row.pads = cols
        elif kind == "rail":
            row.timer = r.uniform(0.5, 3.5)
            row.idle = (max(0.6, 2.0 - 1.4 * d), max(1.6, 5.0 - 3.0 * d))
            row.warn = max(0.9, 1.4 - 0.5 * d)
        return row

    def generate(self, y_max):
        """Génère les rangées jusqu'à y_max (en suivant le plan de sections)."""
        while self.top <= y_max:
            if not self.plan:
                self.plan_section()
            tag = self.plan.pop(0)
            rest = tag == "rest"
            k = "grass" if rest else tag
            self.run = self.run + 1 if k == self.last else 1
            self.last = k
            row = self.make(self.top, k, rest=rest)
            self.ensure_passable(row)
            self.rows[self.top] = row
            self.top += 1

    # ---- garantie que la map est toujours franchissable ----
    def standable(self, row, c):
        if row.kind == "grass":
            return c not in row.trees
        if row.kind == "pads":
            return c in row.pads
        return True

    def spread(self, row, cells):
        """Colonnes atteignables sur la rangée en se déplaçant latéralement."""
        if row.kind not in ("grass", "pads"):
            return set(range(-COL_MAX, COL_MAX + 1))     # route / rails / rivière : on circule librement
        out, stack = set(cells), list(cells)
        while stack:
            c = stack.pop()
            for n in (c - 1, c + 1):
                if -COL_MAX <= n <= COL_MAX and n not in out and self.standable(row, n):
                    out.add(n)
                    stack.append(n)
        return out

    def groups(self, row, cells):
        """Sépare les cases atteignables d'une rangée en groupes dont les cases communiquent sur les côtés."""
        if not cells:
            return []
        if row.kind not in ("grass", "pads"):
            return [set(cells)]                            # route, rails, rivière : on circule librement
        out, cur = [], set()
        for c in range(-COL_MAX, COL_MAX + 1):
            if c in cells:
                cur.add(c)
            elif cur:
                out.append(cur)
                cur = set()
        if cur:
            out.append(cur)
        return out

    def open_cell(self, row, c):
        """Ouvre la case (row, c) : retire l'arbre / le rocher, ou ajoute un nénuphar."""
        if row.kind == "grass":
            row.trees.pop(c, None)
        elif row.kind == "pads":
            row.pads.add(c)


    # ANTI-IMPASSE : chaque groupe de cases que le joueur peut atteindre sur la rangée précédente doit
    # avoir au moins UNE sortie dans cette rangée
       
    def ensure_passable(self, row):
        for grp in self.reach_groups:
            if not any(self.standable(row, c) for c in grp):
                self.open_cell(row, self.rng.choice(sorted(grp)))
        enter = {c for c in self.reach if self.standable(row, c)}
        self.reach = self.spread(row, enter)
        self.reach_groups = self.groups(row, self.reach)

    #Niveau passer
    def prune(self, y_min):
        """Supprime les rangées derrière la caméra."""
        for y in [y for y in self.rows if y < y_min]:
            del self.rows[y]
