#!/usr/bin/env python3
"""Render the animated SVG cards for the GitHub profile README.

Every card is written twice (cards/<name>-light.svg and cards/<name>-dark.svg) and the
README swaps them with <picture>. Animation is plain CSS keyframes plus a little SMIL,
which GitHub keeps when an SVG is shown through <img>. Fonts are embedded subsets.

  python3 scripts/render_cards.py            # fetch fresh stats from GitHub, render
  python3 scripts/render_cards.py --offline  # re-render from data/stats.json
  STATIC=1 python3 scripts/render_cards.py   # end-state frames (no motion), for screenshots

Auth: GITHUB_TOKEN / GH_TOKEN env var, else `gh auth token`. Standard library only.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import subprocess
import sys
import urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
DATA = ROOT / "data" / "stats.json"
FONTS = ROOT / "fonts"
USER = os.environ.get("GH_USER", "mananbatraa")
STATIC = os.environ.get("STATIC") == "1"

# ---------------------------------------------------------------- profile content
NAME = ("Manan", "Batra")
TAGLINE = ("AI engineer who ships ", "full-stack products.")
META = [
    "MS Computer Science @ Arizona State University",
    "prev. AI Software Engineering Intern @ ParentSquare",
    "Tempe, AZ · open to SDE, AI/ML and full-stack roles",
]
PIPELINE = [  # hero diagram: (label, sub)
    ("data", "kafka · pyspark"),
    ("model", "pytorch · llms"),
    ("api", "fastapi · go"),
    ("ui", "react · ts"),
]
STACK = [
    ("AI / ML", ["Python", "PyTorch", "scikit-learn", "XGBoost", "LangGraph", "RAG", "LLM APIs"]),
    ("Backend", ["Go", "FastAPI", "Node.js", "Kafka", "Redis", "PostgreSQL", "MongoDB", "Docker"]),
    ("Data", ["PySpark", "Spark SQL", "Pandas", "Parquet", "Prometheus", "Grafana"]),
    ("Frontend", ["React", "TypeScript", "Streamlit", "Vitest"]),
]
PROJECTS = [  # (repo, description, tags)
    ("researchpilot-ai",
     "Multi-agent research assistant: four LangGraph agents search, analyze, fact-check and write source-cited reports.",
     "langgraph · fastapi · react"),
    ("FRIDAY",
     "Job-application tracker: reads Gmail, classifies emails with Claude structured outputs and keeps a Sheet up to date.",
     "claude · gmail api · streamlit"),
    ("ai-rag-knowledge-assistant",
     "Document Q&A with retrieval-augmented generation: PDF/DOCX upload, cited answers and honest no-answer handling.",
     "rag · embeddings · claude"),
    ("pyspark-data-engineering-pipeline",
     "Batch + streaming pipeline: validation with quarantine, Parquet silver/gold lake, Spark SQL reports and Kafka.",
     "pyspark · kafka · parquet"),
]
SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS", "SCSS", "Dockerfile", "Makefile", "Procfile",
              "Shell", "Batchfile", "PowerShell", "TeX"}

THEMES = {
    "dark": dict(surface="#0f141b", border="#2a313c", text="#e6edf3", muted="#8b949e", faint="#1c232d",
                 a1="#4cc9f0", a2="#b48cff", a3="#c3f73a", bar="#25303d", chip="#151b23", glow="#4cc9f0"),
    "light": dict(surface="#ffffff", border="#d6dbe1", text="#1f2328", muted="#59636e", faint="#eef1f4",
                  a1="#0a72b5", a2="#7c3aed", a3="#4d7c0f", bar="#dfe5eb", chip="#f6f8fa", glow="#0a72b5"),
}

# ---------------------------------------------------------------- data
QUERY = """query($login:String!){ user(login:$login){
  contributionsCollection{ contributionCalendar{ totalContributions
    weeks{ contributionDays{ date contributionCount } } } }
  repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){ totalCount
    nodes{ name stargazerCount primaryLanguage{ name color }
      languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } } } } }"""


def token() -> str:
    for key in ("PROFILE_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def fetch() -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token()}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        sys.exit(f"GraphQL error: {payload['errors']}")
    u = payload["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    langs, colors, primary = Counter(), {}, {}
    for repo in u["repositories"]["nodes"]:
        pl = repo["primaryLanguage"]
        primary[repo["name"]] = (pl["name"], pl["color"]) if pl else None
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            if n not in SKIP_LANGS:
                langs[n] += e["size"]
                colors[n] = e["node"]["color"] or "#8b949e"
    return {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "total": cal["totalContributions"],
        "days": days,
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "languages": [(n, b, colors[n]) for n, b in langs.most_common()],
        "primary": primary,
    }


def derive(s: dict) -> dict:
    days = [(dt.date.fromisoformat(d), c) for d, c in s["days"]]
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    for i, (_, c) in enumerate(reversed(days)):
        if c:
            current += 1
        elif i:  # today being empty doesn't break the streak yet
            break
    weekday = Counter()
    for d, c in days:
        weekday[d.strftime("%A")] += c
    last = days[-1][0]
    months = []
    y, m = last.year, last.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    per_month = Counter()
    for d, c in days:
        per_month[(d.year, d.month)] += c
    return {
        "longest": longest,
        "current": current,
        "active": sum(1 for _, c in days if c),
        "busiest": weekday.most_common(1)[0][0] if any(weekday.values()) else "—",
        "months": [(dt.date(y, m, 1).strftime("%b"), per_month[(y, m)]) for y, m in months],
    }


# ---------------------------------------------------------------- svg helpers
METRICS = json.loads((FONTS / "metrics.json").read_text())
esc = html.escape


def width(text: str, font: str, size: float) -> float:
    m = METRICS[font]
    fallback = m["adv"].get("n", 600)
    return sum(m["adv"].get(ch, fallback) for ch in text) / m["upm"] * size


def fonts_css() -> str:
    out = []
    for fam, w, name in (("G", 700, "grotesk-700"), ("G", 500, "grotesk-500"),
                         ("M", 400, "mono-400"), ("M", 600, "mono-600")):
        ext, b64 = (FONTS / f"{name}.b64").read_text().split(":", 1)
        out.append(f"@font-face{{font-family:{fam};font-weight:{w};"
                   f"src:url(data:font/{ext};base64,{b64}) format('{ext}')}}")
    return "".join(out)


FONT_CSS = fonts_css()
MOTION_OFF = "*{animation:none!important}.fx{display:none}.still{display:inline!important}"
BASE_CSS = """
.still{display:none}
.g{font-family:G,'Segoe UI',Helvetica,Arial,sans-serif}
.mono{font-family:M,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.t{transform-box:fill-box;transform-origin:50% 50%}
.tl{transform-box:fill-box;transform-origin:0 50%}
.tb{transform-box:fill-box;transform-origin:50% 100%}
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes growy{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes pop{0%{opacity:0;transform:scale(.3)}65%{opacity:1;transform:scale(1.12)}100%{opacity:1;transform:scale(1)}}
@keyframes swing{0%{opacity:0;transform:translateY(26px) rotate(-3deg)}60%{opacity:1;transform:translateY(-4px) rotate(.6deg)}100%{opacity:1;transform:none}}
@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
@keyframes ring{0%{transform:scale(.8);opacity:.85}100%{transform:scale(3);opacity:0}}
@keyframes nudge{0%,82%,100%{transform:none}88%{transform:translate(3px,-3px)}94%{transform:none}}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes drift{from{transform:translate(0,0)}to{transform:translate(-18px,-18px)}}
"""
EASE = "cubic-bezier(.2,.8,.2,1)"


def anim(name: str, dur: float, delay: float, extra: str = "both") -> str:
    return f'style="animation:{name} {dur}s {EASE} {delay:.2f}s {extra}"'


def svg(w: int, h: int, body: str, t: dict, label: str, defs: str = "", still: bool = False) -> str:
    motion = MOTION_OFF if (STATIC or still) else f"@media (prefers-reduced-motion:reduce){{{MOTION_OFF}}}"
    frame = (f'<rect width="{w}" height="{h}" fill="{t["surface"]}"/>' if still else
             f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="{t["surface"]}" stroke="{t["border"]}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>'
            f'<style>{FONT_CSS}{BASE_CSS}{motion}</style><defs>{defs}</defs>{frame}{body}</svg>')


def avatar(t: dict, x: float, y: float, size: float, delay: float = 0) -> tuple[str, str]:
    """Illustrated monogram avatar drawn in a 100x100 box. Returns (defs, body)."""
    k = size / 100
    defs = (f'<linearGradient id="av-mono" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{t["a1"]}"/><stop offset="1" stop-color="{t["a2"]}"/></linearGradient>'
            f'<radialGradient id="av-bg" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="{t["a1"]}" stop-opacity=".22"/>'
            f'<stop offset="1" stop-color="{t["a1"]}" stop-opacity="0"/></radialGradient>'
            f'<clipPath id="av-clip"><circle cx="50" cy="50" r="47"/></clipPath>'
            f'<pattern id="av-dots" width="6" height="6" patternUnits="userSpaceOnUse">'
            f'<circle cx="1" cy="1" r=".55" fill="{t["border"]}"/></pattern>')
    nodes = [(0, t["a1"]), (120, t["a2"]), (240, t["a3"])]

    def orbit_nodes() -> str:
        import math
        return "".join(f'<circle cx="{50 + 41 * math.cos(math.radians(a)):.2f}" cy="{50 + 41 * math.sin(math.radians(a)):.2f}" '
                       f'r="3.6" fill="{c}" stroke="{t["surface"]}" stroke-width="1.4"/>' for a, c in nodes)

    body = (f'<g transform="translate({x} {y}) scale({k:.4f})"><g class="t" {anim("pop", .7, delay)}>'
            f'<circle cx="50" cy="50" r="48" fill="{t["chip"]}" stroke="{t["border"]}" stroke-width="1.2"/>'
            f'<circle cx="50" cy="50" r="47.4" fill="url(#av-bg)"/>'
            f'<g clip-path="url(#av-clip)"><rect width="100" height="100" fill="url(#av-dots)" opacity=".7"/>'
            # a little skyline of bars behind the monogram: "ships products"
            + "".join(f'<rect class="tb" x="{18 + i * 9}" y="{86 - h}" width="5" height="{h}" rx="1.5" fill="{t["bar"]}" '
                      f'{anim("growy", .6, delay + .4 + i * .05)}/>' for i, h in enumerate((8, 14, 10, 20, 12, 24, 16)))
            + f'</g>'
            f'<circle cx="50" cy="50" r="41" fill="none" stroke="{t["border"]}" stroke-width="1" stroke-dasharray="2 3.5">'
            f'<animateTransform class="fx" attributeName="transform" type="rotate" from="0 50 50" to="-360 50 50" dur="40s" repeatCount="indefinite"/></circle>'
            f'<g class="fx">{orbit_nodes()}<animateTransform attributeName="transform" type="rotate" from="0 50 50" '
            f'to="360 50 50" dur="14s" repeatCount="indefinite"/></g>'
            f'<g class="still">{orbit_nodes()}</g>'
            f'<text x="50" y="60" text-anchor="middle" class="g" font-weight="700" font-size="33" letter-spacing="0.5" '
            f'fill="url(#av-mono)">MB</text>'
            f'<rect x="{50 + (width("MB", "grotesk-700", 33) + 1) / 2 + 2.5:.1f}" y="57.4" width="7" height="2.6" rx="1" fill="{t["a3"]}" '
            f'style="animation:blink 1.1s steps(1) {delay + 1:.2f}s infinite"/>'
            f'</g></g>')
    return defs, body


def counter(x: float, y: float, value: int, attrs: str, begin: float, dur: float = 1.2, frames: int = 16) -> str:
    """Count up to `value` with SMIL <set> frames (CSS can't change text), then a final static text."""
    vals = sorted({round(value * (1 - (1 - i / frames) ** 3)) for i in range(frames)} - {value})
    out = []
    if vals:
        step = dur / len(vals)
        out.append('<g class="fx">')
        for i, v in enumerate(vals):
            out.append(f'<text x="{x}" y="{y}" {attrs} opacity="0">{v:,}'
                       f'<set attributeName="opacity" to="1" begin="{begin + i * step:.3f}s" dur="{step:.3f}s"/></text>')
        out.append("</g>")
    out.append(f'<text x="{x}" y="{y}" {attrs} style="animation:fade .01s linear {begin + dur:.3f}s both">{value:,}</text>')
    return "".join(out)


def wrap(text: str, chars: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + (1 if cur else 0) <= chars:
            cur = f"{cur} {word}".strip()
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: chars - 1].rstrip() + "…"
    return lines


# ---------------------------------------------------------------- cards
def hero(t: dict, s: dict, d: dict) -> str:
    W, H = 840, 290
    b = []
    defs = (f'<pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse">'
            f'<circle cx="2" cy="2" r="1.1" fill="{t["border"]}"/></pattern>'
            f'<radialGradient id="glow" cx="78%" cy="50%" r="45%"><stop offset="0" stop-color="{t["glow"]}" stop-opacity=".16"/>'
            f'<stop offset="1" stop-color="{t["glow"]}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="160" y2="0">'
            f'<stop offset="0" stop-color="{t["a1"]}" stop-opacity="0"/><stop offset=".5" stop-color="#ffffff" stop-opacity=".9"/>'
            f'<stop offset="1" stop-color="{t["a1"]}" stop-opacity="0"/>'
            f'<animateTransform attributeName="gradientTransform" type="translate" values="-200 0;900 0;900 0" '
            f'keyTimes="0;.4;1" dur="5.5s" begin="2s" repeatCount="indefinite"/></linearGradient>'
            f'<clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="13"/></clipPath>'
            f'<clipPath id="typed"><rect class="tl" x="36" y="30" width="260" height="28" '
            f'style="animation:growx .9s steps(28) .1s both"/></clipPath>')
    b.append(f'<g clip-path="url(#card)"><rect x="0" y="0" width="{W + 40}" height="{H + 40}" fill="url(#dots)" opacity=".55" '
             f'style="animation:drift 14s linear infinite alternate"/><rect width="{W}" height="{H}" fill="url(#glow)"/></g>')
    # typed prompt + caret
    b.append(f'<g clip-path="url(#typed)"><text x="36" y="50" class="mono" font-size="13">'
             f'<tspan fill="{t["a1"]}">{USER}@github</tspan><tspan fill="{t["muted"]}">:~$ </tspan>'
             f'<tspan fill="{t["text"]}">whoami</tspan></text></g>')
    cx = 36 + width(f"{USER}@github:~$ whoami", "mono-400", 13) + 3
    b.append(f'<rect x="{cx:.1f}" y="39" width="8" height="15" fill="{t["a1"]}" '
             f'style="animation:fade .01s 1s both,blink 1.1s steps(1) 1s infinite"/>')
    # avatar, then name word by word beside it
    av_defs, av_body = avatar(t, 34, 72, 104, delay=.25)
    defs += av_defs
    b.append(av_body)
    x0 = 160
    x = x0 - 2
    for i, word in enumerate(NAME):
        b.append(f'<text x="{x:.1f}" y="120" class="g" font-weight="700" font-size="58" fill="{t["text"]}" '
                 f'letter-spacing="-1.2" {anim("rise", .8, .35 + i * .14)}>{esc(word)}</text>')
        x += width(word + " ", "grotesk-700", 58) - 1.2 * len(word)
    # tagline with shimmer on the accent half, shrunk if needed to clear the diagram
    fs = min(22.0, (555 - x0) / width("".join(TAGLINE), "grotesk-500", 1))
    tw = width(TAGLINE[0], "grotesk-500", fs)
    b.append(f'<g {anim("rise", .7, .75)}>'
             f'<text x="{x0}" y="160" class="g" font-weight="500" font-size="{fs:.1f}" fill="{t["muted"]}">{esc(TAGLINE[0])}</text>'
             f'<text x="{x0 + tw:.1f}" y="160" class="g" font-weight="500" font-size="{fs:.1f}" fill="{t["a1"]}">{esc(TAGLINE[1])}</text>'
             f'<text x="{x0 + tw:.1f}" y="160" class="g fx" font-weight="500" font-size="{fs:.1f}" fill="url(#shine)">{esc(TAGLINE[1])}</text></g>')
    b.append(f'<rect class="tl" x="36" y="188" width="500" height="1.5" fill="{t["border"]}" {anim("growx", .9, 1.0)}/>')
    for i, line in enumerate(META):
        y = 212 + i * 24
        col = (t["a1"], t["a2"], t["a3"])[i]
        b.append(f'<g {anim("rise", .6, 1.15 + i * .12)}><rect x="36" y="{y - 9}" width="8" height="8" rx="2" fill="{col}"/>'
                 f'<text x="54" y="{y}" class="mono" font-size="13" fill="{t["muted"]}">{esc(line)}</text></g>')
    # pipeline diagram
    b.append(f'<text x="575" y="36" class="mono" font-size="11" fill="{t["muted"]}" {anim("fade", .6, .4)}># how I build</text>')
    nodes = [(575, 52), (690, 104), (575, 156), (690, 208)]
    accents = (t["a1"], t["a2"], t["a3"], t["a1"])
    paths = ["M693 72 C749 72 749 72 749 104", "M690 124 C634 124 634 124 634 156",
             "M693 176 C749 176 749 176 749 208"]
    for i, p in enumerate(paths):
        b.append(f'<path d="{p}" pathLength="1" fill="none" stroke="{t["border"]}" stroke-width="1.5" '
                 f'stroke-dasharray="1" {anim("draw", .5, .9 + i * .25)}/>')
        b.append(f'<circle class="fx" r="3.2" fill="{accents[i + 1]}" opacity="0">'
                 f'<set attributeName="opacity" to="1" begin="{1.8 + i * .5}s"/>'
                 f'<animateMotion path="{p}" dur="1.6s" begin="{1.8 + i * .5}s" repeatCount="indefinite"/></circle>')
    for i, ((nx, ny), (label, sub)) in enumerate(zip(nodes, PIPELINE)):
        b.append(f'<g class="t" {anim("pop", .55, .55 + i * .22)}>'
                 f'<rect x="{nx}" y="{ny}" width="118" height="40" rx="9" fill="{t["chip"]}" stroke="{accents[i]}" stroke-width="1.2"/>'
                 f'<text x="{nx + 12}" y="{ny + 17}" class="mono" font-weight="600" font-size="12" fill="{accents[i]}">{label}()</text>'
                 f'<text x="{nx + 12}" y="{ny + 31}" class="mono" font-size="10" fill="{t["muted"]}">{esc(sub)}</text></g>')
    return svg(W, H, "".join(b), t, f"{' '.join(NAME)}: {''.join(TAGLINE)}", defs)


def tile(t: dict, idx: int, label: str, value: int, unit: str, sub: str, color: str) -> str:
    W, H = 272, 150
    delay = .5 + idx * .15
    b = [f'<g class="t" {anim("swing", .8, delay)}>',
         f'<rect class="tl" x="24" y="22" width="30" height="4" rx="2" fill="{color}" {anim("growx", .5, delay + .3)}/>',
         f'<text x="24" y="52" class="mono" font-size="11.5" letter-spacing="1.2" fill="{t["muted"]}">{esc(label)}</text>',
         counter(24, 104, value, f'class="g" font-weight="700" font-size="50" fill="{t["text"]}"', delay + .35)]
    if unit:
        ux = 24 + width(f"{value:,}", "grotesk-700", 50) + 8
        b.append(f'<text x="{ux:.1f}" y="104" class="g" font-weight="500" font-size="18" fill="{t["muted"]}" '
                 f'{anim("fade", .4, delay + 1.5)}>{esc(unit)}</text>')
    b.append(f'<text x="24" y="130" class="mono" font-size="12" fill="{t["muted"]}">{esc(sub)}</text>')
    b.append(f'<circle cx="244" cy="30" r="4" fill="{color}"/>'
             f'<circle class="t" cx="244" cy="30" r="4" fill="none" stroke="{color}" stroke-width="1.5" '
             f'style="animation:ring 2.4s ease-out {delay + 1.4:.2f}s infinite"/>')
    b.append("</g>")
    return svg(W, H, "".join(b), t, f"{label}: {value} {unit}".strip())


def activity(t: dict, s: dict, d: dict) -> str:
    W, H = 840, 250
    months = d["months"]
    peak = max((c for _, c in months), default=0)
    best = max(range(len(months)), key=lambda i: months[i][1]) if peak else -1
    b = [f'<text x="32" y="46" class="g" font-weight="700" font-size="20" fill="{t["text"]}" {anim("rise", .6, .2)}>Activity</text>',
         f'<text x="{32 + width("Activity", "grotesk-700", 20) + 12:.1f}" y="46" class="mono" font-size="12" fill="{t["muted"]}" '
         f'{anim("fade", .6, .35)}>contributions per month · last 12 months</text>',
         f'<text x="808" y="46" text-anchor="end" class="mono" font-size="12" fill="{t["muted"]}" {anim("fade", .6, .4)}>'
         f'<tspan fill="{t["a1"]}" font-weight="600">{s["total"]:,}</tspan> total · {d["active"]} active days</text>']
    base, top = 196, 82
    for k in range(4):
        y = base - (base - top) * k / 3
        dash = ' stroke-dasharray="3 4"' if k else ""
        b.append(f'<line x1="32" x2="808" y1="{y:.1f}" y2="{y:.1f}" stroke="{t["faint"]}" stroke-width="1"{dash}/>')
    slot = (808 - 32) / len(months)
    for i, (label, c) in enumerate(months):
        cx = 32 + slot * i + slot / 2
        h = max(3, (base - top) * c / peak) if peak else 3
        fill = t["a1"] if i == best else t["bar"]
        delay = .35 + i * .06
        b.append(f'<rect class="tb" x="{cx - 17:.1f}" y="{base - h:.1f}" width="34" height="{h:.1f}" rx="5" fill="{fill}" '
                 f'{anim("growy", .7, delay)}/>')
        b.append(f'<text x="{cx:.1f}" y="{base + 22}" text-anchor="middle" class="mono" font-size="11" '
                 f'fill="{t["text"] if i == best else t["muted"]}">{label}</text>')
        if c:
            weight, col, a = ("600", t["a1"], "pop") if i == best else ("400", t["muted"], "fade")
            b.append(f'<text class="t mono" x="{cx:.1f}" y="{base - h - 8:.1f}" text-anchor="middle" '
                     f'font-weight="{weight}" font-size="11" fill="{col}" '
                     f'{anim(a, .5, delay + .6)}>{c}</text>')
    return svg(W, H, "".join(b), t, f"{s['total']} contributions in the last 12 months")


def stack(t: dict, s: dict, d: dict) -> str:
    W = 840
    b = [f'<text x="32" y="46" class="g" font-weight="700" font-size="20" fill="{t["text"]}" {anim("rise", .6, .2)}>Toolbox</text>']
    y, n = 82, 0
    accents = (t["a1"], t["a2"], t["a3"], t["a1"])
    for gi, (group, items) in enumerate(STACK):
        b.append(f'<text x="32" y="{y + 17}" class="mono" font-weight="600" font-size="12" fill="{accents[gi]}" '
                 f'{anim("fade", .5, .3 + gi * .15)}>{esc(group)}</text>')
        x = 150
        for item in items:
            w = width(item, "mono-400", 12) + 26
            if x + w > 808:
                x, y = 150, y + 36
            b.append(f'<g class="t" {anim("pop", .45, .4 + n * .035)}><rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="26" rx="13" '
                     f'fill="{t["chip"]}" stroke="{t["border"]}"/><text x="{x + w / 2:.1f}" y="{y + 17}" text-anchor="middle" '
                     f'class="mono" font-size="12" fill="{t["text"]}">{esc(item)}</text></g>')
            x += w + 8
            n += 1
        y += 42
    # language split across public repos
    langs = s["languages"]
    total = sum(bts for _, bts, _ in langs) or 1
    shown = [(nm, bts / total, col) for nm, bts, col in langs if bts / total >= .015][:7]
    y += 10
    b.append(f'<text x="32" y="{y}" class="mono" font-size="12" fill="{t["muted"]}" {anim("fade", .5, 1.2)}>'
             f'languages by code across {s["repos"]} public repos</text>')
    y += 14
    b.append(f'<clipPath id="lang"><rect class="tl" x="32" y="{y}" width="776" height="10" rx="5" {anim("growx", 1.1, 1.3)}/></clipPath>'
             f'<g clip-path="url(#lang)"><rect x="32" y="{y}" width="776" height="10" fill="{t["bar"]}"/>')
    x = 32.0
    for nm, frac, col in shown:
        b.append(f'<rect x="{x:.1f}" y="{y}" width="{776 * frac:.1f}" height="10" fill="{col}"/>')
        x += 776 * frac
    b.append("</g>")
    y += 34
    x = 32.0
    for i, (nm, frac, col) in enumerate(shown):
        label = f"{nm} {frac * 100:.1f}%"
        b.append(f'<g {anim("fade", .4, 1.6 + i * .08)}><circle cx="{x + 5:.1f}" cy="{y - 4}" r="5" fill="{col}"/>'
                 f'<text x="{x + 16:.1f}" y="{y}" class="mono" font-size="12" fill="{t["muted"]}">{esc(label)}</text></g>')
        x += 16 + width(label, "mono-400", 12) + 22
    H = y + 28
    return svg(W, H, "".join(b), t, "Toolbox and languages")


def project(t: dict, idx: int, repo: str, desc: str, tags: str, lang) -> str:
    W, H = 412, 176
    delay = .4 + idx * .15
    color = (t["a1"], t["a2"], t["a3"], t["a1"])[idx % 4]
    title = repo if width(repo, "grotesk-700", 19) < 330 else repo[:30] + "…"
    b = [f'<g class="t" {anim("swing", .8, delay)}>',
         f'<rect class="tl" x="24" y="20" width="26" height="3" rx="1.5" fill="{color}" {anim("growx", .5, delay + .3)}/>',
         f'<text x="24" y="50" class="g" font-weight="700" font-size="19" fill="{t["text"]}">{esc(title)}</text>',
         f'<text class="t mono" x="388" y="50" text-anchor="end" font-size="18" '
         f'fill="{color}" style="animation:nudge 3.5s ease-in-out {delay + 1:.2f}s infinite">↗</text>']
    for i, line in enumerate(wrap(desc, 49, 3)):
        b.append(f'<text x="24" y="{78 + i * 19}" class="mono" font-size="12" fill="{t["muted"]}">{esc(line)}</text>')
    if lang:
        name, col = lang
        b.append(f'<circle cx="30" cy="148" r="5" fill="{col or t["muted"]}"/>'
                 f'<text x="42" y="152" class="mono" font-size="12" fill="{t["text"]}">{esc(name)}</text>')
    b.append(f'<text x="388" y="152" text-anchor="end" class="mono" font-size="11" fill="{t["muted"]}">{esc(tags)}</text>')
    b.append("</g>")
    return svg(W, H, "".join(b), t, f"{repo}: {desc}")


# ---------------------------------------------------------------- main
def main() -> None:
    if "--offline" in sys.argv:
        s = json.loads(DATA.read_text())
    else:
        s = fetch()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(s, indent=1))
    d = derive(s)
    top_langs = " · ".join(n for n, _, _ in s["languages"][:3])
    CARDS.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        out = {
            "hero": hero(t, s, d),
            "stat-contributions": tile(t, 0, "CONTRIBUTIONS", s["total"], "", "in the last 12 months", t["a1"]),
            "stat-repos": tile(t, 1, "PUBLIC REPOS", s["repos"], "", top_langs, t["a2"]),
            "stat-streak": tile(t, 2, "LONGEST STREAK", d["longest"], "days" if d["longest"] != 1 else "day",
                                f"busiest day: {d['busiest']}", t["a3"]),
            "activity": activity(t, s, d),
            "stack": stack(t, s, d),
        }
        for i, (repo, desc, tags) in enumerate(PROJECTS):
            out[f"project-{i + 1}"] = project(t, i, repo, desc, tags, s["primary"].get(repo))
        for name, content in out.items():
            (CARDS / f"{name}-{theme}.svg").write_text(content)
        # static, full-bleed avatar to export as the GitHub profile picture (PNG)
        av_defs, av_body = avatar(t, 20, 20, 460)
        (ROOT / "assets").mkdir(exist_ok=True)
        (ROOT / "assets" / f"avatar-{theme}.svg").write_text(
            svg(500, 500, av_body, t, f"{' '.join(NAME)} avatar", av_defs, still=True))
    print(f"rendered {len(out) * 2} cards · {s['total']} contributions · {s['repos']} repos · "
          f"longest streak {d['longest']} · busiest {d['busiest']}")


if __name__ == "__main__":
    main()
