#!/usr/bin/env python3
"""Builds the isometric building illustrations used by the sector showcase.

    python3 tools/sector-art/build.py

writes public/assets/sectors/<sector>.svg. Each scene is described in world
units (roughly metres: x runs to the right-front, z to the left-front, y up) and
drawn back to front, so later shapes sit in front of earlier ones. Strokes use
non-scaling-stroke, so outlines stay crisp at any display size.
"""
import math
import os

C, S = math.cos(math.pi / 6), 0.5
VIEW_W, VIEW_H, PAD = 1600, 1000, 70
OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'public', 'assets', 'sectors'))

# ---------------------------------------------------------------- palette
INK = '#2A2B30'
ROOF = '#FFFFFF'
ROOF_IN = '#EEEFF2'
WALL_L = '#F6F6F8'
WALL_R = '#E1E2E7'
GLASS = '#C9D6E1'
GLASS_D = '#9DB2C3'
DOOR = '#5C606A'
SHUTTER = '#D9DBE1'
PV = '#F8632C'
PV_LINE = '#FFC2A3'
PV_EDGE = '#B93E0B'
SLAB_TOP = '#F2F2F4'
SLAB_L = '#E6E6EA'
SLAB_R = '#D8D9DE'
GRASS = '#E3EBDC'
ROAD = '#E4E4E8'
PAVE = '#ECECEF'
LINE_W = '#FFFFFF'
LEAF = '#A8BE9E'
LEAF_HI = '#C6D6BE'
TRUNK = '#8C7B6B'
SHADOW = 'rgba(24,26,34,.075)'


def iso(p):
    x, y, z = p
    return ((x - z) * C, (x + z) * S - y)


def hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class Scene:
    def __init__(self, title):
        self.title = title
        self.items = []

    # ------------------------------------------------------------ primitives
    def poly(self, pts, fill, stroke=INK, sw=1.0, op=None):
        self.items.append(('poly', pts, dict(fill=fill, stroke=stroke, sw=sw, op=op)))

    def segs(self, segments, stroke, sw=0.6, dash=None, op=None):
        """Many line segments emitted as one path."""
        if segments:
            self.items.append(('segs', segments, dict(stroke=stroke, sw=sw, dash=dash, op=op)))

    def raw(self, pts, fn):
        """fn(M, k) -> svg string, where M maps world -> view and k is the view scale."""
        self.items.append(('raw', pts, fn))

    # ------------------------------------------------------------ ground
    def slab(self, x0, z0, x1, z1, t=1.6):
        # soft contact shadow under the whole diorama
        foot = [(x0, -t, z0), (x1, -t, z0), (x1, -t, z1), (x0, -t, z1)]
        self.raw(foot, lambda M, k, f=foot: '<polygon points="%s" fill="rgba(20,22,30,.16)" filter="url(#soft)"/>' % pts_attr(M, [(p[0] + 2.0, p[1] - 1.2, p[2] + 2.0) for p in f]))
        self.poly([(x1, 0, z0), (x1, 0, z1), (x1, -t, z1), (x1, -t, z0)], SLAB_R, sw=1)
        self.poly([(x0, 0, z1), (x1, 0, z1), (x1, -t, z1), (x0, -t, z1)], SLAB_L, sw=1)
        self.poly([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)], SLAB_TOP, sw=1)

    def flat(self, x0, z0, x1, z1, fill, stroke=None, sw=0.8, y=0.02):
        self.poly([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], fill, stroke=stroke, sw=sw)

    def road_x(self, x0, x1, z0, z1, dashed=True):
        self.flat(x0, z0, x1, z1, ROAD)
        if dashed:
            zm, segs, x = (z0 + z1) / 2, [], x0 + 1
            while x + 2.2 < x1:
                segs.append(((x, 0.05, zm), (x + 2.2, 0.05, zm)))
                x += 4.4
            self.segs(segs, LINE_W, sw=1.4)

    def road_z(self, z0, z1, x0, x1, dashed=True):
        self.flat(x0, z0, x1, z1, ROAD)
        if dashed:
            xm, segs, z = (x0 + x1) / 2, [], z0 + 1
            while z + 2.2 < z1:
                segs.append(((xm, 0.05, z), (xm, 0.05, z + 2.2)))
                z += 4.4
            self.segs(segs, LINE_W, sw=1.4)

    def bays_x(self, x0, x1, z0, depth, step=2.6):
        """Parking bay lines along x, bays running in +z."""
        segs, x = [], x0
        while x <= x1 + 0.01:
            segs.append(((x, 0.05, z0), (x, 0.05, z0 + depth)))
            x += step
        self.segs(segs, LINE_W, sw=1.2)

    def shadow_box(self, x0, z0, x1, z1, h, k=0.55):
        dx = h * k
        foot = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
        moved = [(x + dx, z - dx * 0.35) for x, z in foot]
        hl = hull(foot + moved)
        self.poly([(x, 0.03, z) for x, z in hl], SHADOW, stroke=None)

    # ------------------------------------------------------------ building parts
    def box(self, x0, z0, w, d, h, y0=0.0, top=ROOF, left=WALL_L, right=WALL_R, sw=1.0, draw_top=True):
        x1, z1, y1 = x0 + w, z0 + d, y0 + h
        self.poly([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], right, sw=sw)
        self.poly([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], left, sw=sw)
        if draw_top:
            self.poly([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], top, sw=sw)

    def parapet(self, x0, z0, x1, z1, y, inset=0.7):
        self.poly([(x0 + inset, y, z0 + inset), (x1 - inset, y, z0 + inset), (x1 - inset, y, z1 - inset), (x0 + inset, y, z1 - inset)], ROOF_IN, sw=0.7)

    def ribbons_left(self, x0, x1, z, floors, fh, y0=0.0, sill=1.0, wh=1.6, margin=1.2, step=1.6, first=0):
        for f in range(first, floors):
            ya = y0 + f * fh + sill
            yb = ya + wh
            xa, xb = x0 + margin, x1 - margin
            self.poly([(xa, ya, z), (xb, ya, z), (xb, yb, z), (xa, yb, z)], GLASS, sw=0.7)
            segs, x = [], xa + step
            while x < xb - 0.2:
                segs.append(((x, ya, z), (x, yb, z)))
                x += step
            self.segs(segs, GLASS_D, sw=0.6)

    def ribbons_right(self, z0, z1, x, floors, fh, y0=0.0, sill=1.0, wh=1.6, margin=1.2, step=1.6, first=0):
        for f in range(first, floors):
            ya = y0 + f * fh + sill
            yb = ya + wh
            za, zb = z0 + margin, z1 - margin
            self.poly([(x, ya, za), (x, ya, zb), (x, yb, zb), (x, yb, za)], GLASS, sw=0.7)
            segs, z = [], za + step
            while z < zb - 0.2:
                segs.append(((x, ya, z), (x, yb, z)))
                z += step
            self.segs(segs, GLASS_D, sw=0.6)

    def punched_left(self, x0, x1, z, floors, fh, y0=0.0, ww=1.4, wh=1.6, sill=0.9, gap=1.3, margin=1.2, balcony=False):
        n = max(1, int((x1 - x0 - 2 * margin + gap) // (ww + gap)))
        span = n * ww + (n - 1) * gap
        start = x0 + (x1 - x0 - span) / 2
        for f in range(floors):
            ya = y0 + f * fh + sill
            for i in range(n):
                xa = start + i * (ww + gap)
                self.poly([(xa, ya, z), (xa + ww, ya, z), (xa + ww, ya + wh, z), (xa, ya + wh, z)], GLASS, sw=0.6)
                if balcony and f > 0 and i % 2 == 0:
                    bw = ww + 0.9
                    bx = xa - 0.45
                    by = y0 + f * fh + 0.05
                    self.box(bx, z, bw, 0.9, 0.18, y0=by, top='#FFFFFF', left='#E8E9ED', right='#D5D6DC', sw=0.6)
                    self.poly([(bx, by + 0.18, z + 0.9), (bx + bw, by + 0.18, z + 0.9), (bx + bw, by + 0.95, z + 0.9), (bx, by + 0.95, z + 0.9)], 'rgba(201,214,225,.55)', stroke=GLASS_D, sw=0.5)

    def punched_right(self, z0, z1, x, floors, fh, y0=0.0, ww=1.4, wh=1.6, sill=0.9, gap=1.3, margin=1.2):
        n = max(1, int((z1 - z0 - 2 * margin + gap) // (ww + gap)))
        span = n * ww + (n - 1) * gap
        start = z0 + (z1 - z0 - span) / 2
        for f in range(floors):
            ya = y0 + f * fh + sill
            for i in range(n):
                za = start + i * (ww + gap)
                self.poly([(x, ya, za), (x, ya, za + ww), (x, ya + wh, za + ww), (x, ya + wh, za)], GLASS, sw=0.6)

    def curtain_left(self, x0, x1, z, y0, y1, step_x=2.0, step_y=None):
        self.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], GLASS, sw=0.8)
        segs, x = [], x0 + step_x
        while x < x1 - 0.2:
            segs.append(((x, y0, z), (x, y1, z)))
            x += step_x
        if step_y:
            y = y0 + step_y
            while y < y1 - 0.2:
                segs.append(((x0, y, z), (x1, y, z)))
                y += step_y
        self.segs(segs, GLASS_D, sw=0.6)

    def door_left(self, xa, w, h, z, fill=DOOR):
        self.poly([(xa, 0, z), (xa + w, 0, z), (xa + w, h, z), (xa, h, z)], fill, sw=0.7)

    def shutter_left(self, xa, w, h, z):
        self.poly([(xa, 0, z), (xa + w, 0, z), (xa + w, h, z), (xa, h, z)], SHUTTER, sw=0.8)
        segs, y = [], 0.45
        while y < h - 0.1:
            segs.append(((xa, y, z), (xa + w, y, z)))
            y += 0.45
        self.segs(segs, '#B9BCC4', sw=0.5)

    def shutter_right(self, za, w, h, x):
        self.poly([(x, 0, za), (x, 0, za + w), (x, h, za + w), (x, h, za)], SHUTTER, sw=0.8)
        segs, y = [], 0.45
        while y < h - 0.1:
            segs.append(((x, y, za), (x, y, za + w)))
            y += 0.45
        self.segs(segs, '#B9BCC4', sw=0.5)

    # ------------------------------------------------------------ solar
    def pv_rows(self, x0, x1, z0, z1, y, row=2.1, gap=1.5, tilt=0.85, module=2.1):
        """Rows of tilted modules on a flat roof, facing +z, drawn back to front."""
        z = z0
        while z + row <= z1 + 0.01:
            back, front = z, z + row
            # strip of shade behind each row
            self.poly([(x0, y + 0.01, back - 0.7), (x1, y + 0.01, back - 0.7), (x1, y + 0.01, back), (x0, y + 0.01, back)], 'rgba(30,32,40,.07)', stroke=None)
            a, b = (x0, y + tilt, back), (x1, y + tilt, back)
            c, d = (x1, y + 0.15, front), (x0, y + 0.15, front)
            self.poly([a, b, c, d], PV, stroke=PV_EDGE, sw=0.8)
            segs = [(lerp(a, d, 0.5), lerp(b, c, 0.5))]
            n = max(1, round((x1 - x0) / module))
            for i in range(1, n):
                t = i / n
                segs.append((lerp(a, b, t), lerp(d, c, t)))
            self.segs(segs, PV_LINE, sw=0.6)
            # end of the row on the right
            self.poly([(x1, y + 0.15, front), (x1, y + tilt, back), (x1, y, back), (x1, y, front)], '#9C3A10', stroke=PV_EDGE, sw=0.5)
            z += row + gap

    def pv_plane(self, a, b, c, d, u0=0.06, u1=0.94, v0=0.1, v1=0.9, cols=8, rows=3):
        """Module grid on a sloped plane: a,b low edge (left, right), d,c high edge (left, right)."""
        def at(u, v):
            return lerp(lerp(a, b, u), lerp(d, c, u), v)
        q = [at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)]
        self.poly(q, PV, stroke=PV_EDGE, sw=0.8)
        segs = []
        for i in range(1, cols):
            u = u0 + (u1 - u0) * i / cols
            segs.append((at(u, v0), at(u, v1)))
        for j in range(1, rows):
            v = v0 + (v1 - v0) * j / rows
            segs.append((at(u0, v), at(u1, v)))
        self.segs(segs, PV_LINE, sw=0.6)

    def carport(self, x0, x1, z0, z1, h=3.2, tilt=0.8):
        posts = []
        x = x0 + 1
        while x < x1:
            posts.append(((x, 0, (z0 + z1) / 2), (x, h, (z0 + z1) / 2)))
            x += 6
        self.segs(posts, '#7E838D', sw=1.2)
        a, b = (x0, h + tilt, z0), (x1, h + tilt, z0)
        c, d = (x1, h, z1), (x0, h, z1)
        self.poly([a, b, c, d], PV, stroke=PV_EDGE, sw=0.9)
        segs = [(lerp(a, d, 0.5), lerp(b, c, 0.5))]
        n = max(1, round((x1 - x0) / 2.1))
        for i in range(1, n):
            segs.append((lerp(a, b, i / n), lerp(d, c, i / n)))
        self.segs(segs, PV_LINE, sw=0.6)
        self.poly([(x1, h, z1), (x1, h + tilt, z0), (x1, h - 0.25, z0), (x1, h - 0.25, z1)], '#9C3A10', stroke=PV_EDGE, sw=0.5)

    # ------------------------------------------------------------ roofs
    def saw_roof(self, x0, z0, x1, z1, h, teeth, rise, pv=True):
        tw = (z1 - z0) / teeth
        for i in range(teeth):
            za, zb = z0 + i * tw, z0 + (i + 1) * tw
            low_l, low_r = (x0, h, zb), (x1, h, zb)
            high_l, high_r = (x0, h + rise, za), (x1, h + rise, za)
            self.poly([low_l, low_r, high_r, high_l], ROOF, sw=1)
            if pv:
                self.pv_plane(low_l, low_r, high_r, high_l, u0=0.04, u1=0.96, v0=0.12, v1=0.86, cols=int((x1 - x0) / 2.2), rows=3)
            self.poly([(x1, h, za), (x1, h + rise, za), (x1, h, zb)], WALL_R, sw=1)

    def gable_x(self, x0, z0, x1, z1, h, rise, pv=True, cols=10, rows=3):
        zm = (z0 + z1) / 2
        self.poly([(x0, h, z0), (x1, h, z0), (x1, h + rise, zm), (x0, h + rise, zm)], '#E9EAEE', sw=1)
        front = [(x0, h, z1), (x1, h, z1), (x1, h + rise, zm), (x0, h + rise, zm)]
        self.poly(front, ROOF, sw=1)
        if pv:
            self.pv_plane(*front, u0=0.05, u1=0.95, v0=0.12, v1=0.88, cols=cols, rows=rows)
        self.poly([(x1, h, z0), (x1, h, z1), (x1, h + rise, zm)], WALL_R, sw=1)

    def gable_z(self, x0, z0, x1, z1, h, rise, pv=True, cols=10, rows=3):
        xm = (x0 + x1) / 2
        self.poly([(x0, h, z1), (x0, h, z0), (xm, h + rise, z0), (xm, h + rise, z1)], '#E9EAEE', sw=1)
        right = [(x1, h, z1), (x1, h, z0), (xm, h + rise, z0), (xm, h + rise, z1)]
        self.poly(right, ROOF, sw=1)
        if pv:
            # a = low-left (front), b = low-right (back) as seen on this slope
            self.pv_plane(right[0], right[1], right[2], right[3], u0=0.05, u1=0.95, v0=0.12, v1=0.88, cols=cols, rows=rows)
        self.poly([(x0, h, z1), (x1, h, z1), (xm, h + rise, z1)], WALL_L, sw=1)

    # ------------------------------------------------------------ round things
    def cylinder(self, cx, cz, r, h, y0=0.0, fill='url(#cyl)', top='#FFFFFF', cone=0.0, rings=0, glass=False):
        pts = [(cx + r, y0, cz + r), (cx - r, y0, cz - r), (cx + r, y0 + h + cone, cz + r), (cx - r, y0 + h + cone, cz - r),
               (cx + r, y0, cz - r), (cx - r, y0, cz + r)]

        def fn(M, k):
            bx, by = M((cx, y0, cz))
            tx, ty = M((cx, y0 + h, cz))
            rx, ry = r * math.sqrt(2) * C * k, r * math.sqrt(2) * S * k
            body = ('<path d="M%.1f %.1f L%.1f %.1f A%.1f %.1f 0 0 0 %.1f %.1f L%.1f %.1f A%.1f %.1f 0 0 1 %.1f %.1f Z" '
                    'fill="%s" %s/>') % (tx - rx, ty, bx - rx, by, rx, ry, bx + rx, by, tx + rx, ty, rx, ry, tx - rx, ty,
                                        ('url(#glassg)' if glass else fill), stroke_attr(INK, 1.0))
            out = [body]
            for i in range(1, rings + 1):
                yy = y0 + h * i / (rings + 1)
                rx2, ry2 = M((cx, yy, cz))
                out.append('<path d="M%.1f %.1f A%.1f %.1f 0 0 0 %.1f %.1f" fill="none" %s/>' % (rx2 - rx, ry2, rx, ry, rx2 + rx, ry2, stroke_attr('#9EA3AD', 0.6)))
            if cone:
                ax, ay = M((cx, y0 + h + cone, cz))
                out.append('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f A%.1f %.1f 0 0 1 %.1f %.1f Z" fill="url(#cone)" %s/>' % (
                    tx - rx, ty, ax, ay, tx + rx, ty, rx, ry, tx - rx, ty, stroke_attr(INK, 1.0)))
            else:
                out.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" %s/>' % (tx, ty, rx, ry, top, stroke_attr(INK, 1.0)))
            return ''.join(out)
        self.raw(pts, fn)

    def ring_on_roof(self, cx, cz, r, y, label_h=True):
        pts = [(cx + r, y, cz + r), (cx - r, y, cz - r)]

        def fn(M, k):
            x, yv = M((cx, y + 0.02, cz))
            rx, ry = r * math.sqrt(2) * C * k, r * math.sqrt(2) * S * k
            s = '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#E6E7EB" %s/>' % (x, yv, rx, ry, stroke_attr(INK, 0.8))
            s += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="none" %s/>' % (x, yv, rx * 0.78, ry * 0.78, stroke_attr('#FFFFFF', 1.6))
            if label_h:
                hs = r * 0.42
                segs = [((cx - hs, y, cz + hs * 0.0 - hs), (cx - hs, y, cz + hs)), ((cx + hs, y, cz - hs), (cx + hs, y, cz + hs)),
                        ((cx - hs, y, cz), (cx + hs, y, cz))]
                d = ''.join('M%.1f %.1f L%.1f %.1f ' % (*M(a), *M(b)) for a, b in segs)
                s += '<path d="%s" fill="none" %s/>' % (d, stroke_attr('#FFFFFF', 2.4))
            return s
        self.raw(pts, fn)

    def tree(self, x, z, s=1.0):
        s *= 1.25
        pts = [(x - 3 * s, 0, z - 3 * s), (x + 3 * s, 0, z + 3 * s), (x, 6.5 * s, z)]

        def fn(M, k):
            gx, gy = M((x, 0, z))
            sx, sy = M((x + 1.3 * s, 0.02, z - 1.3 * s * 0.35))
            cx_, cy_ = M((x, 3.9 * s, z))
            r = 2.1 * s * k
            out = '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>' % (sx, sy, r * 1.05, r * 0.5, SHADOW)
            out += '<path d="M%.1f %.1f L%.1f %.1f" %s/>' % (gx, gy, cx_, cy_ + r * 0.4, stroke_attr(TRUNK, 1.6))
            out += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" %s/>' % (cx_, cy_, r, LEAF, stroke_attr('#7E9573', 0.8))
            out += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (cx_ - r * 0.28, cy_ - r * 0.3, r * 0.52, LEAF_HI)
            return out
        self.raw(pts, fn)

    # ------------------------------------------------------------ vehicles
    def car(self, x, z, along='x', color='#FFFFFF'):
        L, W = 4.2, 1.8
        tones = {'#FFFFFF': ('#FFFFFF', '#ECEDF0', '#D9DADF'), 'grey': ('#C4C7CE', '#B2B5BD', '#9EA2AB'),
                 'dark': ('#5A5F6A', '#4C515B', '#3E424B'), 'orange': ('#FF8A55', '#F8632C', '#D9531F')}
        top, left, right = tones.get(color, tones['#FFFFFF'])
        if along == 'x':
            self.box(x, z, L, W, 0.8, y0=0.25, top=top, left=left, right=right, sw=0.6)
            self.box(x + 0.9, z + 0.15, 2.2, W - 0.3, 0.6, y0=1.05, top=top, left='#B9C7D3', right='#A4B4C2', sw=0.6)
        else:
            self.box(x, z, W, L, 0.8, y0=0.25, top=top, left=left, right=right, sw=0.6)
            self.box(x + 0.15, z + 0.9, W - 0.3, 2.2, 0.6, y0=1.05, top=top, left='#B9C7D3', right='#A4B4C2', sw=0.6)

    def truck_z(self, x, z, length=12.0):
        """Articulated lorry pointing +z (cab at the front)."""
        self.box(x, z, 2.5, length, 3.6, y0=1.0, top='#FFFFFF', left='#F3F4F6', right='#DDDFE4', sw=0.8)
        self.box(x, z + length + 0.4, 2.5, 2.4, 2.4, y0=0.7, top='#4A4E57', left='#3D414A', right='#30343C', sw=0.8)
        self.poly([(x + 0.2, 2.0, z + length + 2.8), (x + 2.3, 2.0, z + length + 2.8), (x + 2.3, 2.9, z + length + 2.8), (x + 0.2, 2.9, z + length + 2.8)], '#8FA3B4', sw=0.5)

    def truck_x(self, x, z, length=12.0):
        """Articulated lorry pointing +x (cab at the front)."""
        self.box(x, z, length, 2.5, 3.6, y0=1.0, top='#FFFFFF', left='#F3F4F6', right='#DDDFE4', sw=0.8)
        self.box(x + length + 0.4, z, 2.4, 2.5, 2.4, y0=0.7, top='#4A4E57', left='#3D414A', right='#30343C', sw=0.8)
        self.poly([(x + length + 2.8, 2.0, z + 0.2), (x + length + 2.8, 2.0, z + 2.3), (x + length + 2.8, 2.9, z + 2.3), (x + length + 2.8, 2.9, z + 0.2)], '#8FA3B4', sw=0.5)

    def plant(self, x, z, y, w=2.4, d=1.8, h=1.2):
        self.box(x, z, w, d, h, y0=y, top='#F7F7F9', left='#E4E5EA', right='#CFD1D7', sw=0.7)
        cx, cz = x + w / 2, z + d / 2
        self.cylinder(cx, cz, min(w, d) * 0.28, 0.12, y0=y + h, top='#C9CCD3')

    # ------------------------------------------------------------ output
    def svg(self):
        pts = []
        for kind, data, _ in self.items:
            pts.extend(data)
        iso_pts = [iso(p) for p in pts]
        minx = min(p[0] for p in iso_pts)
        maxx = max(p[0] for p in iso_pts)
        miny = min(p[1] for p in iso_pts)
        maxy = max(p[1] for p in iso_pts)
        k = min((VIEW_W - 2 * PAD) / (maxx - minx), (VIEW_H - 2 * PAD) / (maxy - miny))
        offx = (VIEW_W - (maxx - minx) * k) / 2 - minx * k
        offy = (VIEW_H - (maxy - miny) * k) / 2 - miny * k

        def M(p):
            ix, iy = iso(p)
            return (ix * k + offx, iy * k + offy)

        body = []
        for kind, data, style in self.items:
            if kind == 'poly':
                body.append('<polygon points="%s" fill="%s"%s%s/>' % (
                    pts_attr(M, data), style['fill'],
                    (' ' + stroke_attr(style['stroke'], style['sw'])) if style['stroke'] else '',
                    (' opacity="%s"' % style['op']) if style['op'] else ''))
            elif kind == 'segs':
                d = ''.join('M%.1f %.1f L%.1f %.1f ' % (*M(a), *M(b)) for a, b in zip(data[0::2], data[1::2]))
                body.append('<path d="%s" fill="none" %s%s/>' % (d.strip(), stroke_attr(style['stroke'], style['sw']),
                                                                (' stroke-dasharray="%s"' % style['dash']) if style['dash'] else ''))
            else:
                body.append(style(M, k))
        defs = ('<defs>'
                '<linearGradient id="cyl" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#FAFAFB"/><stop offset=".55" stop-color="#ECEDF0"/><stop offset="1" stop-color="#D3D5DB"/></linearGradient>'
                '<linearGradient id="cone" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#DADCE1"/></linearGradient>'
                '<linearGradient id="glassg" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#DCE6EE"/><stop offset="1" stop-color="#A9BDCC"/></linearGradient>'
                '<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="14"/></filter>'
                '</defs>')
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" aria-label="%s">'
                '<title>%s</title>%s%s</svg>\n') % (VIEW_W, VIEW_H, self.title, self.title, defs, ''.join(body))


