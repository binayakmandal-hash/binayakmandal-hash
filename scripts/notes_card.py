"""Draws the "by the numbers" card for the profile README, in the same sketchbook style as the header.

Run by .github/workflows/snake.yml every morning. It reads public data from the GitHub GraphQL API
(contributions in the last year, current and longest streak, public repos, languages by code size)
and writes notes-light.svg and notes-dark.svg into the folder given as the first argument.

If the API call fails, the previous day's cards (passed as the second argument) are kept, so the
README never shows a broken image.
"""
import datetime
import json
import math
import os
import pathlib
import random
import shutil
import sys
import urllib.request

USER = os.environ.get("GH_USER", "binayakmandal-hash")
HERE = pathlib.Path(__file__).parent

THEMES = {
    "light": dict(bg="#E9EDF1", ink="#22303F", soft="#5B6878", faint="#C9D2DB",
                  teal="#2F6F73", tealsoft="#8DB8B6", amber="#C98A12", bar=["#2F6F73", "#5E9794", "#8DB8B6", "#C98A12", "#C9D2DB"]),
    "dark": dict(bg="#182029", ink="#E3E9EF", soft="#93A1B0", faint="#33414F",
                 teal="#6FB3B1", tealsoft="#3E6E6D", amber="#E8B14A", bar=["#6FB3B1", "#4F8F8C", "#3E6E6D", "#E8B14A", "#33414F"]),
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def fetch():
    token = os.environ["GITHUB_TOKEN"]
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]["user"]


def summarize(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    counts = [d["contributionCount"] for d in days]
    # current streak: today may still be empty, so allow it to be 0
    cur, i = 0, len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    while i >= 0 and counts[i] > 0:
        cur += 1
        i -= 1
    best = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        best = max(best, run)
    langs = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:4]
    shares = [(name, size / total) for name, size in top]
    rest = 1 - sum(s for _, s in shares)
    if rest > 0.005:
        shares.append(("Other", rest))
    return dict(total=cal["totalContributions"], streak=cur, best=best,
                repos=user["repositories"]["totalCount"], langs=shares)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wobble(points, seed, amt=0.6):
    rnd = random.Random(seed)
    pts = [(x + rnd.uniform(-amt, amt), y + rnd.uniform(-amt, amt)) for x, y in points]
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for k in range(1, len(pts) - 1, 2):
        (cx, cy), (x, y) = pts[k], pts[min(k + 1, len(pts) - 1)]
        d += f" Q{cx:.1f},{cy:.1f} {x:.1f},{y:.1f}"
    return d


def underline(x0, x1, y, seed):
    rnd = random.Random(seed)
    return wobble([(x0 + (x1 - x0) * t / 10, y + math.sin(t / 10 * 3.1) * 2 + rnd.uniform(-.8, .8)) for t in range(11)], seed, .4)


def circle(cx, cy, rx, ry, seed):
    rnd = random.Random(seed)
    pts = []
    for k in range(33):
        th = -0.6 + k / 32 * 2.15 * math.pi
        f = 1 + rnd.uniform(-.04, .04) + .05 * k / 32
        pts.append((cx + rx * f * math.cos(th), cy + ry * f * math.sin(th)))
    return wobble(pts, seed, .5)


