#!/usr/bin/env python3
"""Draws the profile README cards as SVG files, styled like an IDE window.

Run it locally with `python scripts/render_cards.py`, or let the daily
workflow (.github/workflows/readme-cards.yml) do it. With GITHUB_TOKEN set it
reads the real contribution calendar through GraphQL; without it, it falls back
to counting your commits in the repos listed in PROJECTS.

Edit PROFILE, CODE and PROJECTS below to change what the cards say.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import io
import json
import os
import re
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
FONTS = ROOT / "assets" / "fonts"
README = ROOT / "README.md"

# ---------------------------------------------------------------- content ---

LOGIN = "MarioCarcalete"

PROFILE = {
    "initials": "MC",
    "project": "MarioCarcalete",
    "branch": "main",
}

# The hero card shows this file in the editor. Keep lines under ~74 chars.
CODE_FILE = "Developer.kt"
CODE = '''package dev.mario

/** Hey, I'm Mario. Welcome to my GitHub! */
data class Developer(
    val name: String = "Mario Cristian Carcalete",
    val location: String = "Madrid, Spain",
    val studies: String = "2nd year of DAM",
    val stack: List<String> = listOf("Kotlin", "Java", "Python", "SQL"),
    val learning: List<String> = listOf("Spring Boot", "Cybersecurity"),
)

fun main() {
    val mario = Developer()
    mario.build("a personal AI assistant")  // in progress
}'''

# Shown as a test tree on the activity card: (label, repo, language).
PROJECTS = [
    ("LightsOut", "Programaci-n_multiplataforma_Kotlin_y_dem-s", "Kotlin"),
    ("TelemetrySystem", "Ampliacion-EntornosIDE-Testing", "Java"),
    ("Data access toolkit", "Ejercicios-Java-PP", "Java"),
    ("Processes & threads", "PSP_Dam", "Java"),
    ("Web forms", "Lenguage-De-Marcas", "HTML"),
]

# Buttons under the cards: (file id, label, hint).
BUTTONS = [
    ("linkedin", "LinkedIn", "connect"),
    ("lightsout", "LightsOut", "Kotlin game"),
    ("testing", "Testing", "JUnit + Mockito"),
    ("repos", "Repositories", "all projects"),
]

# ------------------------------------------------------------------ theme ---

C = {
    "bg": "#1e1f22",
    "panel": "#2b2d30",
    "border": "#393b40",
    "text": "#bcbec4",
    "dim": "#6f737a",
    "keyword": "#cf8e6d",
    "string": "#6aab73",
    "comment": "#7a7e85",
    "type": "#c9a0dc",
    "func": "#56a8f5",
    "number": "#2aacb8",
    "green": "#5fb865",
    "accent1": "#7f52ff",  # Kotlin purple
    "accent2": "#e44857",  # Kotlin red
    "accent3": "#f88909",  # Kotlin orange
}
LANG_COLOR = {"Kotlin": "#a97bff", "Java": "#e3893a", "HTML": "#e34c26", "Python": "#3572a5"}
MONO = "'JBM','JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
CW = 0.6  # JetBrains Mono advance width, in em

# ------------------------------------------------------------------- data ---


def _get(url: str, token: str | None, body: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "readme-cards")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def contributions_graphql(token: str) -> dict[str, int]:
    q = """query($l:String!){user(login:$l){contributionsCollection{
      contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    data = _get("https://api.github.com/graphql", token, {"query": q, "variables": {"l": LOGIN}})
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def contributions_rest(token: str | None) -> dict[str, int]:
    """Fallback: your commits in your own repos over the last year."""
    since = (dt.date.today() - dt.timedelta(days=365)).isoformat()
    days: Counter[str] = Counter()
    for repo in ["MarioCarcalete"] + [p[1] for p in PROJECTS]:
        page = 1
        while True:
            url = (f"https://api.github.com/repos/{LOGIN}/{repo}/commits"
                   f"?author={LOGIN}&since={since}T00:00:00Z&per_page=100&page={page}")
            try:
                items = _get(url, token)
            except Exception as e:  # noqa: BLE001
                print(f"  skip {repo}: {e}")
                break
            for c in items:
                days[c["commit"]["author"]["date"][:10]] += 1
            if len(items) < 100:
                break
            page += 1
    return dict(days)


def load_contributions() -> tuple[dict[str, int], str]:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        try:
            return contributions_graphql(token), "contributions"
        except Exception as e:  # noqa: BLE001
            print(f"GraphQL failed ({e}); counting commits instead")
    return contributions_rest(token), "commits"


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def stats(days: dict[str, int], today: dt.date) -> dict:
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    per_month = Counter()
    for d, n in days.items():
        per_month[(int(d[:4]), int(d[5:7]))] += n
    start = today - dt.timedelta(days=364)
    active = sorted(d for d, n in days.items() if n and d >= start.isoformat())
    # streaks
    best = cur = run = 0
    prev = None
    for d in active:
        day = dt.date.fromisoformat(d)
        run = run + 1 if prev and (day - prev).days == 1 else 1
        best = max(best, run)
        prev = day
    if prev and (today - prev).days <= 1:
        cur = run
    bars = [(MONTHS[m - 1], per_month[(y, m)]) for y, m in months]
    top = max(bars, key=lambda b: b[1])
    return {
        "bars": bars,
        "total": sum(n for _, n in bars),
        "active_days": len(active),
        "best_streak": best,
        "current_streak": cur,
        "best_month": top if top[1] else ("-", 0),
    }


# ------------------------------------------------------------------- svg ----


def font_face(text: str, weights: dict[str, str]) -> str:
    """Embeds JetBrains Mono, subset to the characters this card uses."""
    chars = "".join(sorted(set(text + " .")))
    css = []
    for weight, (fname, style) in weights.items():
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = []
        f = TTFont(FONTS / fname, recalcTimestamp=False)
        s = subset.Subsetter(opts)
        s.populate(text=chars)
        s.subset(f)
        buf = io.BytesIO()
        f.flavor = "woff2"
        f.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        css.append(f"@font-face{{font-family:'JBM';font-weight:{weight};font-style:{style};"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css)


def svg(w: int, h: int, label: str, body: str, css: str, text_for_font: str) -> str:
    faces = font_face(text_for_font, {
        "400": ("JetBrainsMono-Regular.ttf", "normal"),
        "700": ("JetBrainsMono-Bold.ttf", "normal"),
        "400i": ("JetBrainsMono-Italic.ttf", "italic"),
    }).replace("font-weight:400i", "font-weight:400")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">'
            f'<title>{escape(label)}</title><style>{faces}'
            f'text{{font-family:{MONO};white-space:pre}}{css}'
            f'@media (prefers-reduced-motion:reduce){{*{{animation:none!important;opacity:1!important}}}}'
            f'</style>{body}</svg>')


def t(x, y, s, size=13, fill=None, weight=400, italic=False, extra=""):
    fill = fill or C["text"]
    st = ' font-style="italic"' if italic else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}"{st} {extra}>{escape(s)}</text>')


def window(w, h, title):
    """Rounded IDE window with a header bar."""
    return (f'<defs><linearGradient id="kt" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{C["accent1"]}"/><stop offset=".55" stop-color="{C["accent2"]}"/>'
            f'<stop offset="1" stop-color="{C["accent3"]}"/></linearGradient></defs>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="12" fill="{C["bg"]}" stroke="{C["border"]}"/>'
            f'<path d="M1 40V12.5A11.5 11.5 0 0 1 12.5 1h{w-25}A11.5 11.5 0 0 1 {w-1} 12.5V40z" fill="{C["panel"]}"/>'
            f'<line x1="1" y1="40.5" x2="{w-1}" y2="40.5" stroke="{C["border"]}"/>')


def play_icon(x, y, s=10, fill=None):
    fill = fill or C["green"]
    return f'<path d="M{x} {y}l{s} {s*0.6}l-{s} {s*0.6}z" fill="{fill}"/>'


def check_icon(x, y, fill=None):
    fill = fill or C["green"]
    return (f'<circle cx="{x}" cy="{y}" r="6.5" fill="{fill}" opacity=".18"/>'
            f'<path d="M{x-3} {y}l2 2.2l4-4.4" fill="none" stroke="{fill}" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def folder_icon(x, y):
    return (f'<path d="M{x} {y+1}h4.5l1.5 1.5h6v7.5h-12z" fill="none" stroke="{C["dim"]}" '
            f'stroke-width="1.2" stroke-linejoin="round"/>')


def kt_icon(x, y, size=11):
    return (f'<path d="M{x} {y}h{size}l-{size/2} {size/2}l{size/2} {size/2}h-{size}z" fill="url(#kt)"/>')


# ---------------------------------------------------------------- tokens ----

KEYWORDS = {"package", "data", "class", "val", "var", "fun", "return", "import", "object"}
TOKEN = re.compile(r'(//.*$|/\*.*?\*/)|("(?:[^"\\]|\\.)*")|(\b\d+\b)|([A-Za-z_]\w*)|(\s+)|(.)')


def highlight(line: str):
    out = []
    for m in TOKEN.finditer(line):
        com, s, num, ident, ws, other = m.groups()
        if com:
            out.append((com, C["comment"], True))
        elif s:
            out.append((s, C["string"], False))
        elif num:
            out.append((num, C["number"], False))
        elif ident:
            rest = line[m.end():]
            if ident in KEYWORDS:
                out.append((ident, C["keyword"], False))
            elif ident[0].isupper():
                out.append((ident, C["type"], False))
            elif rest.startswith("("):
                out.append((ident, C["func"], False))
            elif rest.startswith(":"):
                out.append((ident, C["text"], False))
            else:
                out.append((ident, C["text"], False))
        else:
            out.append((ws or other, C["text"], False))
    return out


def code_line(x, y, line, size):
    spans = []
    for s, fill, italic in highlight(line):
        st = ' font-style="italic"' if italic else ""
        spans.append(f'<tspan fill="{fill}"{st}>{escape(s)}</tspan>')
    return f'<text x="{x}" y="{y}" font-size="{size}" xml:space="preserve">{"".join(spans)}</text>'


# ----------------------------------------------------------------- cards ----


def hero() -> str:
    W, H = 880, 420
    lines = CODE.split("\n")
    size, lh = 12.5, 19.5
    side = 216
    body = [window(W, H, "")]
    # toolbar: badge, project, branch, run config
    body.append(f'<rect x="14" y="10" width="22" height="20" rx="5" fill="url(#kt)"/>')
    body.append(t(25, 24.5, PROFILE["initials"], 10, "#fff", 700, extra='text-anchor="middle"'))
    body.append(t(44, 25, PROFILE["project"], 13, C["text"], 700))
    pw = 44 + len(PROFILE["project"]) * 13 * CW + 6
    body.append(t(pw, 25, "v", 10, C["dim"]))
    bx = pw + 26
    body.append(f'<path d="M{bx} 14v12M{bx} 20c0-3 6-3 6-6" fill="none" stroke="{C["dim"]}" stroke-width="1.3"/>'
                f'<circle cx="{bx+6}" cy="13" r="1.8" fill="{C["dim"]}"/>')
    body.append(t(bx + 12, 25, PROFILE["branch"], 13, C["text"]))
    rx = W - 196
    body.append(f'<rect x="{rx}" y="9" width="182" height="22" rx="6" fill="{C["bg"]}" stroke="{C["border"]}"/>')
    body.append(kt_icon(rx + 10, 14.5, 10))
    body.append(t(rx + 28, 24.5, "Developer.main()", 12, C["text"]))
    body.append(play_icon(rx + 160, 14.5, 9))
    # project tool window
    body.append(f'<rect x="1" y="41" width="{side}" height="{H-72}" fill="{C["panel"]}"/>'
                f'<line x1="{side+1.5}" y1="41" x2="{side+1.5}" y2="{H-31}" stroke="{C["border"]}"/>')
    body.append(t(16, 64, "Project", 12, C["text"], 700))
    tree = [
        (0, "folder", "MarioCarcalete", True),
        (1, "folder", "src", True),
        (2, "kt", CODE_FILE, "sel"),
        (2, "kt", "LightsOut.kt", False),
        (2, "kt", "TelemetrySystem.kt", False),
        (2, "kt", "DataAccess.kt", False),
        (1, "folder", "cards", False),
        (1, "md", "README.md", False),
        (1, "gr", "build.gradle.kts", False),
    ]
    ty = 92
    for depth, kind, name, state in tree:
        x = 16 + depth * 16
        if state == "sel":
            body.append(f'<rect x="6" y="{ty-14}" width="{side-12}" height="21" rx="5" fill="#2e436e"/>')
        if kind == "folder":
            body.append(t(x, ty, "v" if state else ">", 10, C["dim"]))
            body.append(folder_icon(x + 12, ty - 10))
            body.append(t(x + 30, ty, name, 12, C["text"]))
        else:
            if kind == "kt":
                body.append(kt_icon(x + 13, ty - 10, 10))
            else:
                col = C["func"] if kind == "md" else C["number"]
                body.append(f'<rect x="{x+13}" y="{ty-10}" width="10" height="11" rx="2" fill="none" stroke="{col}" stroke-width="1.3"/>')
            body.append(t(x + 30, ty, name, 12, "#fff" if state == "sel" else C["text"]))
        ty += 24
    # editor tabs
    ex = side + 2
    body.append(f'<rect x="{ex}" y="41" width="{W-ex-1}" height="34" fill="{C["bg"]}"/>'
                f'<line x1="{ex}" y1="75.5" x2="{W-1}" y2="75.5" stroke="{C["border"]}"/>')
    tx = ex + 14
    for i, name in enumerate([CODE_FILE, "LightsOut.kt", "README.md"]):
        if name.endswith(".kt"):
            body.append(kt_icon(tx, 52, 10))
        else:
            body.append(f'<rect x="{tx}" y="52" width="10" height="11" rx="2" fill="none" stroke="{C["func"]}" stroke-width="1.3"/>')
        body.append(t(tx + 17, 62, name, 12, "#fff" if i == 0 else C["dim"]))
        wtab = 17 + len(name) * 12 * CW + 26
        if i == 0:
            body.append(f'<rect x="{tx-6}" y="72" width="{wtab-12}" height="3" rx="1.5" fill="url(#kt)"/>')
        tx += wtab
    # code
    gx, cx, y0 = ex + 40, ex + 56, 102
    css = []
    for i, line in enumerate(lines):
        y = y0 + i * lh
        body.append(f'<g class="l" style="animation-delay:{0.25 + i * 0.12:.2f}s">')
        body.append(t(gx, y, str(i + 1), 12, C["dim"], extra='text-anchor="end"'))
        body.append(code_line(cx, y, line, size))
        body.append("</g>")
    last = len(lines) - 2
    caret_x = cx + len(lines[last].split("  //")[0]) * size * CW + 1
    body.append(f'<rect class="caret" x="{caret_x:.1f}" y="{y0 + last*lh - 13}" width="2" height="17" fill="#ced0d6"/>')
    css.append(".l{opacity:0;animation:in .35s ease-out forwards}"
               "@keyframes in{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}"
               f".caret{{opacity:0;animation:blink 1.1s steps(1) {0.4 + len(lines)*0.12:.2f}s infinite}}"
               "@keyframes blink{0%{opacity:1}50%{opacity:0}}")
    # status bar
    body.append(f'<path d="M1 {H-30}h{W-2}v17.5a11.5 11.5 0 0 1-11.5 11.5H12.5A11.5 11.5 0 0 1 1 {H-12.5}z" fill="{C["panel"]}"/>'
                f'<line x1="1" y1="{H-30.5}" x2="{W-1}" y2="{H-30.5}" stroke="{C["border"]}"/>')
    body.append(t(16, H - 11, f"{PROFILE['project']}  >  src  >  {CODE_FILE}", 11, C["dim"]))
    right = f"{last+1}:{len(lines[last].split('  //')[0])+1}   LF   UTF-8   Kotlin"
    body.append(t(W - 16, H - 11, right, 11, C["dim"], extra='text-anchor="end"'))
    label = ("Mario Cristian Carcalete: 2nd year DAM student in Madrid, Spain. "
             "Kotlin, Java, Python and SQL; learning Spring Boot and cybersecurity.")
    text = CODE + "".join(n for _, _, n, _ in tree) + PROFILE["project"] + right + "Developer.main()LightsOut.ktREADME.mdProjectv>0123456789:"
    return svg(W, H, label, "".join(body), "".join(css), text)


def activity(st: dict, source: str, today: dt.date) -> str:
    W, H = 880, 344
    body = [window(W, H, "")]
    body.append(t(18, 25, "Run", 13, C["text"], 700))
    body.append(f'<rect x="58" y="9" width="190" height="22" rx="6" fill="{C["bg"]}" stroke="{C["border"]}"/>')
    body.append(play_icon(68, 14.5, 9))
    body.append(t(84, 24.5, "profile:activity", 12, C["text"]))
    body.append(t(W - 18, 25, f"last 12 months  ·  {source}", 12, C["dim"], extra='text-anchor="end"'))

    # left: test tree of projects
    side = 300
    body.append(f'<path d="M1 41h{side}v{H-42}H12.5A11.5 11.5 0 0 1 1 {H-12.5}z" fill="{C["panel"]}"/>'
                f'<line x1="{side+1.5}" y1="41" x2="{side+1.5}" y2="{H-1}" stroke="{C["border"]}"/>')
    n = len(PROJECTS)
    body.append(check_icon(24, 66))
    body.append(t(38, 70, f"Tests passed: {n} of {n}", 12, C["green"], 700))
    body.append(t(18, 98, "v", 10, C["dim"]))
    body.append(check_icon(38, 94))
    body.append(t(52, 98, LOGIN, 12, C["text"], 700))
    y = 124
    for i, (label, _repo, lang) in enumerate(PROJECTS):
        body.append(f'<g class="row" style="animation-delay:{0.2 + i*0.15:.2f}s">')
        body.append(check_icon(54, y - 4))
        body.append(t(68, y, label, 12, C["text"]))
        body.append(f'<circle cx="{side-58}" cy="{y-4}" r="4" fill="{LANG_COLOR.get(lang, C["dim"])}"/>')
        body.append(t(side - 50, y, lang, 11, C["dim"]))
        body.append("</g>")
        y += 26
    # right: console + bar chart
    x0 = side + 22
    body.append(t(x0, 68, "> Task :fetchContributions", 12, C["dim"]))
    body.append(t(x0, 88, "> Task :renderChart", 12, C["dim"]))
    bars = st["bars"]
    mx = max([b[1] for b in bars] + [1])
    cw = (W - x0 - 24) / len(bars)
    base, hmax = 236, 120
    for i, (mon, v) in enumerate(bars):
        bx = x0 + i * cw + 6
        bw = cw - 12
        bh = max(3, v / mx * hmax) if v else 3
        fill = "url(#bar)" if v else C["border"]
        body.append(f'<rect class="bar" style="animation-delay:{0.3 + i*0.05:.2f}s" x="{bx:.1f}" '
                    f'y="{base-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{fill}"/>')
        if v:
            body.append(t(bx + bw / 2, base - bh - 6, str(v), 11, C["text"], extra='text-anchor="middle"'))
        last = i == len(bars) - 1
        body.append(t(bx + bw / 2, base + 17, mon, 11, C["text"] if last else C["dim"],
                      700 if last else 400, extra='text-anchor="middle"'))
    body.append('<defs><linearGradient id="bar" x1="0" y1="1" x2="0" y2="0">'
                f'<stop offset="0" stop-color="{C["accent1"]}"/><stop offset="1" stop-color="{C["accent3"]}"/>'
                '</linearGradient></defs>')
    bm, bv = st["best_month"]
    body.append(t(x0, 284, "BUILD SUCCESSFUL", 12, C["green"], 700))
    word = "contributions" if source == "contributions" else "commits"
    line = (f"{st['total']} {word}  ·  {st['active_days']} active days  ·  "
            f"best streak {st['best_streak']}d  ·  best month {bm}")
    body.append(t(x0 + 136, 284, "in 12 months", 12, C["dim"]))
    body.append(t(x0, 306, line, 12, C["text"]))
    body.append(t(W - 18, H - 14, f"updated {today.isoformat()}  ·  redrawn daily", 10, C["dim"],
                  extra='text-anchor="end"'))
    css = (".bar{transform-box:fill-box;transform-origin:50% 100%;animation:grow .7s cubic-bezier(.2,.8,.2,1) both}"
           "@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
           ".row{opacity:0;animation:in .35s ease-out forwards}"
           "@keyframes in{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}")
    label = (f"Activity over the last 12 months: {line}. Projects: "
             + ", ".join(f"{p[0]} ({p[2]})" for p in PROJECTS) + ".")
    text = ("".join(p[0] + p[2] for p in PROJECTS) + "".join(m for m, _ in bars) + line + LOGIN
            + "Tests passed: of RunBUILD SUCCESSFULin 12 months> Task :fetchContributions:renderChart"
            + "profile:activitylast 12 months  · contributionscommitsupdated redrawn daily0123456789-")
    return svg(W, H, label, "".join(body), css, text)


def button(label: str, hint: str) -> str:
    W, H = 210, 52
    body = [f'<defs><linearGradient id="kt" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{C["accent1"]}"/><stop offset=".55" stop-color="{C["accent2"]}"/>'
            f'<stop offset="1" stop-color="{C["accent3"]}"/></linearGradient></defs>',
            f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="10" fill="{C["panel"]}" stroke="{C["border"]}"/>',
            f'<rect x="10" y="10" width="32" height="32" rx="8" fill="url(#kt)"/>',
            play_icon(22, 19.5, 11, "#fff"),
            t(54, 24, label, 14, "#fff", 700),
            t(54, 40, hint, 11, C["dim"])]
    return svg(W, H, f"{label}: {hint}", "".join(body), "", label + hint)


# ------------------------------------------------------------------ write ---


def write_card(name: str, content: str) -> str:
    """Saves the card under a content hash so GitHub's image cache refreshes."""
    h = hashlib.sha1(content.encode()).hexdigest()[:8]
    fname = f"{name}-{h}.svg"
    for old in CARDS.glob(f"{name}-*.svg"):
        if old.name != fname:
            old.unlink()
    (CARDS / fname).write_text(content, encoding="utf-8")
    return fname


def main():
    CARDS.mkdir(exist_ok=True)
    today = dt.date.today()
    days, source = load_contributions()
    st = stats(days, today)
    print(json.dumps({k: v for k, v in st.items()}, default=str))
    names = {"hero": write_card("hero", hero()),
             "activity": write_card("activity", activity(st, source, today))}
    for fid, label, hint in BUTTONS:
        names[f"btn-{fid}"] = write_card(f"btn-{fid}", button(label, hint))
    readme = README.read_text(encoding="utf-8")
    for name, fname in names.items():
        readme = re.sub(rf"\./cards/{re.escape(name)}-[0-9a-f]{{8}}\.svg", f"./cards/{fname}", readme)
    README.write_text(readme, encoding="utf-8")
    print("cards:", ", ".join(sorted(names.values())))


if __name__ == "__main__":
    main()
