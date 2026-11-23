#!/usr/bin/env python3
"""Draws the profile banner (cards/flujo-*.svg) as a node workflow.

Run `pip install fonttools brotli` once, then `python scripts/render_banner.py`
whenever you change the texts below. Commit the new SVG and README.
"""
from __future__ import annotations

import base64
import hashlib
import io
import re
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
FONTS = ROOT / "assets" / "fonts"
README = ROOT / "README.md"

# ---------------------------------------------------------------- content ---

TRIGGER = ("Hola!", "inicio")
PERSON = ("Mario Cristian", "Carcalete", "2º DAM · Madrid", "Profe particular")
BRANCHES = [  # (title, subtitle, colour key)
    ("Android", "Kotlin", "kotlin"),
    ("Backend", "Java · SQL", "java"),
    ("Automatización IA", "n8n · Python · OCR", "ai"),
    ("Servidor casero", "Debian · Docker", "server"),
]
OUTPUT = (("Busco", "prácticas"), "FCT")
FOOTER = [("Español", "nativo"), ("Rumano", "nativo"), ("Inglés", "B2")]

# ------------------------------------------------------------------ theme ---

C = {
    "bg": "#15171c",
    "dot": "#2a2e37",
    "node": "#20232b",
    "stroke": "#353a45",
    "text": "#e4e6eb",
    "dim": "#8a909c",
    "kotlin": "#a97bff",
    "java": "#f0883e",
    "ai": "#2dd4bf",
    "green": "#4ade80",
    "server": "#60a5fa",
    "pink": "#f472b6",
}
FONT = "'JBM','JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
CW = 0.6  # character width of JetBrains Mono, in em


def font_face(text: str) -> str:
    """Embeds JetBrains Mono, cut down to the characters the banner uses."""
    chars = "".join(sorted(set(text + " .")))
    css = []
    for weight, fname in (("400", "JetBrainsMono-Regular.ttf"), ("700", "JetBrainsMono-Bold.ttf")):
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = []
        f = TTFont(FONTS / fname, recalcTimestamp=False)
        s = subset.Subsetter(opts)
        s.populate(text=chars)
        s.subset(f)
        buf = io.BytesIO()
        f.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        css.append(f"@font-face{{font-family:'JBM';font-weight:{weight};"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css)


def t(x, y, s, size=13, fill=None, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill or C["text"]}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>')


def node(x, y, w, h, colour, delay, inner, rx=12):
    return (f'<g class="n" style="animation-delay:{delay:.2f}s">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{C["node"]}" '
            f'stroke="{C["stroke"]}" stroke-width="1.2"/>'
            + ("" if rx > 20 else f'<rect x="{x}" y="{y+12}" width="3" height="{h-24}" rx="1.5" fill="{colour}"/>')
            + f'{inner}</g>')


def port(x, y, colour):
    return f'<circle cx="{x}" cy="{y}" r="4.5" fill="{C["bg"]}" stroke="{colour}" stroke-width="2"/>'


def wire(x1, y1, x2, y2, colour, delay):
    mx = (x1 + x2) / 2
    d = f"M{x1} {y1}C{mx} {y1} {mx} {y2} {x2} {y2}"
    return (f'<path d="{d}" fill="none" stroke="{C["stroke"]}" stroke-width="2"/>'
            f'<path class="w" style="animation-delay:{delay:.2f}s" d="{d}" fill="none" stroke="{colour}" '
            f'stroke-width="2" stroke-dasharray="4 10" stroke-linecap="round"/>')