def stroke_attr(color, sw):
    return 'stroke="%s" stroke-width="%s" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"' % (color, sw)


def pts_attr(M, pts):
    return ' '.join('%.1f,%.1f' % M(p) for p in pts)


def flatten_segs(scene):
    """segs items store [(a,b), ...]; flatten to a,b,a,b for bbox + output."""
    out = []
    for kind, data, style in scene.items:
        if kind == 'segs':
            flat = []
            for a, b in data:
                flat.extend([a, b])
            out.append((kind, flat, style))
        else:
            out.append((kind, data, style))
    scene.items = out
    return scene


# ====================================================================== scenes

def industrial():
    s = Scene('Manufacturing plant with solar panels on its sawtooth roof')
    s.slab(-8, -6, 92, 60)
    s.road_x(-8, 92, 52, 59)
    s.flat(-8, 44, 30, 52, PAVE)
    s.flat(64, 40, 92, 52, PAVE)
    s.bays_x(66, 90, 44.5, 6)
    s.flat(-8, -6, 92, -1, GRASS)
    s.shadow_box(0, 0, 60, 36, 12)
    s.shadow_box(60, 14, 76, 36, 13)
    # chimney behind the hall
    s.cylinder(10, 4, 1.4, 26, rings=2, top='#3F434C')
    # main hall with sawtooth roof
    s.box(0, 0, 60, 36, 8, draw_top=False)
    for i, xa in enumerate([6, 16, 26, 36]):
        s.shutter_left(xa, 6, 5.2, 36)
    s.door_left(48, 2.2, 2.6, 36)
    s.ribbons_right(2, 34, 60, 1, 4, sill=4.6, wh=1.6, margin=2, step=2.2)
    s.saw_roof(0, 0, 60, 36, 8, 4, 4.6)
    # office block
    s.box(60, 14, 16, 22, 12.6)
    s.ribbons_left(60, 76, 36, 3, 4.2, step=1.8)
    s.ribbons_right(14, 36, 76, 3, 4.2, step=1.8)
    s.parapet(60, 14, 76, 36, 12.6)
    s.pv_rows(61.6, 74.4, 16, 34.4, 12.62, row=2.0, gap=1.5)
    s.door_left(64, 3, 3.0, 36, fill='#7B8794')
    # yard
    s.truck_z(12, 38.5, length=10)
    s.truck_z(24, 39.5, length=9)
    for i, x in enumerate([66.5, 69.1, 74.3, 79.5, 84.7]):
        s.car(x + 0.2, 45.2, along='z', color=['#FFFFFF', 'grey', 'dark', '#FFFFFF', 'grey'][i])
    for x in [-3, 36, 46]:
        s.tree(x, 47, 1.0)
    for x in [70, 84]:
        s.tree(x, 61.5, 0.9)
    s.tree(88, 30, 1.1)
    s.tree(88, 20, 0.9)
    return s