def render(s, c, fonts, today):
    W, H = 1000, 250
    css = fonts + f"""
.n{{font-family:Hand;font-weight:600;font-size:60px;fill:{c['amber']}}}
.l{{font-family:Bric;font-weight:500;font-size:16px;fill:{c['ink']}}}
.s{{font-family:Bric;font-weight:500;font-size:14px;fill:{c['soft']}}}
.h{{font-family:Hand;font-weight:600;font-size:23px;fill:{c['soft']}}}
.draw{{stroke-dasharray:1;stroke-dashoffset:0;animation:draw 1s ease-out var(--w,0s) backwards}}
@keyframes draw{{from{{stroke-dashoffset:1}}}}
.grow{{animation:grow .8s cubic-bezier(.3,1,.4,1) var(--w,0s) backwards;transform-box:fill-box;transform-origin:left}}
@keyframes grow{{from{{transform:scaleX(0)}}}}
@media (prefers-reduced-motion:reduce){{.draw,.grow{{animation:none}}}}
"""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="{s["total"]} contributions in the last year, {s["streak"]} day current streak, {s["repos"]} public repositories">'
           f'<title>By the numbers</title><style>{css}</style>',
           f'<rect width="{W}" height="{H}" rx="16" fill="{c["bg"]}"/>']
    stats = [(s["total"], ["contributions", "in the last year"]),
             (s["streak"], ["day streak right now", f"best so far: {s['best']}"]),
             (s["repos"], ["public repos", "of my own"])]
    for k, (num, labels) in enumerate(stats):
        x = 52 + k * 170
        txt = str(num)
        out.append(f'<text class="n" x="{x}" y="112">{txt}</text>')
        width = 26 * len(txt) + 6
        if k == 0:
            out.append(f'<path class="draw" pathLength="1" d="{circle(x + width / 2, 92, width / 2 + 16, 34, 3)}" fill="none" '
                       f'stroke="{c["amber"]}" stroke-width="2" stroke-linecap="round" style="--w:.3s"/>')
        else:
            out.append(f'<path class="draw" pathLength="1" d="{underline(x - 2, x + width + 4, 126, 5 + k)}" fill="none" '
                       f'stroke="{c["amber"]}" stroke-width="2.5" stroke-linecap="round" style="--w:{.3 + k * .2:.1f}s"/>')
        for j, lab in enumerate(labels):
            out.append(f'<text class="{"l" if j == 0 else "s"}" x="{x}" y="{156 + j * 22}">{esc(lab)}</text>')
    # languages: one hand-drawn bar, split by share of code
    bx, by, bw, bh = 580, 64, 370, 34
    out.append(f'<text class="l" x="{bx}" y="{by - 16}">What my code is written in</text>')
    x = bx
    for k, (name, share) in enumerate(s["langs"]):
        w = max(bw * share, 3)
        out.append(f'<rect class="grow" x="{x:.1f}" y="{by}" width="{w:.1f}" height="{bh}" rx="5" fill="{c["bar"][k % 5]}" style="--w:{.3 + k * .12:.2f}s"/>')
        x += w
    out.append(f'<path d="{wobble([(bx - 2, by - 2), (bx + bw / 2, by - 3), (bx + bw + 2, by - 1), (bx + bw + 3, by + bh / 2), (bx + bw + 1, by + bh + 2), (bx + bw / 2, by + bh + 3), (bx - 1, by + bh + 1), (bx - 2, by + bh / 2), (bx - 2, by - 2)], 11, .5)}" '
               f'fill="none" stroke="{c["ink"]}" stroke-width="1.5" opacity=".55"/>')
    for k, (name, share) in enumerate(s["langs"]):
        col, row = k % 3, k // 3
        lx, ly = bx + col * 126, by + bh + 32 + row * 26
        out.append(f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="3" fill="{c["bar"][k % 5]}"/>'
                   f'<text class="s" x="{lx + 18}" y="{ly}">{esc(name)} {share * 100:.0f}%</text>')
    out.append(f'<text class="h" x="{W - 30}" y="{H - 20}" text-anchor="end">redrawn every morning, last on {today}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    out_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    prev_dir = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if os.environ.get("NOTES_SAMPLE"):
            s = json.loads(os.environ["NOTES_SAMPLE"])
        else:
            s = summarize(fetch())
        fonts = (HERE / "fonts.css").read_text()
        today = datetime.date.today().strftime("%d %b %Y")
        for name, c in THEMES.items():
            (out_dir / f"notes-{name}.svg").write_text(render(s, c, fonts, today))
        print("drew the card:", {k: v for k, v in s.items() if k != "langs"}, s["langs"])
    except Exception as exc:  # keep yesterday's card rather than publishing nothing
        print("could not draw a new card:", exc)
        if prev_dir:
            for name in THEMES:
                old = prev_dir / f"notes-{name}.svg"
                if old.exists():
                    shutil.copy(old, out_dir / old.name)
                    print("kept", old.name)


if __name__ == "__main__":
    main()
