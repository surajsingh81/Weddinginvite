#!/usr/bin/env python3
"""
Validate the generated SVGs: well-formed XML, sane path syntax, and content that
stays inside its viewBox.

This is not a renderer. It exists to catch the failure modes that hand-computed
coordinates actually produce: curves escaping the canvas, malformed path
commands, and transforms that push art outside the tile.

Run:  python3 check_art.py
"""
import glob
import math
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def nums(s):
    return [float(m) for m in NUM.findall(s or "")]


def bezier(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def quad(p0, p1, p2, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


def arc_points(x0, y0, rx, ry, phi, large, sweep, x1, y1, n=16):
    """Endpoint -> centre parameterisation (SVG spec F.6.5)."""
    if rx == 0 or ry == 0:
        return [(x0, y0), (x1, y1)]
    rx, ry = abs(rx), abs(ry)
    p = math.radians(phi)
    cosp, sinp = math.cos(p), math.sin(p)
    dx2, dy2 = (x0 - x1) / 2, (y0 - y1) / 2
    x1p = cosp * dx2 + sinp * dy2
    y1p = -sinp * dx2 + cosp * dy2
    lam = x1p**2 / rx**2 + y1p**2 / ry**2
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx**2 * ry**2 - rx**2 * y1p**2 - ry**2 * x1p**2
    den = rx**2 * y1p**2 + ry**2 * x1p**2
    coef = math.sqrt(max(0, num / den)) if den else 0
    if large == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cosp * cxp - sinp * cyp + (x0 + x1) / 2
    cy = sinp * cxp + cosp * cyp + (y0 + y1) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    th1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dth = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    pts = []
    for i in range(n + 1):
        t = th1 + dth * i / n
        x = cosp * rx * math.cos(t) - sinp * ry * math.sin(t) + cx
        y = sinp * rx * math.cos(t) + cosp * ry * math.sin(t) + cy
        pts.append((x, y))
    return pts


def path_points(d):
    """Flatten a path 'd' into points. Returns (points, ok).

    Handles implicit command repetition, e.g. "M0 0c1 1 2 2 3 3 4 4 5 5 6 6"
    is one moveto followed by two cubic segments under the same 'c'.
    """
    toks = re.findall(r"([MmLlHhVvCcSsQqTtAaZz])|([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)", d)
    cmds = []
    for c, n in toks:
        cmds.append(("cmd", c) if c else ("num", float(n)))
    ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    pts, cur, start, prev_c2, prev_q = [], (0, 0), (0, 0), None, None
    i, ok, pending = 0, True, None
    while i < len(cmds):
        kind, val = cmds[i]
        if kind == "cmd":
            pending = val
            i += 1
        elif pending is None:
            ok = False
            break
        # implicit repeat: a number run continues the previous command
        op = pending
        if op in "Zz":
            cur = start
            prev_c2 = prev_q = None
            pending = None
            i += 1
            continue
        o = op.upper()
        need = ARGC.get(o)
        if not need:
            ok = False
            break
        args = []
        while i < len(cmds) and cmds[i][0] == "num" and len(args) < need:
            args.append(cmds[i][1])
            i += 1
        if len(args) < need:
            ok = False
            break
        rel = op.islower()
        if o == "M":
            x, y = (cur[0] + args[0], cur[1] + args[1]) if rel else (args[0], args[1])
            pts.append((x, y)); cur = start = (x, y); prev_c2 = prev_q = None
            pending = "l" if rel else "L"   # further pairs are implicit linetos
        elif o == "L":
            x, y = (cur[0] + args[0], cur[1] + args[1]) if rel else (args[0], args[1])
            pts.append((x, y)); cur = (x, y); prev_c2 = prev_q = None
        elif o == "H":
            x = cur[0] + args[0] if rel else args[0]
            pts.append((x, cur[1])); cur = (x, cur[1]); prev_c2 = prev_q = None
        elif o == "V":
            y = cur[1] + args[0] if rel else args[0]
            pts.append((cur[0], y)); cur = (cur[0], y); prev_c2 = prev_q = None
        elif o == "C":
            a = args
            if rel:
                a = [cur[0] + a[0], cur[1] + a[1], cur[0] + a[2], cur[1] + a[3], cur[0] + a[4], cur[1] + a[5]]
            pts += bezier(cur, (a[0], a[1]), (a[2], a[3]), (a[4], a[5]))
            prev_c2 = (a[2], a[3]); cur = (a[4], a[5]); prev_q = None
        elif o == "S":
            a = args
            if rel:
                a = [cur[0] + a[0], cur[1] + a[1], cur[0] + a[2], cur[1] + a[3]]
            r = (2 * cur[0] - prev_c2[0], 2 * cur[1] - prev_c2[1]) if prev_c2 else cur
            pts += bezier(cur, r, (a[0], a[1]), (a[2], a[3]))
            prev_c2 = (a[0], a[1]); cur = (a[2], a[3]); prev_q = None
        elif o == "Q":
            a = args
            if rel:
                a = [cur[0] + a[0], cur[1] + a[1], cur[0] + a[2], cur[1] + a[3]]
            pts += quad(cur, (a[0], a[1]), (a[2], a[3]))
            prev_q = (a[0], a[1]); cur = (a[2], a[3]); prev_c2 = None
        elif o == "T":
            a = args
            if rel:
                a = [cur[0] + a[0], cur[1] + a[1]]
            q = (2 * cur[0] - prev_q[0], 2 * cur[1] - prev_q[1]) if prev_q else cur
            pts += quad(cur, q, (a[0], a[1]))
            prev_q = q; cur = (a[0], a[1]); prev_c2 = None
        elif o == "A":
            a = args
            ex, ey = (cur[0] + a[5], cur[1] + a[6]) if rel else (a[5], a[6])
            pts += arc_points(cur[0], cur[1], a[0], a[1], a[2], int(a[3]), int(a[4]), ex, ey)
            cur = (ex, ey); prev_c2 = prev_q = None
        if not (o == "A" and rel and args[4] == 1):  # keep flags explicit
            pass
    return pts, ok


def fit_viewbox(markup, pad=2.0):
    """Return a square viewBox that tightly frames an icon, so it renders
    centred and at the same visual weight as every other icon in the set."""
    import xml.etree.ElementTree as _ET
    wrapper = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
               'fill="none" stroke="currentColor">' + markup + "</svg>")
    try:
        root = _ET.fromstring(wrapper)
    except _ET.ParseError:
        return None
    xs, ys = [], []
    for el in root.iter():
        for x, y in element_points(el):
            xs.append(x); ys.append(y)
    if not xs:
        return None
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    # square it off around the centre so aspect ratio is never distorted
    side = max(hi_x - lo_x, hi_y - lo_y, 1e-6) + 2 * pad
    cx, cy = (lo_x + hi_x) / 2, (lo_y + hi_y) / 2
    return (cx - side / 2, cy - side / 2, side, side)


def rotate(p, deg, cx, cy):
    a = math.radians(deg)
    x, y = p[0] - cx, p[1] - cy
    return (cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a))