def warehouse():
    s = Scene('Distribution warehouse with a large rooftop solar array and lorries at the loading docks')
    s.slab(-8, -6, 108, 72)
    s.flat(-8, -6, 108, -2, GRASS)
    s.flat(-8, 46, 98, 64, PAVE)
    s.road_x(-8, 108, 64, 71)
    s.flat(98, -2, 108, 64, GRASS)
    s.shadow_box(0, 0, 84, 46, 12)
    s.box(0, 0, 84, 46, 11.5)
    s.parapet(0, 0, 84, 46, 11.5)
    s.pv_rows(2.2, 81.8, 2.6, 43.6, 11.52, row=2.1, gap=1.35)
    # loading docks on the front
    for xa in range(6, 66, 8):
        s.shutter_left(xa, 4.6, 4.8, 46)
    s.ribbons_right(4, 42, 84, 1, 4, sill=7.6, wh=1.4, margin=2, step=2.4)
    # office pod
    s.shadow_box(84, 26, 96, 46, 8)
    s.box(84, 26, 12, 20, 8)
    s.ribbons_left(84, 96, 46, 2, 3.7, step=1.6)
    s.ribbons_right(26, 46, 96, 2, 3.7, step=1.8)
    s.parapet(84, 26, 96, 46, 8)
    s.pv_rows(85.4, 94.6, 27.6, 44.6, 8.02, row=2.0, gap=1.4)
    # lorries backed onto docks
    for xa in (14.1, 30.1, 46.1):
        s.truck_z(xa, 46.6, length=12)
    s.car(70, 55, along='x', color='grey')
    s.car(78, 58, along='x', color='#FFFFFF')
    s.tree(-3, 56, 1.1)
    for z in [6, 18, 30, 52]:
        s.tree(103, z, 1.0)
    return s