def icon(kind, cx, cy, colour):
    """Small line icons drawn as paths, so they never depend on fonts."""
    st = f'fill="none" stroke="{colour}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "kotlin":  # phone
        return f'<rect x="{cx-6}" y="{cy-9}" width="12" height="18" rx="2.5" {st}/><path d="M{cx-2} {cy+5.5}h4" {st}/>'
    if kind == "java":  # server
        return (f'<rect x="{cx-8}" y="{cy-8}" width="16" height="7" rx="2" {st}/>'
                f'<rect x="{cx-8}" y="{cy+1}" width="16" height="7" rx="2" {st}/>'
                f'<path d="M{cx-4.5} {cy-4.5}h.1M{cx-4.5} {cy+4.5}h.1" {st}/>')
    if kind == "ai":  # spark
        return (f'<path d="M{cx} {cy-9}l2.2 6.8L{cx+9} {cy}l-6.8 2.2L{cx} {cy+9}l-2.2-6.8L{cx-9} {cy}'
                f'l6.8-2.2z" {st}/>')
    if kind == "server":  # old laptop
        return (f'<rect x="{cx-8}" y="{cy-7}" width="16" height="11" rx="1.5" {st}/>'
                f'<path d="M{cx-10} {cy+7}h20" {st}/>')
    if kind == "play":
        return f'<path d="M{cx-4} {cy-6}l10 6l-10 6z" fill="{colour}"/>'
    if kind == "flag":
        return f'<path d="M{cx-6} {cy+9}V{cy-8}h11l-2.5 4l2.5 4h-11" {st}/>'
    return ""


