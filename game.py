"""La classe Game : état, entrées clavier, règles (collisions, mort, score), caméra.
Le dessin est délégué à RenderMixin (renderer.py)."""
import json
import math
import random
import sys

import pygame

from ai import CrossyAI
from settings import (LEAD, HOP_T, COL_MAX, WRAP, LOG_SNAP_SPEED, LOG_DIP_DEPTH, LOG_DIP_TIME,
                      SAVE_FILE, ZT, SKINS, LEVEL_STEP,
                      CAM_SMOOTH_Y, CAM_SMOOTH_X, COP_INTERVAL_START, COP_INTERVAL_END, COP_MIN_SCORE, COP_SPEED)
from utils import shade, pd, creep_speed, difficulty
from world import World, ground_z, ground_color
from player import Player
from sounds import make_sounds
from renderer import RenderMixin


class Game(RenderMixin):
    def __init__(self, screen):
        self.screen = screen
        self.f_big = pygame.font.Font(None, 96)
        self.f_mid = pygame.font.Font(None, 52)
        self.f_small = pygame.font.Font(None, 30)
        self.best, self.coins = 0, 0
        self.owned, self.skin_i = {s["name"] for s in SKINS if s["price"] == 0}, 0     # les persos gratuits sont débloqués
        self.snd = make_sounds()
        self.ai = CrossyAI()
        self.ai_enabled = False
        self.ai_timer = 0.0
        self.load()
        self.t = 0.0
        self.paused = False
        self.reset("title")

    # ---- sauvegarde ----
    def load(self):
        try:
            d = json.loads(SAVE_FILE.read_text())
            self.best, self.coins = int(d.get("best", 0)), int(d.get("coins", 0))
            self.owned |= set(d.get("owned", []))
            names = [s["name"] for s in SKINS]
            # on retrouve le perso par son NOM (l'ordre de la liste peut changer), sinon par l'ancien indice
            self.skin_i = names.index(d["skin_name"]) if d.get("skin_name") in names else int(d.get("skin", 0)) % len(SKINS)
        except Exception:
            pass

    def save(self):
        try:
            SAVE_FILE.write_text(json.dumps({"best": self.best, "coins": self.coins,
                                              "owned": sorted(self.owned), "skin": self.skin_i,
                                              "skin_name": SKINS[self.skin_i]["name"]}))
        except Exception:
            pass

    def shutdown(self):
        self.save()

    # ---- état ----
    def reset(self, state="play"):
        self.world = World()
        self.p = Player()
        if state == "title":
            self.p.face = (0, -1)
        self.parts, self.land_t = [], -9.0
        self.level, self.lvl_t = 1, -9.0
        self.cam_x = 0.0
        self.cam_y = -LEAD
        self.started = False
        self.state = state
        self.dead = None
        self.dead_t = 0.0
        self.dead_gz = 0.0
        self.run_coins = 0
        self.cop_t = self.cop_delay()
        self.cop_row = None
        self.ai_timer = 0.0
        self.stop_siren()
        self.world.generate(30)

    # ---- effets ----
    def creep(self):
        return creep_speed(self.p.max_y)

    def play(self, name):
        snd = self.snd.get(name)
        if snd:
            snd.play()

    def skin_now(self):
        sk = SKINS[self.skin_i]
        return sk if (self.state == "title" or sk["name"] in self.owned) else SKINS[0]

    def next_skin(self):
        self.skin_i = (self.skin_i + 1) % len(SKINS)
        sk = SKINS[self.skin_i]
        if sk["name"] not in self.owned and self.coins >= sk["price"]:
            self.coins -= sk["price"]
            self.owned.add(sk["name"])
            self.play("buy")
        self.save()

    def burst(self, x, y, z, col, n, spd=2.0, up=90, life=0.6):
        for _ in range(n):
            a, v = random.uniform(0, 6.283), random.uniform(.3, 1) * spd
            self.parts.append([x, y, z, math.cos(a) * v, math.sin(a) * v,
                               random.uniform(.4, 1) * up, 0.0, life * random.uniform(.6, 1), col])

    def hop_squash(self):
        p = self.p
        if p.hop:
            sn = math.sin(math.pi * min(1.0, p.hop[4]))
            return 1 + 0.28 * sn, 1 - 0.14 * sn
        k = max(0.0, 1 - (self.t - self.land_t) / 0.14)
        return 1 - 0.22 * k + 0.02 * math.sin(self.t * 3), 1 + 0.12 * k

    def player_z(self):
        p = self.p
        rows = self.world.rows
        if p.hop:
            h = p.hop
            f = min(1.0, h[4])
            z0, z1 = ground_z(rows.get(h[1])), ground_z(rows.get(h[3]))
            return z0 + (z1 - z0) * f
        row = rows.get(round(p.y))
        gz = ground_z(row)
        if row is not None and row.kind == "river" and p.ride and p.ride["row"] is row:
            gz += self.log_bob(row, p.ride["idx"])      # le joueur suit le balancement de sa bûche
        return gz

    def die(self, kind):
        if self.state == "dead":
            return
        self.dead_gz = self.player_z()
        self.state, self.dead, self.dead_t = "dead", kind, 0.0
        p, bc = self.p, self.skin_now()["body"]
        if kind == "squash":
            self.burst(p.x, p.y, self.dead_gz + 10, bc, 14)
            self.burst(p.x, p.y, self.dead_gz + 10, (255, 255, 255), 8)
            self.play("splat")
        elif kind == "drown":
            self.burst(p.x, p.y, self.dead_gz, (200, 236, 252), 20, up=140)
            self.play("splash")
        else:
            self.play("eagle")
        self.stop_siren()
        self.best = max(self.best, int(self.p.max_y))
        self.save()

    # ---- entrées ----
    def key(self, k):
        if k == pygame.K_ESCAPE:
            self.shutdown()
            pygame.quit()
            sys.exit()
        if k == pygame.K_i and self.state in ("title", "play"):
            self.ai_enabled = not self.ai_enabled
            self.ai_timer = 0.0
            if self.state == "title":
                self.state = "play"
            return
        if k == pygame.K_p and self.state == "play":
            self.paused = not self.paused
            try:
                pygame.mixer.pause() if self.paused else pygame.mixer.unpause()
            except pygame.error:
                pass
            return
        if k == pygame.K_r:
            self.reset("play")
            return
        if k == pygame.K_c and self.state == "title":
            self.next_skin()
            return
        mv = None
        if k in (pygame.K_UP, pygame.K_w, pygame.K_z, pygame.K_SPACE):
            mv = (0, 1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            mv = (0, -1)
        elif k in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
            mv = (-1, 0)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            mv = (1, 0)
        if self.state == "title" and (mv or k == pygame.K_RETURN):
            self.state = "play"
        elif self.state == "dead":
            if self.dead_t > 0.8 and (k in (pygame.K_SPACE, pygame.K_RETURN) or mv):
                self.reset("play")
            return
        if mv and self.state == "play" and not self.paused:
            self.try_hop(*mv)

    def try_hop(self, dx, dy):
        p = self.p
        if p.hop:
            p.queue = (dx, dy)
            return
        p.face = (dx, dy)
        ty = p.y + dy
        row = self.world.rows.get(ty)
        if row is None:
            return
        follow = None
        if dy != 0:
            tx = p.x if row.kind == "river" else float(round(p.x))
        else:
            tx = p.x + dx
            r = p.ride
            if row.kind == "river" and r is not None and r["row"] is row:
                # déplacement latéral SUR la bûche : on vise la case voisine de la même bûche
                new_off = r["off"] + dx
                if abs(new_off) <= (row.logs[r["idx"]][1] - 1) / 2 + 1e-6:
                    follow = dict(r, off=new_off)
                    tx = self.log_center(row, r["idx"], r["k"]) + new_off
        if abs(tx) > COL_MAX + 0.5:
            return
        if row.kind == "grass" and round(tx) in row.trees:
            return
        p.hop_follow = follow
        p.ride = None
        p.hop = [p.x, p.y, tx, ty, 0.0]
        self.started = True
        self.play("hop")

    # ---- logique ----
    def on_log(self, row, x):
        return self.find_log(row, x) is not None

    # ---- bûches : chaque bûche est une suite de 2, 3 ou 4 CASES ----
    def log_center(self, row, idx, k):
        return row.shift + row.logs[idx][0] + k * WRAP

    def log_dip_k(self, row, idx):
        """Progression 0..1 de l'enfoncement de la bûche, ou None s'il n'y en a pas."""
        t0 = row.dips.get(idx)
        if t0 is None:
            return None
        k = (self.t - t0) / LOG_DIP_TIME
        return k if 0 <= k < 1 else None

    def log_bob(self, row, idx):
        """Hauteur de la bûche : balancement + enfoncement à l'atterrissage (descend vite, remonte doucement)."""
        z = math.sin(self.t * 2 + row.logs[idx][0]) * 1.2
        k = self.log_dip_k(row, idx)
        if k is not None:
            z -= LOG_DIP_DEPTH * math.sin(math.pi * k ** 0.6)
        return z

    def find_log(self, row, x):
        """Bûche située sous la position x : (indice, copie k, écart d au centre) ou None."""
        for idx, (c, ln) in enumerate(row.logs):
            base = row.shift + c
            d = pd(x, base)
            if abs(d) <= ln / 2 + 0.1:
                return idx, round((x - base - d) / WRAP), d
        return None

    def attach_log(self, row, hit):
        """Place le joueur sur la case de la bûche la plus proche (recalage doux)."""
        idx, k, d = hit
        ln = row.logs[idx][1]
        off = min((i - (ln - 1) / 2 for i in range(int(ln))), key=lambda o: abs(o - d))
        self.p.ride = dict(row=row, idx=idx, k=k, off=off)
        self.p.snap = d - off              # écart actuel : se résorbe en quelques images

    def ride_log(self, row, dt):
        p = self.p
        r = p.ride
        if r is None or r["row"] is not row:
            hit = self.find_log(row, p.x)
            if hit is None:
                self.die("drown")
                return
            self.attach_log(row, hit)
            r = p.ride
        p.snap *= math.exp(-LOG_SNAP_SPEED * dt)
        p.x = self.log_center(row, r["idx"], r["k"]) + r["off"] + p.snap
        if abs(p.x) > 5.4:
            self.die("drown")

    def land(self):
        p = self.p
        row = self.world.rows.get(round(p.y))
        if row is None:
            return
        p.max_y = max(p.max_y, p.y)
        self.land_t = self.t
        if row.kind in ("grass", "road", "rail"):
            self.burst(p.x, p.y, ground_z(row), shade(ground_color(row), 1.2), 5, 1.0, 45, .35)
        if row.kind == "pads" and round(p.x) not in row.pads:
            self.die("drown")
        elif row.kind == "river":
            hit = self.find_log(row, p.x)
            if hit is None:
                self.die("drown")
            else:
                self.attach_log(row, hit)
                row.dips[hit[0]] = self.t              # la bûche s'enfonce sous le poids du joueur
        elif row.kind == "grass" and round(p.x) in row.coins:
            row.coins.discard(round(p.x))
            self.coins += 1
            self.run_coins += 1
            self.burst(p.x, p.y, ground_z(row) + 14, (255, 214, 62), 8, 1.2, 110, .5)
            self.play("coin")

    # ---- voiture de police ----
    # Déroulement sur une route visible :
    #   clearing  : plus aucun nouveau véhicule n'entre, ceux de l'écran finissent de sortir
    #   active    : la route est vide, la police traverse (sirène tant qu'elle n'a pas dépassé le joueur)
    #   restoring : les véhicules reviennent un par un, hors écran, une fois la police partie
    def cop_delay(self):
        """Délai avant la prochaine police : raccourcit avec la difficulté (donc en montant)."""
        d = difficulty(self.p.max_y)
        lo = COP_INTERVAL_START[0] + (COP_INTERVAL_END[0] - COP_INTERVAL_START[0]) * d
        hi = COP_INTERVAL_START[1] + (COP_INTERVAL_END[1] - COP_INTERVAL_START[1]) * d
        return random.uniform(lo, hi)

    def lane_window(self, row):
        return self.xrange_(row.y, pad=0)           # zone réellement visible de la rangée

    def veh_visible(self, row, v, lo, hi):
        m = v["len"] / 2 + 0.6
        return bool(self.copies(row.shift + v["off"], lo - m, hi + m))

    def start_cop(self):
        rows = [r for r in self.world.rows.values()
                if r.kind == "road" and 1 <= r.y - self.cam_y <= 14 and r.cop_state is None]
        if not rows:
            self.cop_t = 1.5
            return
        row = random.choice(rows)
        lo, hi = self.lane_window(row)
        for v in row.items:
            v["gone"] = not self.veh_visible(row, v, lo, hi)
        row.cop_state = "clearing"
        self.cop_row = row
        self.cop_t = 1e9                             # relancé quand la police est repartie

    def stop_siren(self):
        snd = self.snd.get("siren")
        if snd:
            snd.stop()
        self.siren_on = False

    def end_cop(self, row):
        row.cop_state = None
        row.cops = []
        for v in row.items:
            v["gone"] = False
        self.cop_row = None
        self.cop_t = self.cop_delay()
        self.stop_siren()

    def service_cop(self):
        row = self.cop_row
        if row is None:
            return
        # l'événement ne s'arrête que quand la voie est vraiment hors de l'écran (le bas de l'écran
        # montre jusqu'à ~9,5 rangées sous la caméra) ou supprimée du monde
        if self.world.rows.get(row.y) is not row or row.y < self.cam_y - 12:
            self.end_cop(row)
            return
        lo, hi = self.lane_window(row)
        if row.cop_state == "clearing":
            for v in row.items:
                if not v.get("gone") and not self.veh_visible(row, v, lo, hi):
                    v["gone"] = True
            if all(v.get("gone") for v in row.items):          # route vide : la police arrive
                spd = COP_SPEED + 3.0 * difficulty(self.p.max_y)
                start = (lo - 4.0) if row.dir > 0 else (hi + 4.0)   # juste hors écran
                v = dict(truck=False, len=1.5, cop=True, color=(34, 46, 92), color2=(0, 0, 0))
                row.cops.append(dict(x=start, spd=spd, v=v, passed=False))
                row.cop_state = "active"
                snd = self.snd.get("siren")
                if snd:
                    snd.set_volume(0.6)
                    snd.play(loops=-1)
                self.siren_on = True
        elif row.cop_state == "active":
            exit_x = hi if row.dir > 0 else lo                  # la police est retirée une fois sortie de l'écran
            row.cops = [c for c in row.cops if (c["x"] - exit_x) * row.dir <= 3.0]
            if row.cops:
                cop = row.cops[0]
                dist = cop["x"] - self.p.x
                if not cop["passed"] and dist * row.dir > 0.8:   # la police a dépassé le joueur
                    cop["passed"] = True
                    self.stop_siren()
                elif not cop["passed"] and self.siren_on:
                    snd = self.snd.get("siren")
                    if snd:
                        snd.set_volume(max(0.2, min(1.0, 1.0 - abs(dist) / 24.0)))
            else:
                row.cop_state = "restoring"
                self.stop_siren()
        elif row.cop_state == "restoring":
            for v in row.items:
                if v.get("gone") and not self.veh_visible(row, v, lo, hi):
                    v["gone"] = False
            if not any(v.get("gone") for v in row.items):
                self.end_cop(row)

    def update(self, dt):
        self.t += dt
        for q in self.parts:
            q[0] += q[3] * dt
            q[1] += q[4] * dt
            q[2] += q[5] * dt
            q[5] -= 380 * dt
            q[6] += dt
        self.parts = [q for q in self.parts if q[6] < q[7]]
        w = self.world
        for r in w.rows.values():
            r.update(dt, w.rng)
        if self.state == "dead":
            self.dead_t += dt
            return
        if self.state != "play" or self.paused:
            return
        p = self.p
        if p.hop:
            h = p.hop
            if p.hop_follow:                               # saut latéral sur bûche : la cible suit la bûche
                hf = p.hop_follow
                h[2] = self.log_center(hf["row"], hf["idx"], hf["k"]) + hf["off"]
            h[4] += dt / HOP_T
            f = min(1.0, h[4])
            p.x = h[0] + (h[2] - h[0]) * f
            p.y = h[1] + (h[3] - h[1]) * f
            p.lift = math.sin(math.pi * f) * 24
            if h[4] >= 1:
                p.x, p.y, p.hop, p.lift = h[2], h[3], None, 0.0
                p.hop_follow = None
                self.land()
                if p.queue and self.state == "play":
                    mv, p.queue = p.queue, None
                    self.try_hop(*mv)
        else:
            row = w.rows.get(round(p.y))
            if row is not None and row.kind == "river":
                self.ride_log(row, dt)
        if self.state != "play":
            return
        row = w.rows.get(round(p.y))
        if row is not None:
            if row.kind == "road":
                for v in row.items:
                    if v.get("gone"):
                        continue
                    if abs(pd(p.x, row.shift + v["off"])) < v["len"] / 2 + 0.3:
                        self.die("squash")
                        return
                for c in row.cops:
                    if abs(p.x - c["x"]) < 0.75 + 0.3:
                        self.die("squash")
                        return
            elif row.kind == "rail" and row.state == "pass":
                lo, hi = row.train_extent()
                if lo - 0.3 < p.x < hi + 0.3:
                    self.die("squash")
                    return
        lvl = 1 + int(p.max_y // LEVEL_STEP)
        if lvl > self.level:
            self.level, self.lvl_t = lvl, self.t
            self.play("buy")
        # voiture de police (rare)
        if self.started and p.max_y >= COP_MIN_SCORE and self.cop_row is None:
            self.cop_t -= dt
            if self.cop_t <= 0:
                self.start_cop()
        self.service_cop()
        # caméra
        if self.started:
            creep = self.creep()
            target = max(p.max_y, p.y) - LEAD          # suit aussi le saut en cours
            c = self.cam_y + creep * dt
            if target > self.cam_y:
                c = max(c, self.cam_y + (target - self.cam_y) * (1 - math.exp(-CAM_SMOOTH_Y * dt)))
            self.cam_y = c
        self.cam_x += (p.x - self.cam_x) * (1 - math.exp(-CAM_SMOOTH_X * dt))
        if p.y < self.cam_y - 1.0:
            self.die("eagle")
            return
        w.generate(int(self.cam_y) + 30)
        w.prune(int(self.cam_y) - 16)
        if self.ai_enabled and not self.paused and self.state == "play":
            self.ai_timer += dt
            if self.ai_timer >= 0.18:
                self.ai_timer = 0.0
                action = self.ai.choose_action(self)
                if action is not None:
                    self.try_hop(*action)