def agri():
    s = Scene('Farm and food production buildings with solar panels on the shed roofs, beside two grain silos')
    s.slab(-8, -15, 92, 44)
    s.flat(-8, 30, 92, 44, GRASS)
    segs = []
    for i in range(5):
        z = 32.5 + i * 2.6
        segs.append(((-6, 0.05, z), (60, 0.05, z)))
    s.segs(segs, '#CBD8C0', sw=1.2)
    s.flat(-8, 20, 92, 30, PAVE)
    s.flat(64, -15, 92, 20, PAVE)
    s.shadow_box(54, -10, 74, 22, 9)
    s.shadow_box(0, 0, 44, 18, 9)
    # silos at the back
    s.cylinder(74, -8, 3.2, 15, cone=3.2, rings=3)
    s.cylinder(84, -6, 3.2, 15, cone=3.2, rings=3)
    # long shed, ridge along x, panels on the front slope
    s.box(0, 0, 44, 18, 5.4, draw_top=False)
    for xa in (4, 14):
        s.shutter_left(xa, 5, 4.2, 18)
    s.ribbons_left(24, 42, 18, 1, 3, sill=2.6, wh=1.2, margin=0.6, step=1.6)
    s.gable_x(0, 0, 44, 18, 5.4, 4.2, cols=16, rows=3)
    # cross shed, ridge along z, panels on the right slope
    s.box(54, -10, 20, 32, 5.0, draw_top=False)
    s.shutter_right(-4, 6, 4.0, 74)
    s.shutter_right(8, 6, 4.0, 74)
    s.poly([(54, 0, 22), (74, 0, 22), (74, 5.0, 22), (54, 5.0, 22)], WALL_L, sw=1)
    s.shutter_left(60, 8, 4.4, 22)
    s.gable_z(54, -10, 74, 22, 5.0, 4.6, cols=12, rows=3)
    # tractor-ish utility vehicle and trees
    s.car(30, 23, along='x', color='orange')
    s.car(80, 10, along='z', color='grey')
    for x, z, k in [(-3, 24, 1.1), (86, 26, 1.1), (88, 14, 1.0), (50, 27, 0.9)]:
        s.tree(x, z, k)
    return s