def banner() -> str:
    W, H = 880, 400
    b = []
    b.append(f'<defs><pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse">'
             f'<circle cx="1.5" cy="1.5" r="1.2" fill="{C["dot"]}"/></pattern>'
             f'<linearGradient id="hl" x1="0" y1="0" x2="1" y2="1">'
             f'<stop offset="0" stop-color="{C["kotlin"]}"/><stop offset="1" stop-color="{C["pink"]}"/>'
             f'</linearGradient></defs>')
    b.append(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="{C["bg"]}" stroke="{C["stroke"]}"/>')
    b.append(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="15.5" fill="url(#g)"/>')
    # top bar
    b.append(t(24, 36, "sobre-mi", 13, C["text"], 700))
    b.append(t(24 + 8 * 13 * CW, 36, ".flow", 13, C["dim"]))
    b.append(f'<rect x="{W-112}" y="18" width="88" height="26" rx="13" fill="{C["node"]}" stroke="{C["stroke"]}"/>'
             f'<circle class="pulse" cx="{W-95}" cy="31" r="4" fill="{C["green"]}"/>')
    b.append(t(W - 83, 35.5, "activo", 12, C["green"], 700))

    cy = 196  # middle line
    # trigger
    tx, tw, th = 24, 118, 64
    b.append(node(tx, cy - th / 2, tw, th, C["green"], 0.1,
                  f'<circle cx="{tx+28}" cy="{cy}" r="14" fill="{C["green"]}" opacity=".15"/>'
                  + icon("play", tx + 29, cy, C["green"])
                  + t(tx + 50, cy - 2, TRIGGER[0], 13, weight=700) + t(tx + 50, cy + 15, TRIGGER[1], 11, C["dim"]),
                  rx=32))
    b.append(port(tx + tw, cy, C["green"]))
    # person
    px, pw, ph = 192, 216, 140
    b.append(wire(tx + tw, cy, px, cy, C["green"], 0.6))
    b.append(node(px, cy - ph / 2, pw, ph, "url(#hl)", 0.35,
                  f'<rect x="{px+16}" y="{cy-44}" width="44" height="44" rx="12" fill="url(#hl)"/>'
                  + t(px + 38, cy - 16, "MC", 16, "#fff", 700, "middle")
                  + t(px + 72, cy - 26, PERSON[0], 13, weight=700)
                  + t(px + 72, cy - 9, PERSON[1], 13, weight=700)
                  + f'<line x1="{px+16}" y1="{cy+16}" x2="{px+pw-16}" y2="{cy+16}" stroke="{C["stroke"]}"/>'
                  + t(px + 16, cy + 38, PERSON[2], 12, C["dim"])
                  + t(px + 16, cy + 56, PERSON[3], 12, C["dim"])))
    b.append(port(px, cy, C["green"]))
    b.append(port(px + pw, cy, C["kotlin"]))
    # branches
    bx, bw, bh, gap = 474, 212, 56, 14
    top = cy - (len(BRANCHES) * bh + (len(BRANCHES) - 1) * gap) / 2
    mids = []
    for i, (title, sub, key) in enumerate(BRANCHES):
        col = C[key]
        y = top + i * (bh + gap)
        my = y + bh / 2
        mids.append((my, col))
        b.append(wire(px + pw, cy, bx, my, col, 1.0 + i * 0.15))
        b.append(node(bx, y, bw, bh, col, 0.6 + i * 0.15,
                      f'<rect x="{bx+14}" y="{my-15}" width="30" height="30" rx="9" fill="{col}" opacity=".14"/>'
                      + icon(key, bx + 29, my, col)
                      + t(bx + 56, my - 3, title, 13, weight=700) + t(bx + 56, my + 14, sub, 11, C["dim"])))
    # output
    ox, ow, oh = 744, 112, 100
    for i, (my, col) in enumerate(mids):
        b.append(wire(bx + bw, my, ox, cy, col, 1.6 + i * 0.1))
        b.append(port(bx, my, col))
        b.append(port(bx + bw, my, col))
    b.append(node(ox, cy - oh / 2, ow, oh, C["green"], 1.2,
                  icon("flag", ox + 24, cy - 24, C["green"])
                  + t(ox + 16, cy + 6, OUTPUT[0][0], 13, weight=700)
                  + t(ox + 16, cy + 22, OUTPUT[0][1], 13, weight=700)
                  + t(ox + 16, cy + 39, OUTPUT[1], 11, C["green"], 700)))
    b.append(port(ox, cy, C["green"]))
    # footer: languages
    fy = H - 28
    b.append(f'<line x1="24" y1="{fy-24}" x2="{W-24}" y2="{fy-24}" stroke="{C["stroke"]}"/>')
    b.append(t(24, fy, "idiomas", 12, C["dim"]))
    x = 24 + 8 * 12 * CW + 14
    for name, lvl in FOOTER:
        b.append(t(x, fy, name, 12, C["text"], 700))
        x += (len(name) + 1) * 12 * CW
        b.append(t(x, fy, lvl, 12, C["dim"]))
        x += len(lvl) * 12 * CW + 26
    b.append(t(W - 24, fy, "Madrid, España", 12, C["dim"], anchor="end"))

    css = (f"text{{font-family:{FONT};white-space:pre}}"
           ".n{opacity:0;animation:pop .5s cubic-bezier(.2,.8,.2,1) forwards}"
           "@keyframes pop{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
           ".w{animation:flow 1.2s linear infinite}"
           "@keyframes flow{to{stroke-dashoffset:-28}}"
           ".pulse{animation:pulse 1.6s ease-in-out infinite}"
           "@keyframes pulse{50%{opacity:.3}}"
           "@media (prefers-reduced-motion:reduce){*{animation:none!important;opacity:1!important}}")
    label = (f"{PERSON[0]} {PERSON[1]}, {PERSON[2]}, {PERSON[3].lower()}. "
             + ", ".join(f"{a} ({s})" for a, s, _ in BRANCHES)
             + f". {' '.join(OUTPUT[0])} {OUTPUT[1]}. Idiomas: "
             + ", ".join(f"{n} {l}" for n, l in FOOTER) + ".")
    used = label + "sobre-mi.flowactivoidiomasMC MadridEspaña!"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f'<style>{font_face(used)}{css}</style>{"".join(b)}</svg>')


def main():
    CARDS.mkdir(exist_ok=True)
    svg = banner()
    # The hash in the name makes GitHub show the new version instead of a cached one.
    name = f"flujo-{hashlib.sha1(svg.encode()).hexdigest()[:8]}.svg"
    for old in CARDS.glob("flujo-*.svg"):
        if old.name != name:
            old.unlink()
    (CARDS / name).write_text(svg, encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    README.write_text(re.sub(r"cards/flujo-[0-9a-f]{8}\.svg", f"cards/{name}", readme), encoding="utf-8")
    print(name)


if __name__ == "__main__":
    main()