def element_points(el):
    tag = el.tag.replace(NS, "")
    pts = []
    if tag == "path":
        pts, _ = path_points(el.get("d"))
    elif tag == "circle":
        cx, cy, r = float(el.get("cx", 0)), float(el.get("cy", 0)), float(el.get("r", 0))
        pts = [(cx - r, cy - r), (cx + r, cy + r)]
    elif tag == "ellipse":
        cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
        rx, ry = float(el.get("rx", 0)), float(el.get("ry", 0))
        pts = [(cx - rx, cy - ry), (cx + rx, cy + ry)]
    elif tag in ("rect",):
        x, y = float(el.get("x", 0)), float(el.get("y", 0))
        w, h = float(el.get("width", 0)), float(el.get("height", 0))
        pts = [(x, y), (x + w, y + h)]
    elif tag == "polygon":
        v = nums(el.get("points"))
        pts = list(zip(v[::2], v[1::2]))
    elif tag == "line":
        pts = [(float(el.get("x1", 0)), float(el.get("y1", 0))),
               (float(el.get("x2", 0)), float(el.get("y2", 0)))]
    tr = el.get("transform") or ""
    m = re.match(r"rotate\(\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?(?:\s+(-?[\d.]+))?\s*\)", tr)
    if m and pts:
        deg = float(m.group(1))
        cx = float(m.group(2) or 0)
        cy = float(m.group(3) or 0)
        pts = [rotate(p, deg, cx, cy) for p in pts]
    return pts


def main():
    files = sorted(glob.glob("docs/assets/**/*.svg", recursive=True))
    if not files:
        sys.exit("no SVGs found - run make_art.py first")
    problems = 0
    total_bytes = 0
    for p in files:
        raw = open(p, encoding="utf-8").read()
        total_bytes += len(raw.encode())
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            print(f"  XML ERROR  {p}\n               {e}")
            problems += 1
            continue
        vb = nums(root.get("viewBox"))
        if len(vb) == 4:
            ox, oy, W, H = vb
        else:
            ox, oy, W, H = 0, 0, float(root.get("width", 0)), float(root.get("height", 0))

        bad_paths = 0
        xs, ys = [], []
        for el in root.iter():
            if el.tag.replace(NS, "") == "path":
                _, ok = path_points(el.get("d"))
                if not ok:
                    bad_paths += 1
            for x, y in element_points(el):
                xs.append(x); ys.append(y)

        name = p.split("assets/")[-1]
        tile = name == "jali.svg"   # a repeating pattern must overhang its edges
        if not xs:
            print(f"  EMPTY      {name}")
            problems += 1
            continue
        lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
        tol_x, tol_y = W * 0.14, H * 0.14
        notes = []
        if bad_paths:
            notes.append(f"{bad_paths} malformed path(s)")
        if not tile and (lo_x < ox - tol_x or hi_x > ox + W + tol_x):
            notes.append(f"x {lo_x:.0f}..{hi_x:.0f} outside {ox:.0f}..{ox + W:.0f}")
        if not tile and (lo_y < oy - tol_y or hi_y > oy + H + tol_y):
            notes.append(f"y {lo_y:.0f}..{hi_y:.0f} outside {oy:.0f}..{oy + H:.0f}")
        if tile:
            notes.append("tile (edge overhang by design)")
        if bad_paths or (notes and not tile):
            problems += 1
        mark = "FAIL" if (bad_paths or (notes and not tile)) else "ok  "
        print(f"  {mark} {name:30} {W:.0f}x{H:.0f}  content x[{lo_x:.0f}..{hi_x:.0f}] y[{lo_y:.0f}..{hi_y:.0f}]"
              + ("  <- " + "; ".join(n for n in notes if n != "tile (edge overhang by design)") if notes and not tile else ""))

    print(f"\n{len(files)} files, {total_bytes/1024:.1f} KB total, {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
