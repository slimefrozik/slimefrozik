#!/usr/bin/env python3
"""Slime snake for the GitHub contribution graph.

Fetches the last year of contributions via the GitHub GraphQL API and renders an
animated SVG: a gooey slime snake zig-zags over the grid and eats the cells.
Outputs slime-snake.svg (dark) and slime-snake-light.svg (light).

Usage:  GITHUB_TOKEN=... python slime_snake.py --user NAME --out dist
        python slime_snake.py --mock --out dist        # offline test, random data
"""
import argparse, json, math, os, random, urllib.request

P, CELL = 14, 11            # grid pitch / cell size
GY, W, H = 54, 900, 186
K = 16                      # body segments
DT = 0.11                   # seconds per grid step
MONO = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'DejaVu Sans Mono',monospace"

THEMES = {
    "dark":  dict(bg="#0d1117", border="#30363d", text="#c9d1d9", sub="#8b949e",
                  levels=["#161b22", "#12331f", "#1f6b3d", "#2fa85a", "#56d364"],
                  gel="#3eb856", body="#2fa85a", core="#7ee787", edge_to="#3eb856"),
    "light": dict(bg="#f6fff9", border="#b7e4c7", text="#1f2328", sub="#59636e",
                  levels=["#e3ece6", "#b7f0cb", "#6ede9b", "#2fb36b", "#17814f"],
                  gel="#2da44e", body="#1f9d57", core="#7ef0b0", edge_to="#2da44e"),
}


def fetch(user, token):
    q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
      totalContributions weeks{contributionDays{contributionCount weekday}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "slime-snake"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [{d["weekday"]: d["contributionCount"] for d in w["contributionDays"]} for w in cal["weeks"]]
    return weeks, cal["totalContributions"]


def mock():
    rnd = random.Random(7)
    weeks = []
    for c in range(53):
        w = {}
        for r in range(7):
            if c == 52 and r > 3:
                continue
            busy = 0.25 if r in (0, 6) else 0.6
            w[r] = int(rnd.expovariate(1 / 4)) + 1 if rnd.random() < busy * (0.4 + 0.6 * math.sin(c / 9) ** 2) else 0
        weeks.append(w)
    return weeks, sum(sum(w.values()) for w in weeks)


def levels_for(weeks):
    nz = sorted(v for w in weeks for v in w.values() if v > 0)
    if not nz:
        return lambda v: 0
    q = [nz[int(len(nz) * f) - 1 if len(nz) * f >= 1 else 0] for f in (.25, .5, .75)]
    return lambda v: 0 if v == 0 else 1 + sum(v > t for t in q)


def gel_strip(x0, x1, y, color, drips, th=7, k=1.35):
    out = f'<rect x="{x0}" y="{y}" width="{x1-x0}" height="{th}" rx="{th/2}" fill="{color}"/>'
    out += f'<rect x="{x0+6}" y="{y+1.2}" width="{x1-x0-12}" height="1.6" rx=".8" fill="#fff" opacity=".5"/>'
    for i, (x, L) in enumerate(drips):
        d = (i * 1.37) % 5
        out += (f'<g class="dp" style="animation-delay:-{d:.2f}s"><rect x="{x-3*k:.1f}" y="{y+1}" width="{6*k:.1f}" height="{L}" rx="{3*k:.1f}" fill="{color}"/>'
                f'<circle cx="{x}" cy="{y+L}" r="{4.6*k:.1f}" fill="{color}"/>'
                f'<rect x="{x-1.8*k:.1f}" y="{y+4}" width="2.2" height="{max(L-5, 2)}" rx="1.1" fill="#fff" opacity=".45"/></g>'
                f'<circle class="dd" style="animation-delay:-{d:.2f}s" cx="{x}" cy="{y+L+9}" r="2.3" fill="{color}"/>')
    return out


def render(weeks, total, theme):
    t = THEMES[theme]
    lvl = levels_for(weeks)
    C = len(weeks)
    gx = (W - (C * P - (P - CELL))) / 2
    cx = lambda c: gx + c * P + CELL / 2
    cy = lambda r: GY + r * P + CELL / 2

    # zig-zag path: one point per grid step, constant spacing => constant speed
    entry = math.ceil((cx(0) + 24) / P)
    pts = [(cx(0) - (entry - i) * P, cy(0)) for i in range(entry)]
    index = {}
    for c in range(C):
        rows = range(7) if c % 2 == 0 else range(6, -1, -1)
        for r in rows:
            index[(c, r)] = len(pts)
            pts.append((cx(c), cy(r)))
    lx, ly = pts[-1]
    for i in range(1, math.ceil((W + 24 - lx) / P) + 1):
        pts.append((lx + i * P, ly))
    T = (len(pts) - 1) * DT
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)

    base, eat = [], []
    for c, w in enumerate(weeks):
        for r, v in sorted(w.items()):
            x, y = gx + c * P, GY + r * P
            base.append(f'<rect x="{x:.1f}" y="{y}" width="{CELL}" height="{CELL}" rx="3" fill="{t["levels"][0]}"/>')
            L = lvl(v)
            if L:
                te = index[(c, r)] * DT
                a, b = max(te - DT * .6, 0) / T, (te + DT * .25) / T
                eat.append(f'<rect x="{x:.1f}" y="{y}" width="{CELL}" height="{CELL}" rx="3" fill="{t["levels"][L]}">'
                           f'<animate attributeName="opacity" dur="{T:.2f}s" repeatCount="indefinite" '
                           f'values="1;1;0;0;1" keyTimes="0;{a:.5f};{b:.5f};0.999;1"/></rect>')

    def seg(k, r, fill, extra=""):
        b = k * DT / 2
        return (f'<circle r="{r:.2f}" fill="{fill}" visibility="hidden"{extra}>'
                f'<set attributeName="visibility" to="visible" begin="{b:.3f}s" fill="freeze"/>'
                f'<animateMotion dur="{T:.2f}s" begin="{b:.3f}s" repeatCount="indefinite">'
                f'<mpath href="#sp" xlink:href="#sp"/></animateMotion></circle>')

    rk = lambda k: 9.0 if k == 0 else max(5.2, 8.4 - k * 0.2)
    outer = "".join(seg(k, rk(k), t["body"]) for k in range(K))
    inner = "".join(seg(k, rk(k) * .62, t["core"]) for k in range(K))
    gloss = "".join(seg(k, max(rk(k) * .2, .8), "#ffffff", ' opacity=".85"') for k in range(0, K, 2))
    head = (f'<g><animateMotion dur="{T:.2f}s" repeatCount="indefinite" rotate="auto"><mpath href="#sp" xlink:href="#sp"/></animateMotion>'
            '<path d="M9 0 H14.5 M14.5 0 l2.6 -1.7 M14.5 0 l2.6 1.7" stroke="#ff7b72" stroke-width="1.2" stroke-linecap="round" fill="none">'
            '<animate attributeName="opacity" dur="2.2s" repeatCount="indefinite" values="0;0;1;1;0;0" keyTimes="0;.55;.6;.75;.8;1"/></path>'
            '<circle cx="3.6" cy="-4.4" r="2.5" fill="#fff"/><circle cx="3.6" cy="4.4" r="2.5" fill="#fff"/>'
            '<circle cx="4.4" cy="-4.4" r="1.25" fill="#0a2a22"/><circle cx="4.4" cy="4.4" r="1.25" fill="#0a2a22"/></g>')

    lab = f'{total:,} contributions in the last year'.replace(",", " ")
    xs = [gx + C * P - (P - CELL) - 120 - i * 17 for i in range(5)][::-1]
    legend = (f'<text x="{xs[0]-8}" y="{GY+7*P+22}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{t["sub"]}">Less</text>'
              + "".join(f'<rect x="{x:.1f}" y="{GY+7*P+13}" width="11" height="11" rx="3" fill="{t["levels"][i]}"/>' for i, x in enumerate(xs))
              + f'<text x="{xs[-1]+19}" y="{GY+7*P+22}" font-family="{MONO}" font-size="10.5" fill="{t["sub"]}">More</text>')
    strip = gel_strip(18, W - 18, 4, t["gel"], [(430, 16), (520, 26), (610, 14), (700, 22), (790, 14)])

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" aria-label="Slime snake eating the GitHub contribution graph: {lab}">
<defs>
  <path id="sp" d="{d}" fill="none"/>
  <filter id="goo" filterUnits="userSpaceOnUse" x="-30" y="0" width="{W+60}" height="{H}"><feGaussianBlur in="SourceGraphic" stdDeviation="2.1" result="b"/><feColorMatrix in="b" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -9"/></filter>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["border"]}"/><stop offset=".7" stop-color="{t["edge_to"]}" stop-opacity=".7"/><stop offset="1" stop-color="{t["edge_to"]}"/></linearGradient>