def school():
    s = Scene('School buildings and sports hall with solar panels on their flat roofs')
    s.slab(-30, -8, 64, 50)
    s.flat(-30, 40, 64, 50, PAVE)
    # painted court
    s.flat(-26, 24, -6, 37, '#E8D9CF', stroke='#FFFFFF', sw=1.4)
    s.segs([((-16, 0.06, 24), (-16, 0.06, 37))], '#FFFFFF', sw=1.4)
    s.flat(-30, -8, 64, -3, GRASS)
    s.shadow_box(-26, -4, -4, 18, 11)
    s.shadow_box(0, 0, 52, 14, 8.6)
    s.shadow_box(38, 14, 52, 38, 8.6)
    # sports hall
    s.box(-26, -4, 22, 22, 10.5)
    s.parapet(-26, -4, -4, 18, 10.5)
    s.pv_rows(-24.4, -5.6, -2.4, 16.6, 10.52, row=2.0, gap=1.45)
    s.ribbons_left(-26, -4, 18, 1, 4, sill=6.8, wh=2.2, margin=1.6, step=2.2)
    s.door_left(-18, 3.2, 3.0, 18)
    # teaching block (two storeys)
    s.box(0, 0, 52, 14, 8.6)
    s.parapet(0, 0, 52, 14, 8.6)
    s.pv_rows(1.6, 50.4, 1.6, 12.4, 8.62, row=2.0, gap=1.4)
    s.ribbons_left(0, 52, 14, 2, 4.2, step=1.7)
    s.door_left(20, 4.2, 3.0, 14, fill='#7B8794')
    # wing
    s.box(38, 14, 14, 24, 8.6)
    s.parapet(38, 14, 52, 38, 8.6)
    s.pv_rows(39.6, 50.4, 15.6, 36.4, 8.62, row=2.0, gap=1.4)
    s.ribbons_left(38, 52, 38, 2, 4.2, step=1.7)
    s.ribbons_right(14, 38, 52, 2, 4.2, step=1.7)
    s.ribbons_right(0, 14, 52, 2, 4.2, step=1.7)
    for x, z, k in [(6, 30, 1.1), (18, 34, 0.9), (59, 20, 1.0), (59, 32, 1.1), (28, 30, 1.0)]:
        s.tree(x, z, k)
    for i, x in enumerate([2, 5, 8, 11]):
        s.car(x, 43.2, along='z', color=['grey', '#FFFFFF', 'dark', '#FFFFFF'][i])
    s.bays_x(1.4, 13.4, 42.8, 5, step=3.0)
    return s


