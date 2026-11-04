"""Tout le DESSIN du jeu (projection isométrique, cubes, rangées, joueur, HUD).

RenderMixin est "mélangé" à la classe Game : les méthodes ici utilisent
self.screen, self.p, self.world, self.t, self.cam_x... fournis par Game.
Ce fichier ne doit contenir que du rendu, jamais de règles de jeu.
"""
import math

import pygame

from settings import (W, H, AX, AY, BX, BY, OX, OY, Z_BOT, COL_MAX, WRAP, ZT, LOG_H, LOG_C,
                      GRASS_C, ROAD_C, WATER_C, RAIL_C, PAD_C, FOLIAGE, WINDOW, SKINS,
                      SIDE_DARKEN, FOAM_COLOR, TRUNK_H, RAIL_SIGNAL_X, CHICKEN_SCALE)
from utils import shade
from world import ground_color
from sprites import draw_coin, draw_eagle


class RenderMixin:
    # ---- projection / primitives ----
    def P(self, x, y, z):
        """Coordonnées monde (x, y, z) -> pixels écran."""
        dx, dy = x - self.cam_x, y - self.cam_y
        return (OX + dx * AX + dy * AY,
                OY + dx * BX - dy * BY - z)

    def xrange_(self, y, pad=90):
        dy = y - self.cam_y
        lo = self.cam_x + (-pad - OX - dy * AY) / AX
        hi = self.cam_x + (W + pad - OX - dy * AY) / AX
        return lo, hi

    def cube(self, x0, x1, y0, y1, z0, z1, col):
        s, P = self.screen, self.P
        pygame.draw.polygon(s, shade(col, 0.84), [P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)])
        pygame.draw.polygon(s, shade(col, 0.66), [P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)])
        pygame.draw.polygon(s, col, [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)])

    def top_poly(self, x0, x1, y0, y1, z, col):
        P = self.P
        pygame.draw.polygon(self.screen, col, [P(x0, y0, z), P(x1, y0, z), P(x1, y1, z), P(x0, y1, z)])

    def face_b(self, x0, x1, y, z0, z1, col):
        P = self.P
        pygame.draw.polygon(self.screen, col, [P(x0, y, z0), P(x1, y, z0), P(x1, y, z1), P(x0, y, z1)])

    def face_a(self, x, y0, y1, z0, z1, col):
        P = self.P
        pygame.draw.polygon(self.screen, col, [P(x, y0, z0), P(x, y1, z0), P(x, y1, z1), P(x, y0, z1)])

    def slab(self, xa, xb, y0, y1, zt, col):
        P, s = self.P, self.screen
        pygame.draw.polygon(s, shade(col, 0.74), [P(xa, y0, Z_BOT), P(xb, y0, Z_BOT), P(xb, y0, zt), P(xa, y0, zt)])
        self.top_poly(xa, xb, y0, y1, zt, col)

    def draw_borders(self, row, xa, xb, zt, col):
        """Assombrit le sol hors des colonnes jouables (bordures gauche / droite)."""
        edge = COL_MAX + 0.5
        dark = shade(col, SIDE_DARKEN[row.kind])
        y0, y1 = row.y - .5, row.y + .5
        if xa < -edge:
            self.top_poly(xa, -edge, y0, y1, zt, dark)
        if xb > edge:
            self.top_poly(edge, xb, y0, y1, zt, dark)

    def draw_foam(self, row, lo, hi, zt):
        """Particules blanches : écume le long des bordures + éclats sur l'eau."""
        t, y, edge = self.t, row.y, COL_MAX + 0.5
        for i in range(7):
            for sd in (-1, 1):
                dx = ((i * 0.43 + row.seed * 0.017 + t * 0.25 * sd) % 1.8) - 0.3
                yf = y - .4 + ((i * 0.29 + row.seed * 0.011 + sd * 0.13) % 0.8)
                xf = sd * (edge + dx)
                self.top_poly(xf, xf + .16, yf, yf + .07, zt, FOAM_COLOR)
        for i in range(10):
            xw = lo - 2 + ((i * 5.9 + row.seed * 0.53 + t * 0.4 * (1 if i % 2 else -1)) % (hi - lo + 4))
            yf = y - .38 + ((i * 0.37 + row.seed * 0.021) % 0.76)
            if abs(xw) > edge:
                self.top_poly(xw, xw + .12, yf, yf + .06, zt, FOAM_COLOR)

    # ---- objets ----
    def tree_at(self, row, c):
        if abs(c) <= COL_MAX:
            return row.trees.get(c)
        h = ((c * 73856093) ^ (row.seed * 19349663) ^ (row.y * 83492791)) & 0xFFFF
        if abs(c) == COL_MAX + 1 or h / 65535.0 < 0.5:
            return (1 + (h >> 3) % 3, (h >> 5) % 3)
        return None

    def draw_tree(self, x, y, z0, layers, tint):
        cube = self.cube
        if tint == 2 and layers == 1:                 # rocher
            cube(x - .32, x + .32, y - .32, y + .32, z0, z0 + 11, (152, 156, 164))
            cube(x - .18, x + .18, y - .18, y + .18, z0 + 11, z0 + 18, (170, 174, 182))
            return
        # tronc : plus haut et plus fin, pour rester visible sous le feuillage
        cube(x - .15, x + .15, y - .15, y + .15, z0, z0 + TRUNK_H, (122, 86, 54))
        if tint == 1:                                  # sapin
            z = z0 + TRUNK_H - 3
            for half, hh in ((.34, 14), (.26, 14), (.16, 14)):
                cube(x - half, x + half, y - half, y + half, z, z + hh, (50, 128, 80))
                z += hh
            return
        col = FOLIAGE[tint]
        z = z0 + TRUNK_H - 2
        for i in range(layers):
            half = .36 - .05 * i                       # base plus petite qu'avant (.44)
            cube(x - half, x + half, y - half, y + half, z, z + 17, col)
            z += 17

    def draw_vehicle(self, x, y, d, v, zt):
        if v["truck"]:
            self.draw_truck(x, y, d, v, zt)
        elif v.get("small"):
            self.draw_mini(x, y, d, v, zt)
        else:
            self.draw_car(x, y, d, v, zt)

    def _tools(self, x, y, d, zt):
        """Outils de dessin d'un véhicule en coordonnées locales :
        u = position le long du véhicule (+ = avant), décalages latéraux relatifs à y,
        hauteurs relatives à zt. Retourne (X, box, side, end)."""
        def X(u):
            return x + d * u

        def box(u0, u1, y0, y1, z0, z1, col):
            lo, hi = sorted((X(u0), X(u1)))
            self.cube(lo, hi, y + y0, y + y1, zt + z0, zt + z1, col)

        def side(u0, u1, z0, z1, col, yy=-.434):      # décor collé sur le flanc visible
            lo, hi = sorted((X(u0), X(u1)))
            self.face_b(lo, hi, y + yy, zt + z0, zt + z1, col)

        def end(xv, y0, y1, z0, z1, col):             # décor collé sur la face x+ visible
            self.face_a(xv, y + y0, y + y1, zt + z0, zt + z1, col)
        return X, box, side, end

    def draw_wheel(self, xc, y, zt, hl=.16, outer=-.44, near=-.30, h=6.5):
        """Roue côté caméra : pneu sombre + jante claire + moyeu."""
        TIRE, RIM, HUB = (26, 26, 32), (206, 210, 218), (110, 114, 126)
        self.cube(xc - hl, xc + hl, y + outer, y + near, zt, zt + h, TIRE)
        yy = y + outer - .004
        self.face_b(xc - hl * .62, xc + hl * .62, yy, zt + h * .22, zt + h * .78, RIM)
        self.face_b(xc - hl * .22, xc + hl * .22, yy - .002, zt + h * .42, zt + h * .58, HUB)

    def draw_car(self, x, y, d, v, zt):
        """Voiture. Si v["cop"] : voiture de police (bleu nuit, portes blanches, gyrophares)."""
        cop = v.get("cop", False)
        col = (34, 46, 92) if cop else v["color"]
        X, box, side, end = self._tools(x, y, d, zt)
        seed = int(abs(v.get("off", 0.0)) * 10)               # petites variations stables d'une voiture à l'autre
        roof = (236, 236, 242) if cop else (shade(col, .70) if seed % 3 == 0 else col)
        DARK, CHROME, LAMP, RED = (40, 42, 50), (200, 204, 214), (255, 238, 150), (230, 50, 50)
        mirror = (30, 32, 40) if cop else shade(col, .85)
        bump = DARK if cop else (172, 176, 188)

        box(.30, .40, .34, .44, 14, 17, mirror)                    # rétroviseur côté lointain
        box(-.70, .70, -.30, .30, 1, 3.5, DARK)                    # dessous
        if d > 0:                                                  # pare-chocs côté lointain
            box(-.82, -.76, -.33, .33, 3, 5.6, bump)
        else:
            box(.76, .82, -.33, .33, 3, 5.6, bump)
        box(-.75, .75, -.36, .36, 3, 13, col)                      # carrosserie
        # --- décor du flanc ---
        if cop:
            side(-.5, .5, 4.2, 12, (240, 240, 246), -.364)         # portes blanches
        side(-.7, .7, 3, 4.2, shade(col, .62), -.364)              # bas de caisse
        side(-.75, .75, 11.4, 12.1, (shade(col, 1.18) if not cop else (60, 80, 150)), -.364)   # ligne de ceinture
        for u in (.45, -.45):                                      # passages de roues
            side(u - .21, u + .21, 3, 7.6, shade(col, .45), -.366)
        for u in (-.44, -.10, .26):                                # joints de portes
            side(u - .012, u + .012, 4.2, 11.2, shade(col, .65) if not cop else (34, 46, 92), -.368)
        for u in (-.28, .08):                                      # poignées
            side(u - .05, u + .05, 9.4, 10.2, CHROME, -.370)
        # --- habitacle ---
        box(-.5, .3, -.32, .32, 13, 20, WINDOW)
        side(-.13, -.07, 13, 20, roof, -.324)                      # montant central
        side(-.5, .3, 19.2, 20, roof, -.324)                       # cadre du toit
        box(-.53, .33, -.35, .35, 20, 23, roof)                    # toit
        xg = max(X(-.5), X(.3)) + .004                             # vitre avant / arrière visible
        end(xg, -.26, -.12, 14.5, 18.5, (104, 138, 180))
        end(xg, .02, .10, 14.5, 18.5, (104, 138, 180))
        # --- face visible : avant (phares, calandre) ou arrière (feux, plaque) ---
        xe = x + .75 + .004
        if d > 0:
            end(xe, -.32, -.16, 6.5, 10.5, LAMP)
            end(xe, .16, .32, 6.5, 10.5, LAMP)
            end(xe, -.11, .11, 5.5, 9.5, DARK)
            end(xe + .003, -.11, .11, 7.2, 7.8, CHROME)
        else:
            end(xe, -.32, -.17, 6.5, 10.5, RED)
            end(xe, .17, .32, 6.5, 10.5, RED)
            end(xe, -.09, .09, 5, 7.6, (240, 240, 230))
        if d > 0:                                                  # pare-chocs côté caméra
            box(.76, .82, -.33, .33, 3, 5.6, bump)
        else:
            box(-.82, -.76, -.33, .33, 3, 5.6, bump)
        if cop:                                                    # gyrophares (le plus lointain d'abord)
            xc = x - d * 0.1
            blink = int(self.t * 8) % 2 == 0
            blue = (70, 120, 255) if not blink else (28, 40, 110)
            red = (255, 60, 60) if blink else (110, 28, 28)
            self.cube(xc - .1, xc + .1, y + .02, y + .30, zt + 23, zt + 27, blue)
            self.cube(xc - .1, xc + .1, y - .30, y - .02, zt + 23, zt + 27, red)
        elif seed % 4 == 0:                                        # antenne
            box(-.46, -.42, .28, .32, 23, 31, DARK)
        for u in (.45, -.45):                                      # roues
            self.draw_wheel(X(u), y, zt)
        box(.30, .40, -.44, -.35, 14, 17, mirror)                  # rétroviseur côté caméra
        side(.31, .39, 14.6, 16.4, (170, 196, 222), -.444)

    def draw_mini(self, x, y, d, v, zt):
        """Petite voiture (~1 case) : citadine courte, cabine haute, grands phares."""
        X, box, side, end = self._tools(x, y, d, zt)
        col = v["color"]
        seed = int(abs(v.get("off", 0.0)) * 10)
        roof = shade(col, .70) if seed % 3 == 0 else col
        DARK, CHROME, LAMP, RED = (40, 42, 50), (200, 204, 214), (255, 238, 150), (230, 50, 50)
        mirror, bump = shade(col, .85), (172, 176, 188)

        box(.18, .26, .31, .40, 13, 15.5, mirror)                    # rétroviseur côté lointain
        box(-.45, .45, -.28, .28, 1, 3.5, DARK)                      # dessous
        if d > 0:                                                    # pare-chocs côté lointain
            box(-.55, -.50, -.30, .30, 3, 5.6, bump)
        else:
            box(.50, .55, -.30, .30, 3, 5.6, bump)
        box(-.5, .5, -.34, .34, 3, 12, col)                          # carrosserie
        side(-.46, .46, 3, 4.2, shade(col, .62), -.344)              # bas de caisse
        side(-.5, .5, 10.6, 11.2, shade(col, 1.18), -.344)           # ligne de ceinture
        for u in (.3, -.3):                                          # passages de roues
            side(u - .19, u + .19, 3, 7.2, shade(col, .45), -.346)
        side(.04, .08, 4.2, 10.4, shade(col, .65), -.348)            # joint de porte
        side(-.12, -.04, 9, 9.7, CHROME, -.350)                      # poignée
        box(-.36, .22, -.30, .30, 12, 19, WINDOW)                    # habitacle
        side(-.10, -.05, 12, 19, roof, -.304)                        # montant
        side(-.36, .22, 18.2, 19, roof, -.304)
        box(-.39, .25, -.32, .32, 19, 22, roof)                      # toit
        xg = max(X(-.36), X(.22)) + .004                             # vitre avant / arrière visible
        end(xg, -.22, -.10, 13.5, 17.5, (104, 138, 180))
        end(xg, .02, .09, 13.5, 17.5, (104, 138, 180))
        xe = x + .5 + .004                                           # face visible : avant ou arrière
        if d > 0:
            end(xe, -.29, -.15, 6.2, 10, LAMP)
            end(xe, .15, .29, 6.2, 10, LAMP)
            end(xe, -.09, .09, 5, 8.2, DARK)
            end(xe + .003, -.09, .09, 6.5, 7.1, CHROME)
        else:
            end(xe, -.29, -.16, 6.2, 10, RED)
            end(xe, .16, .29, 6.2, 10, RED)
            end(xe, -.08, .08, 4.8, 7.2, (240, 240, 230))
        if d > 0:                                                    # pare-chocs côté caméra
            box(.50, .55, -.30, .30, 3, 5.6, bump)
        else:
            box(-.55, -.50, -.30, .30, 3, 5.6, bump)
        if seed % 4 == 0:                                            # antenne
            box(-.30, -.26, .24, .28, 22, 29, DARK)
        for u in (.3, -.3):                                          # roues (un peu plus petites)
            self.draw_wheel(X(u), y, zt, hl=.14, outer=-.40, near=-.27, h=6)
        box(.18, .26, -.40, -.32, 13, 15.5, mirror)                  # rétroviseur côté caméra
        side(.19, .25, 13.6, 15, (170, 196, 222), -.404)

    def draw_pad(self, c, y, zt, orient):
        """Nénuphar : plateforme carrée avec un coin manquant ; l'encoche change de sens (4 orientations)."""
        sx, sy = ((1, 1), (-1, 1), (-1, -1), (1, -1))[orient]
        h, q = .4, .3                                   # demi-côté, taille de l'encoche
        if sy > 0:
            rects = [(c - h, c + h, y - h, y + h - q)]
            y0, y1 = y + h - q, y + h
        else:
            rects = [(c - h, c + h, y - h + q, y + h)]
            y0, y1 = y - h, y - h + q
        rects.append((c - h, c + h - q, y0, y1) if sx > 0 else (c - h + q, c + h, y0, y1))
        col = shade(PAD_C, .94 + .04 * orient)
        for xa, xb, ya, yb in sorted(rects, key=lambda r: -r[2]):     # le plus lointain d'abord
            self.cube(xa, xb, ya, yb, zt - 1, zt + 2, col)

    def draw_truck(self, x, y, d, v, zt):
        """Camion : cabine + remorque. Les pièces sont dessinées de la plus lointaine
        à la plus proche (la caméra voit les faces y- et x+), selon le sens de marche d.
        Toutes les positions latérales sont RELATIVES à y (centre de la rangée)."""
        cube, face_a, face_b = self.cube, self.face_a, self.face_b
        cab_c, box_c = v["color"], v["color2"]
        DARK, CHROME, LAMP = (44, 46, 54), (196, 200, 210), (255, 238, 150)

        def X(u):                          # u = position le long du camion (+ = avant)
            return x + d * u

        def box(u0, u1, y0, y1, z0, z1, col):
            lo, hi = sorted((X(u0), X(u1)))
            cube(lo, hi, y + y0, y + y1, zt + z0, zt + z1, col)

        def side(u0, u1, z0, z1, col, yy=-.434):      # décor collé sur le flanc visible
            lo, hi = sorted((X(u0), X(u1)))
            face_b(lo, hi, y + yy, zt + z0, zt + z1, col)

        def end(xv, y0, y1, z0, z1, col):             # décor collé sur la face x+ visible
            face_a(xv, y + y0, y + y1, zt + z0, zt + z1, col)

        def trailer():
            box(-1.6, .45, -.43, .43, 5, 33, box_c)
            side(-1.6, .45, 12, 17, cab_c)                              # bandeau de couleur
            for u in (-1.1, -.6, -.1):                                  # joints de panneaux
                side(u - .015, u + .015, 6, 32, shade(box_c, .78))
            if d < 0:                                                   # l'arrière est visible
                xr = X(-1.6) + .004
                end(xr, -.40, -.012, 7, 31, shade(box_c, .80))
                end(xr, .012, .40, 7, 31, shade(box_c, .90))
                end(xr + .004, -.40, -.29, 8, 12, (230, 50, 50))
                end(xr + .004, .29, .40, 8, 12, (230, 50, 50))

        def cab():
            box(1.10, 1.26, .38, .52, 17, 24, DARK)                     # rétroviseur côté lointain
            box(.55, 1.65, -.40, .40, 4, 16, cab_c)                     # capot
            box(.55, 1.2, -.38, .38, 16, 27, cab_c)                     # cabine
            side(.62, 1.13, 18.5, 25, WINDOW, -.384)                    # vitre latérale
            side(.62, 1.13, 25, 25.8, shade(cab_c, .7), -.384)
            if d > 0:                                                   # l'avant est visible
                end(X(1.2) + .004, -.31, .31, 18.5, 25, WINDOW)         # pare-brise
                xf = X(1.65) + .004
                end(xf, -.32, .32, 6, 14, (36, 38, 46))                 # calandre
                for z in (8, 10.5, 13):
                    end(xf + .003, -.30, .30, z, z + .9, CHROME)
                end(xf + .003, -.40, -.27, 8, 12.5, LAMP)               # phares
                end(xf + .003, .27, .40, 8, 12.5, LAMP)
            box(1.62, 1.74, -.36, .36, 3, 6.5, (150, 154, 164))         # pare-chocs
            for yy in (.2, 0.0, -.2):                                   # feux de toit
                box(.85, .95, yy - .04, yy + .04, 27, 29.5, (255, 170, 40))
            box(.58, .70, .30, .40, 27, 36, CHROME)                     # cheminée d'échappement
            box(1.10, 1.26, -.52, -.38, 17, 24, DARK)                   # rétroviseur côté caméra
            side(1.12, 1.24, 18, 23, (150, 176, 204), -.524)

        box(-1.6, 1.8, -.34, .34, 2, 5, DARK)                           # châssis
        if d > 0:
            trailer()
            cab()
        else:
            cab()
            trailer()
        for u in (1.15, -.1, -1.0):                                     # roues côté caméra
            self.draw_wheel(X(u), y, zt, hl=.18, outer=-.48, near=-.22, h=7)

    def draw_log(self, x, ln, y, bob):
        z = ZT["river"] + bob
        self.cube(x - ln / 2, x + ln / 2, y - .4, y + .4, z - 6, z + LOG_H, LOG_C)
        self.cube(x + ln / 2, x + ln / 2 + .05, y - .34, y + .34, z - 4, z + LOG_H - 2, (218, 180, 124))

    def draw_frog(self, x, y, z0, sq=1.0, wide=1.0, face=(0, 1)):
        """Héros : petite grenouille cubique (personnage original)."""
        if self.skin_now().get("style") == "chicken":
            self.draw_chicken(x, y, z0, sq, wide, face)
            return
        cube = self.cube
        fx, fy = face
        px, py = abs(fy), abs(fx)
        hw = 0.33 * wide
        h = 22 * sq
        sk = self.skin_now()
        body, foot, belly = sk["body"], sk["foot"], sk["belly"]
        for sgn in (-1, 1):                            # pieds
            cx_ = x + fx * 0.34 + px * sgn * 0.19
            cy_ = y + fy * 0.34 + py * sgn * 0.19
            cube(cx_ - .11, cx_ + .11, cy_ - .11, cy_ + .11, z0, z0 + max(1, 5 * sq), foot)
        cube(x - hw, x + hw, y - hw, y + hw, z0 + 3, z0 + 3 + h, body)
        ztop = z0 + 3 + h
        if sq > 0.5:                                   # bande sombre sur le dos
            self.top_poly(x - .09, x + .09, y - hw + .06, y + hw - .06, ztop, (214, 100, 28))
        if fx == 1:                                    # ventre vers la caméra
            self.face_a(x + hw, y - hw + .08, y + hw - .08, z0 + 5, z0 + 3 + h * 0.55, belly)
        elif fy == -1:
            self.face_b(x - hw + .08, x + hw - .08, y - hw, z0 + 5, z0 + 3 + h * 0.55, belly)
        eh = max(2, 9 * sq)
        for sgn in (-1, 1):                            # yeux
            ex = x + fx * 0.19 + px * sgn * 0.17
            ey = y + fy * 0.19 + py * sgn * 0.17
            cube(ex - .115, ex + .115, ey - .115, ey + .115, ztop, ztop + eh, (252, 252, 252))
            if sq > 0.5:
                if fx == 1:
                    self.face_a(ex + .115, ey - .05, ey + .05, ztop + 2, ztop + 7, (24, 24, 34))
                elif fy == -1:
                    self.face_b(ex - .05, ex + .05, ey - .115, ztop + 2, ztop + 7, (24, 24, 34))
        if sk["acc"] == "ears":                        # oreilles de lapin
            for sgn in (-1, 1):
                ex, ey = x + px * sgn * .17 - fx * .06, y + py * sgn * .17 - fy * .06
                cube(ex - .07, ex + .07, ey - .07, ey + .07, ztop, ztop + 15 * sq, body)
                cube(ex - .03, ex + .03, ey - .03, ey + .03, ztop + 1, ztop + 12 * sq, belly)
        elif sk["acc"] == "beak":                      # bec de canard
            bx, by = x + fx * .4, y + fy * .4
            cube(bx - .11, bx + .11, by - .11, by + .11, ztop - 11 * sq, ztop - 5 * sq, foot)
        elif sk["acc"] == "ant":                       # antenne de robot
            cube(x - .04, x + .04, y - .04, y + .04, ztop, ztop + 11 * sq, (200, 60, 60))
            cube(x - .09, x + .09, y - .09, y + .09, ztop + 11 * sq, ztop + 16 * sq, (255, 90, 90))

    def draw_chicken(self, x, y, z0, sq=1.0, wide=1.0, face=(0, 1)):
        """Poulet blanc voxel : corps et tête cubiques, crête rouge, bec orange, yeux noirs,
        petites ailes, pattes jaunes. sq / wide = écrasement du saut (comme la grenouille).
        Les pièces sont dessinées de la plus lointaine à la plus proche : la caméra voit les
        faces y- et x+, donc le côté 'proche' et l'avant du poulet dépendent de son orientation."""
        sk, cube = self.skin_now(), self.cube
        fx, fy = face
        px, py = abs(fy), abs(fx)                      # axe latéral du poulet
        near = 1 if px == 1 else -1                    # côté latéral tourné vers la caméra
        far = -near
        fwd_near = (fx - fy) > 0                       # l'avant du poulet regarde vers la caméra
        white, wing, foot = sk["body"], sk["wing"], sk["foot"]
        comb, beak, eye = sk["comb"], sk["beak"], sk["eye"]

        K = CHICKEN_SCALE                               # taille globale du poulet (réglable dans settings.py)

        def box(a, s, hf, hl, za, zb, col):            # a = avant/arrière, s = côté, hf/hl = demi-tailles
            a, s, hf, hl, za, zb = a * K, s * K, hf * K, hl * K, za * K, zb * K
            cx, cy = x + fx * a + px * s, y + fy * a + py * s
            hx, hy = (hf, hl) if fx else (hl, hf)
            cube(cx - hx, cx + hx, cy - hy, cy + hy, z0 + za, z0 + zb, col)

        W = 0.29 * wide                                 # demi-largeur du corps (case = 1)
        lh = max(1.0, 8.5 * sq)                         # hauteur des pattes
        bh, hh = max(1.5, 15 * sq), max(1.5, 11 * sq)   # hauteur du corps / de la tête
        zb, zh = lh + bh, lh + bh + hh                  # sommet du corps / de la tête
        for sgn in (far, near):                         # pattes jaunes + petits pieds
            box(0, sgn * .13 * wide, .06, .06, 0, lh, foot)
            box(.09, sgn * .13 * wide, .12, .075, 0, max(1.0, 2.2 * sq), foot)
        box(-.02, far * (W + .035), .17, .035, lh + bh * .18, lh + bh * .78, wing)       # aile lointaine
        box(0, 0, W, W, lh, zb, white)                                                    # corps
        box(-.02, near * (W + .035), .17, .035, lh + bh * .18, lh + bh * .78, wing)      # aile proche
        ez0 = zb + hh * .45
        ez1 = ez0 + max(1.0, 3.5 * sq)
        beak_box = lambda: box(.29 + .075, 0, .075, .07 * wide, zb + hh * .28, zb + hh * .62, beak)
        if not fwd_near:
            beak_box()                                  # bec derrière la tête : dessiné avant elle
        box(.14, far * (.24 * wide + .02), .035, .025, ez0, ez1, eye)                     # œil lointain
        box(.05, 0, .24 * wide, .24 * wide, zb, zh, white)                                # tête
        box(.14, near * (.24 * wide + .02), .035, .025, ez0, ez1, eye)                    # œil proche
        if fwd_near:
            beak_box()                                  # bec devant la tête : dessiné après elle
        bumps = ((-.09, 5), (.02, 7), (.13, 4))         # crête rouge : trois créneaux
        for a, ch in (bumps if fwd_near else bumps[::-1]):
            box(a, 0, .05, .04 * wide, zh, zh + max(1.0, ch * sq), comb)

    def draw_drown_rings(self, zw):
        """Ronds dans l'eau quand le joueur se noie : au niveau de l'eau, donc SOUS les bûches et nénuphars."""
        p = self.p
        cx, cy = self.P(p.x, p.y, zw)
        for i in range(3):
            r = (self.dead_t * 1.1 + i * 0.33) % 1.0
            pygame.draw.ellipse(self.screen, (214, 238, 252),
                                (cx - r * 56, cy - r * 28, r * 112, r * 56), 2)

    def draw_player(self):
        p = self.p
        row = self.world.rows.get(round(p.y))
        gz = self.player_z()
        if self.state == "dead":
            gz = self.dead_gz
            if self.dead == "squash":
                self.draw_frog(p.x, p.y, gz, 0.14, 1.5, p.face)
                return
            if self.dead == "drown":
                sink = min(1.0, self.dead_t / 0.6)
                zw = ZT["river"] if (row and row.kind == "river") else ZT["pads"]
                cut = self.P(p.x + 0.3, p.y - 0.3, zw)[1]
                self.screen.set_clip((0, 0, W, int(cut)))
                if sink < 1:
                    self.draw_frog(p.x, p.y, gz - sink * 30, 1.0, 1.0, p.face)
                self.screen.set_clip(None)
                return                                   # les ronds sont dessinés par draw_row (sous les bûches)
        if row is not None:
            r_ = max(0.18, 0.33 - p.lift * 0.005)
            if self.skin_now().get("style") == "chicken":
                r_ *= CHICKEN_SCALE                      # ombre proportionnelle au poulet
            gc = shade(ground_color(row), 0.78)
            self.top_poly(p.x - r_, p.x + r_, p.y - r_, p.y + r_, gz, gc)
        sq, wd = self.hop_squash()
        self.draw_frog(p.x, p.y, gz + p.lift, sq, wd, p.face)

    # ---- rendu des rangées ----
    def copies(self, base, lo, hi):
        b = base % WRAP
        k0 = math.ceil((lo - b) / WRAP)
        k1 = math.floor((hi - b) / WRAP)
        return [b + k * WRAP for k in range(k0, k1 + 1)]

    def draw_row(self, row, with_player):
        t = self.t
        y = row.y
        lo, hi = self.xrange_(y)
        k = row.kind
        zt = ZT[k]
        xa, xb = lo - 6, hi + 6
        y0, y1 = y - .5, y + .5
        items = []
        if k == "grass":
            self.slab(xa, xb, y0, y1, zt, GRASS_C[y % 2])
            self.draw_borders(row, xa, xb, zt, GRASS_C[y % 2])
            for c in range(math.floor(lo) - 1, math.ceil(hi) + 2):
                tr = self.tree_at(row, c)
                if tr:
                    items.append((c, "tree", (c, tr)))
                elif abs(c) <= COL_MAX + 3 and (c * 31 + row.seed * 17) % 9 == 0:
                    items.append((c, "tuft", c))
            for c in row.coins:
                items.append((c, "coin", c))
        elif k == "road":
            self.slab(xa, xb, y0, y1, zt, ROAD_C[y % 2])
            self.draw_borders(row, xa, xb, zt, ROAD_C[y % 2])
            above = self.world.rows.get(y + 1)
            if above is not None and above.kind == "road":
                for xd in range(math.floor(lo / 2) * 2, math.ceil(hi) + 2, 2):
                    self.top_poly(xd, xd + 1.0, y1 - .05, y1 + .05, zt, (232, 232, 236))
            for v in row.items:
                if v.get("gone"):                # véhicule retiré pendant le passage de la police
                    continue
                for xv in self.copies(row.shift + v["off"], lo - 3, hi + 3):
                    items.append((xv, "veh", (xv, v)))
            for c in row.cops:                       # voiture de police (ne boucle pas)
                items.append((c["x"], "veh", (c["x"], c["v"])))
        elif k in ("river", "pads"):
            self.slab(xa, xb, y0, y1, zt, WATER_C[y % 2])
            self.draw_borders(row, xa, xb, zt, WATER_C[y % 2])
            for i in range(9):
                xw = lo - 4 + ((i * 7.3 + row.seed * 0.37 + t * 0.9 * (1 if i % 2 else -1)) % (hi - lo + 8))
                yw = y - .32 + ((i * 0.23 + row.seed * 0.011) % 0.64)
                self.top_poly(xw, xw + 0.9, yw, yw + .07, zt, (176, 224, 248))
            self.draw_foam(row, lo, hi, zt)
            if k == "pads":
                for c in row.pads:
                    items.append((c, "pad", c))
            else:
                for idx, (c, ln) in enumerate(row.logs):
                    for xv in self.copies(row.shift + c, lo - 5, hi + 5):
                        items.append((xv, "log", (xv, ln, c, idx)))
        elif k == "rail":
            self.slab(xa, xb, y0, y1, zt, RAIL_C)
            self.draw_borders(row, xa, xb, zt, RAIL_C)
            for xs in range(math.floor(lo * 2) - 1, math.ceil(hi * 2) + 2):
                xs /= 2.0
                self.cube(xs - .09, xs + .09, y - .42, y + .42, zt, zt + 2, (124, 88, 58))
            self.cube(xa, xb, y - .30, y - .22, zt + 2, zt + 4, (204, 204, 214))
            self.cube(xa, xb, y + .22, y + .30, zt + 2, zt + 4, (204, 204, 214))
            items.append((RAIL_SIGNAL_X, "pole", None))
            if row.state == "pass":
                for i in range(8):
                    items.append((row.front - row.dir * (1 + 2 * i), "train", (i, row.front - row.dir * (1 + 2 * i))))
        under = None                                   # véhicule / train qui a écrasé le joueur
        if with_player and self.state == "dead":
            if self.dead == "drown":
                self.draw_drown_rings(ZT["river"] if k == "river" else ZT["pads"])   # avant tous les objets : sous les bûches
            elif self.dead == "squash":
                best = 9.0
                for it in items:
                    if it[1] == "veh":
                        xv, half = it[2][0], it[2][1]["len"] / 2 + .5
                    elif it[1] == "train":
                        xv, half = it[2][1], .97 + .5
                    else:
                        continue
                    dx = abs(self.p.x - xv)
                    if dx <= half and dx < best:
                        best, under = dx, it
        if with_player and under is None:
            kx = self.p.x
            if k == "river":                       # le joueur est dessiné APRÈS la bûche qui le porte
                for it in items:
                    if it[1] == "log":
                        xv, ln = it[2][0], it[2][1]
                        if xv - ln / 2 - .15 <= self.p.x <= xv + ln / 2 + .15:
                            kx = max(kx, xv + 1e-3)
            items.append((kx, "player", None))
        items.sort(key=lambda it: it[0])
        for item in items:
            xk, kind, data = item
            if kind == "tree":
                c, (layers, tint) = data
                self.top_poly(c - .38, c + .75, y - .4, y + .4, zt, shade(GRASS_C[y % 2], 0.8))
                self.draw_tree(c, y, zt, layers, tint)
            elif kind == "tuft":
                c = data
                col = (252, 252, 252) if (c + row.seed) % 2 else (252, 226, 90)
                self.cube(c - .06 + .2, c + .06 + .2, y - .06, y + .06, zt, zt + 4, col)
            elif kind == "coin":
                cx, cy = self.P(data, y, zt + 20 + math.sin(t * 3 + data) * 3)
                draw_coin(self.screen, cx, cy, t)
            elif kind == "veh":
                ln_ = 1.7 if data[1]["truck"] else (0.62 if data[1].get("small") else 0.85)
                self.top_poly(data[0] - ln_, data[0] + ln_ + .3, y - .42, y + .42, zt, shade(ROAD_C[y % 2], 0.7))
                if item is under:
                    self.draw_player()                 # écrasé : le joueur est SOUS le véhicule (entre l'ombre et la carrosserie)
                    self._skip |= self.draw_particles(lambda q: abs(q[1] - y) < .8)      # ... et son éclatement aussi
                self.draw_vehicle(data[0], y, row.dir, data[1], zt)
            elif kind == "log":
                xv, ln, c, idx = data
                self.top_poly(xv - ln / 2, xv + ln / 2 + .25, y - .4, y + .4, zt, shade(WATER_C[y % 2], 0.8))
                self.draw_log(xv, ln, y, self.log_bob(row, idx))
            elif kind == "pad":
                c = data
                self.draw_pad(c, y, zt, (c * 7 + row.seed * 3 + y * 5) % 4)
                if (c * 5 + row.seed) % 4 == 0:
                    self.cube(c - .1, c + .1, y - .1, y + .1, zt + 2, zt + 7, (255, 150, 190))
            elif kind == "pole":
                self.cube(xk - .06, xk + .06, y - .44, y - .32, zt, zt + 40, (96, 96, 108))
                self.cube(xk - .16, xk + .16, y - .46, y - .30, zt + 40, zt + 56, (34, 34, 42))
                on1 = row.state == "warn" and int(t * 6) % 2 == 0
                on2 = row.state == "warn" and int(t * 6) % 2 == 1
                self.face_b(xk - .12, xk - .02, y - .46, zt + 44, zt + 52, (255, 70, 70) if on1 else (96, 34, 34))
                self.face_b(xk + .02, xk + .12, y - .46, zt + 44, zt + 52, (255, 70, 70) if on2 else (96, 34, 34))
            elif kind == "train":
                i, c = data
                if item is under:
                    self.draw_player()                 # écrasé par le train : dessiné avant lui
                    self._skip |= self.draw_particles(lambda q: abs(q[1] - y) < .8)
                col = (206, 52, 52) if i == 0 else [(72, 112, 192), (232, 192, 62), (92, 162, 112)][i % 3]
                self.cube(c - .97, c + .97, y - .42, y + .42, zt + 2, zt + 36, col)
                self.face_b(c - .8, c + .8, y - .42, zt + 20, zt + 30, WINDOW)
                if i == 0:
                    front_x = c + row.dir * .97
                    if row.dir > 0:
                        self.face_a(front_x, y - .34, y + .34, zt + 6, zt + 12, (255, 238, 140))
            elif kind == "player":
                self.draw_player()

    # ---- texte, scène complète, HUD ----
    def text(self, txt, font, pos, color=(255, 255, 255), anchor="center"):
        img = font.render(txt, True, color)
        out = font.render(txt, True, (20, 24, 30))
        w, h = img.get_width(), img.get_height()
        if anchor == "center":
            x, y = pos[0] - w / 2, pos[1] - h / 2
        elif anchor == "right":
            x, y = pos[0] - w, pos[1]
        elif anchor == "top":
            x, y = pos[0] - w / 2, pos[1]
        else:
            x, y = pos
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2), (-2, -2)):
            self.screen.blit(out, (x + ox, y + oy))
        self.screen.blit(img, (x, y))

    def draw_particles(self, pred=None, skip=None):
        """Dessine les particules (filtrables) ; renvoie les identifiants dessinés."""
        drawn = set()
        for q in self.parts:
            if (pred and not pred(q)) or (skip and id(q) in skip):
                continue
            sx, sy = self.P(q[0], q[1], q[2])
            r = max(1, int(5 * (1 - q[6] / q[7]) + 1))
            pygame.draw.rect(self.screen, q[8], (sx - r, sy - r, 2 * r, 2 * r))
            drawn.add(id(q))
        return drawn

    def draw(self):
        s = self.screen
        self._skip = set()
        s.fill((104, 176, 74))
        w, p = self.world, self.p
        prow = round(p.y)
        eagle = self.state == "dead" and self.dead == "eagle"
        for y in range(int(self.cam_y) + 22, int(self.cam_y) - 15, -1):
            row = w.rows.get(y)
            if row is None:
                continue
            self.draw_row(row, y == prow and not eagle)
        if eagle:
            tt, gz = self.dead_t, self.dead_gz
            row = w.rows.get(prow)
            if tt < 0.45:
                f = tt / 0.45
                r_ = 0.3 + 1.0 * f
                if row is not None:
                    self.top_poly(p.x - r_, p.x + r_, p.y - r_, p.y + r_, gz, shade(ground_color(row), 0.74))
                self.draw_frog(p.x, p.y, gz, 1.0, 1.0, p.face)
                ex, ey = self.P(p.x, p.y, gz + 34)
                draw_eagle(s, ex, -80 + (ey - 30 + 80) * f, self.t)
            else:
                rise = (tt - 0.45) * 700
                self.draw_frog(p.x, p.y, gz + rise, 1.0, 1.0, p.face)
                ex, ey = self.P(p.x, p.y, gz + rise + 34)
                draw_eagle(s, ex, ey - 30, self.t)
        if self.state == "play" and self.occluded():
            ghost = pygame.Surface((W, H), pygame.SRCALPHA)
            real, self.screen = self.screen, ghost
            self.draw_frog(p.x, p.y, self.player_z() + p.lift, 1.0, 1.0, p.face)
            self.screen = real
            ghost.set_alpha(135)
            real.blit(ghost, (0, 0))
        self.draw_particles(skip=self._skip)             # particules restantes (celles sous un véhicule sont déjà dessinées)
        self.draw_hud()

    def occluded(self):
        """Vrai si un arbre d'une rangée plus proche peut cacher la grenouille."""
        p = self.p
        for dy in (1, 2):
            row = self.world.rows.get(round(p.y) - dy)
            if row is not None and row.kind == "grass":
                for c in row.trees:
                    if abs(c - p.x - dy * AY / AX) <= 1.0 and row.trees[c][0] >= 1:
                        return True
        return False

    def draw_hud(self):
        s = self.screen
        if self.state in ("play", "dead"):
            self.text(str(int(self.p.max_y)), self.f_big, (18, 8), anchor="left")
        self.text("Meilleur : %d" % self.best, self.f_small, (20, 78), anchor="left")
        draw_coin(s, W - 28, 28, self.t)
        self.text(str(self.coins), self.f_mid, (W - 46, 10), anchor="right")
        if self.state in ("play", "dead"):
            self.text("Niveau %d" % self.level, self.f_small, (W // 2, 10), (255, 240, 120), anchor="top")
        if self.ai_enabled and self.state in ("play", "dead"):
            self.text("IA active - I pour reprendre", self.f_small, (20, 108), (170, 255, 170), anchor="left")
        if self.state == "play" and self.t - self.lvl_t < 1.6:
            self.text("NIVEAU %d !" % self.level, self.f_mid, (W // 2, 300), (255, 240, 120))
        if self.state == "title":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 90))
            s.blit(ov, (0, 0))
            self.text("CROSSY ROAD", self.f_big, (W // 2, 170), (255, 240, 120))
            self.text("Traverse sans te faire écraser !", self.f_mid, (W // 2, 244))
            sk = SKINS[self.skin_i]
            lock = "" if sk["name"] in self.owned else "  -  verrouillé : %d pièces" % sk["price"]
            self.text("C : personnage  >  %s%s" % (sk["name"], lock), self.f_small, (W // 2, 540),
                      (255, 220, 80) if not lock else (255, 140, 140))
            self.text("ESPACE ou flèches ", self.f_mid, (W // 2, 590))
            self.text("pour commencer !", self.f_mid, (W // 2, 630))
            self.text("Flèches / ZQSD / WASD  -  I : activer l'IA", self.f_small, (W // 2, 680))
            self.text("P : pause  -  R : rejouer", self.f_small, (W // 2, 714))
        elif self.state == "dead" and self.dead_t > (1.3 if self.dead == "eagle" else 0.8):
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 120))
            s.blit(ov, (0, 0))
            self.text("PERDU !", self.f_big, (W // 2, 230), (255, 110, 110))
            self.text("Score : %d" % int(self.p.max_y), self.f_mid, (W // 2, 320))
            self.text("Meilleur : %d" % self.best, self.f_mid, (W // 2, 368))
            if self.run_coins:
                self.text("+%d pièce(s)" % self.run_coins, self.f_small, (W // 2, 412), (255, 220, 80))
            self.text("ESPACE pour rejouer", self.f_mid, (W // 2, 500))
        elif self.paused:
            self.text("PAUSE", self.f_big, (W // 2, H // 2))