</defs>
<style><![CDATA[
.dp{{transform-box:fill-box;transform-origin:50% 0%;animation:dripS 5s ease-in-out infinite}}
.dd{{animation:dropF 5s ease-in infinite;opacity:0}}
@keyframes dripS{{0%,100%{{transform:scaleY(.6)}}55%{{transform:scaleY(1.12)}}}}
@keyframes dropF{{0%,52%{{opacity:0;transform:translateY(0)}}58%{{opacity:.9}}100%{{opacity:0;transform:translateY(26px)}}}}
]]></style>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="{t["bg"]}" stroke="url(#edge)" stroke-width="1.4"/>
{strip}
<text x="{gx:.0f}" y="38" font-family="{MONO}" font-size="13" font-weight="700" fill="{t["text"]}"><tspan fill="{t["gel"]}">❯ </tspan>{lab}</text>
{"".join(base)}
{"".join(eat)}
<g filter="url(#goo)">{outer}</g>
<g filter="url(#goo)"><g transform="translate(-1.1,-1.5)">{inner}</g></g>
<g transform="translate(-2.4,-3)">{gloss}</g>
{head}
{legend}
</svg>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", ""))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    weeks, total = mock() if a.mock else fetch(a.user, os.environ["GITHUB_TOKEN"])
    os.makedirs(a.out, exist_ok=True)
    for theme, name in (("dark", "slime-snake.svg"), ("light", "slime-snake-light.svg")):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(render(weeks, total, theme))
    print(f"ok: {len(weeks)} weeks, {total} contributions -> {a.out}")


if __name__ == "__main__":
    main()