def hospital():
    s = Scene('Hospital campus with a helipad and solar panels across its roofs')
    s.slab(-8, -8, 80, 61)
    s.flat(-8, 44, 80, 61, PAVE)
    s.road_x(-8, 80, 54, 60)
    s.flat(-8, -8, 80, -3, GRASS)
    s.shadow_box(0, 0, 60, 40, 30)
    # podium
    s.box(0, 0, 60, 40, 9.6)
    s.parapet(0, 0, 60, 40, 9.6)
    s.ribbons_left(0, 60, 40, 2, 4.4, step=1.8)
    s.ribbons_right(0, 40, 60, 2, 4.4, step=1.8)
    # tower on the podium
    s.box(8, 4, 24, 18, 24, y0=9.6)
    s.ribbons_left(8, 32, 22, 6, 4.0, y0=9.6, step=1.6)
    s.ribbons_right(4, 22, 32, 6, 4.0, y0=9.6, step=1.6)
    s.parapet(8, 4, 32, 22, 33.6)
    s.ring_on_roof(20, 13, 6.2, 33.62)
    # podium solar in front of and beside the tower
    s.pv_rows(35, 58.2, 2, 38, 9.62, row=2.0, gap=1.45)
    s.pv_rows(2, 33, 25, 38, 9.62, row=2.0, gap=1.45)
    # entrance canopy
    s.box(18, 40, 14, 4.5, 0.6, y0=3.6, top='#FFFFFF', left='#E8E9ED', right='#D3D5DB', sw=0.8)
    s.door_left(22, 6, 3.4, 40, fill='#A9BCCB')
    # ambulance bay
    s.car(42, 47, along='x', color='#FFFFFF')
    s.car(48, 47, along='x', color='#FFFFFF')
    for i, x in enumerate([58, 61, 64, 67, 70]):
        s.car(x, 47.5, along='z', color=['grey', '#FFFFFF', 'dark', 'grey', '#FFFFFF'][i])
    for x, z, k in [(-3, 48, 1.1), (8, 49, 0.9), (74, 30, 1.1), (74, 14, 1.0), (74, 2, 1.1)]:
        s.tree(x, z, k)
    return s


def university():
    s = Scene('University campus with solar panels on three buildings and a solar car park')
    s.slab(-8, -12, 92, 74)
    s.flat(-8, -12, 92, -6, GRASS)
    s.flat(0, 18, 46, 32, GRASS)   # quad lawn
    s.segs([((0, 0.06, 25), (46, 0.06, 25)), ((23, 0.06, 18), (23, 0.06, 32))], '#FFFFFF', sw=2.2)
    s.flat(54, 42, 92, 66, PAVE)
    s.road_x(-8, 92, 66, 72)
    s.shadow_box(0, 0, 32, 16, 15)
    s.shadow_box(48, -8, 66, 26, 19)
    s.shadow_box(4, 34, 36, 50, 11)
    # library at the back
    s.box(0, 0, 32, 16, 14.8)
    s.ribbons_left(0, 32, 16, 4, 3.6, step=1.6)
    s.ribbons_right(0, 16, 32, 4, 3.6, step=1.6)
    s.parapet(0, 0, 32, 16, 14.8)
    s.pv_rows(1.6, 30.4, 1.6, 14.4, 14.82, row=2.0, gap=1.4)
    # science block
    s.box(48, -8, 18, 34, 18.6)
    s.ribbons_left(48, 66, 26, 5, 3.6, step=1.6)
    s.ribbons_right(-8, 26, 66, 5, 3.6, step=1.6)
    s.parapet(48, -8, 66, 26, 18.6)
    s.pv_rows(49.6, 64.4, -6.4, 24.4, 18.62, row=2.0, gap=1.4)
    s.plant(52, -5, 18.6)
    for x, z, k in [(6, 21, 0.9), (16, 29, 1.0), (32, 21, 0.9), (40, 29, 1.0)]:
        s.tree(x, z, k)
    # teaching block at the front
    s.box(4, 34, 32, 16, 10.8)
    s.ribbons_left(4, 36, 50, 3, 3.5, step=1.6)
    s.ribbons_right(34, 50, 36, 3, 3.5, step=1.6)
    s.parapet(4, 34, 36, 50, 10.8)
    s.pv_rows(5.6, 34.4, 35.6, 48.4, 10.82, row=2.0, gap=1.4)
    # solar car park
    for i, x in enumerate([56, 58.6, 61.2, 66.4, 69, 74.2, 76.8, 82]):
        s.car(x, 44, along='z', color=['grey', '#FFFFFF', 'dark', '#FFFFFF', 'grey', '#FFFFFF', 'dark', 'grey'][i])
    s.carport(55, 88, 43, 49.5, h=3.4)
    for i, x in enumerate([56, 61.2, 63.8, 71.6, 79.4]):
        s.car(x, 56, along='z', color=['#FFFFFF', 'grey', 'dark', '#FFFFFF', 'grey'][i])
    s.carport(55, 88, 55, 61.5, h=3.4)
    for x, z, k in [(-3, 58, 1.1), (8, 60, 0.9), (40, 58, 1.0), (86, 30, 1.1), (86, 14, 1.0)]:
        s.tree(x, z, k)
    return s


def airport():
    s = Scene('Airport terminal with a long rooftop solar array, a control tower and a solar car park')
    s.slab(-6, -20, 134, 62)
    s.flat(-6, -20, 134, -6, '#E7E8EB')   # apron
    s.segs([((-4, 0.06, -14), (130, 0.06, -14))], '#F5C400', sw=1.6)
    s.road_x(-6, 134, 30, 37)
    s.flat(-6, 37, 134, 62, PAVE)
    s.shadow_box(0, -4, 108, 22, 13)
    # control tower behind the terminal's right end
    s.cylinder(124, -10, 2.2, 30)
    s.cylinder(124, -10, 4.6, 4.6, y0=30, glass=True)
    s.cylinder(124, -10, 5.2, 0.7, y0=34.6, top='#F4F4F6')
    s.segs([((124, 35.3, -10), (124, 41, -10))], INK, sw=1.0)
    # terminal
    s.box(0, -4, 108, 26, 12.4)
    s.curtain_left(2, 106, 22, 0.4, 11.4, step_x=2.2, step_y=3.8)
    s.ribbons_right(-2, 20, 108, 2, 4.6, step=2.0)
    s.parapet(0, -4, 108, 22, 12.4)
    s.pv_rows(1.8, 106.2, -2.2, 20.2, 12.42, row=2.1, gap=1.35)
    # drop-off canopy
    s.box(20, 22, 68, 5.5, 0.6, y0=4.4, top='#FFFFFF', left='#E8E9ED', right='#D3D5DB', sw=0.8)
    segs = [((x, 0, 27.2), (x, 4.4, 27.2)) for x in range(22, 88, 8)]
    s.segs(segs, '#7E838D', sw=1.2)
    # solar car park
    for row_z in (41, 52):
        for i, x in enumerate(range(10, 120, 9)):
            if i % 3 != 2:
                s.car(x + 1, row_z + 0.6, along='z', color=['#FFFFFF', 'grey', 'dark'][i % 3])
        s.carport(6, 124, row_z, row_z + 6.5, h=3.4)
    for x in [128, 131]:
        s.tree(x, 48 + (x - 128) * 3, 1.0)
    return s


def residential():
    s = Scene('Apartment blocks with balconies and solar panels on their roofs')
    s.slab(-8, -8, 76, 46)
    s.flat(-8, -8, 76, -3, GRASS)
    s.flat(-8, 29, 40, 46, GRASS)
    s.flat(40, 29, 76, 46, PAVE)
    s.segs([((-8, 0.06, 37), (40, 0.06, 37))], '#FFFFFF', sw=2.4)
    s.shadow_box(0, 0, 18, 18, 24)
    s.shadow_box(24, 6, 42, 24, 18)
    s.shadow_box(48, 0, 64, 18, 13)
    blocks = [(0, 0, 18, 18, 8), (24, 6, 18, 18, 6), (48, 0, 16, 18, 4)]
    for x0, z0, w, d, floors in blocks:
        h = floors * 3.0 + 0.8
        s.box(x0, z0, w, d, h)
        s.punched_left(x0, x0 + w, z0 + d, floors, 3.0, balcony=True)
        s.punched_right(z0, z0 + d, x0 + w, floors, 3.0)
        s.parapet(x0, z0, x0 + w, z0 + d, h)
        s.pv_rows(x0 + 1.5, x0 + w - 1.5, z0 + 1.6, z0 + d - 1.4, h + 0.02, row=2.0, gap=1.4)
        s.door_left(x0 + w / 2 - 1.2, 2.4, 2.8, z0 + d, fill='#7B8794')
    for i, x in enumerate([44, 47, 50, 56, 59, 65]):
        s.car(x, 33.4, along='z', color=['grey', '#FFFFFF', 'dark', '#FFFFFF', 'grey', 'dark'][i])
    s.bays_x(43.4, 67.4, 33, 5, step=3.0)
    for x, z, k in [(-3, 26, 1.0), (4, 33, 1.1), (14, 42, 0.9), (26, 33, 1.0), (34, 42, 1.1), (71, 20, 1.0), (71, 6, 1.1)]:
        s.tree(x, z, k)
    return s


SCENES = {
    'industrial': industrial, 'warehouse': warehouse, 'agri': agri, 'school': school,
    'hospital': hospital, 'university': university, 'airport': airport, 'residential': residential,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for key, build in SCENES.items():
        scene = flatten_segs(build())
        path = os.path.join(OUT, key + '.svg')
        with open(path, 'w') as f:
            f.write(scene.svg())
        print('%-12s %6.1f KB' % (key, os.path.getsize(path) / 1024))


if __name__ == '__main__':
    main()
