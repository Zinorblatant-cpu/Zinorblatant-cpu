"""Gera os SVGs do README (versões clara e escura).

O GitHub não aceita CSS nem fontes customizadas no Markdown, então o visual
(Anton / Geist / Geist Mono, hachura, cantoneiras, tags em mono) vive em
SVGs com as fontes embutidas como subconjunto em base64.

Uso:  python assets/src/build_assets.py
As fontes são baixadas do Google Fonts na primeira execução (cache em
assets/src/.fonts, ignorado pelo git).
"""

import base64
import io
import re
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
FONT_DIR = ROOT / ".fonts"

FONTS = {
    "anton": ("Anton", 400),
    "geist": ("Geist", 400),
    "geist600": ("Geist", 600),
    "mono": ("Geist Mono", 400),
    "mono500": ("Geist Mono", 500),
}

# Tokens do frontend2 (moneta), tema escuro e claro.
THEMES = {
    "dark": dict(
        frame="#050505", card="#101013", ink="#fafafa", on_ink="#0a0a0b",
        ink_dim="#9a9a9e", fg="#f3f4f6", fg_muted="#c8c8d0", fg_faint="#8b8b95",
        line="rgba(255,255,255,0.06)", line2="rgba(255,255,255,0.10)",
        line_strong="rgba(255,255,255,0.32)", hatch="rgba(255,255,255,0.06)",
        brkc="rgba(255,255,255,0.5)", tint2="rgba(255,255,255,0.02)",
        tint6="rgba(255,255,255,0.06)",
    ),
    "light": dict(
        frame="#e9e9e6", card="#ffffff", ink="#0f1012", on_ink="#ffffff",
        ink_dim="#55565c", fg="#16171a", fg_muted="#393a3f", fg_faint="#5f6066",
        line="rgba(0,0,0,0.08)", line2="rgba(0,0,0,0.12)",
        line_strong="rgba(0,0,0,0.4)", hatch="rgba(0,0,0,0.06)",
        brkc="rgba(0,0,0,0.45)", tint2="rgba(0,0,0,0.02)",
        tint6="rgba(0,0,0,0.05)",
    ),
}

W = 900
EASE = "cubic-bezier(0.16,1,0.3,1)"


# ---------------------------------------------------------------- fontes

def font_path(key):
    family, weight = FONTS[key]
    path = FONT_DIR / f"{key}.ttf"
    if not path.exists():
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        css_url = ("https://fonts.googleapis.com/css2?family="
                   f"{family.replace(' ', '+')}:wght@{weight}")
        # Sem User-Agent de navegador, o Google Fonts devolve TTF.
        css = urllib.request.urlopen(css_url).read().decode()
        ttf_url = re.search(r"url\((https://[^)]+\.ttf)\)", css).group(1)
        path.write_bytes(urllib.request.urlopen(ttf_url).read())
    return path


_metrics = {}


def text_width(key, text, size, spacing=0.0):
    if key not in _metrics:
        f = TTFont(font_path(key))
        _metrics[key] = (f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm)
    cmap, hmtx, upm = _metrics[key]
    adv = sum(hmtx[cmap.get(ord(c), cmap[ord("?")])][0] for c in text)
    return adv * size / upm + spacing * size * max(len(text) - 1, 0)


class FontUse:
    """Acumula os caracteres usados por fonte para gerar o subconjunto."""

    def __init__(self):
        self.chars = {}

    def t(self, key, text):
        self.chars.setdefault(key, set()).update(text)
        return escape(text)

    def css(self):
        rules = []
        for key, chars in self.chars.items():
            family, weight = FONTS[key]
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga"]
            font = TTFont(font_path(key))
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)))
            sub.subset(font)
            buf = io.BytesIO()
            font.flavor = "woff2"
            font.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            rules.append(
                f"@font-face{{font-family:'{family}-{key}';font-weight:{weight};"
                f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
            )
        return "".join(rules)


def fam(key):
    fallback = {"anton": "Impact,'Arial Narrow',sans-serif",
                "geist": "'Segoe UI',system-ui,sans-serif",
                "geist600": "'Segoe UI',system-ui,sans-serif",
                "mono": "ui-monospace,Consolas,monospace",
                "mono500": "ui-monospace,Consolas,monospace"}[key]
    family, weight = FONTS[key]
    return f"font-family:'{family}-{key}',{fallback};font-weight:{weight}"


def svg(width, height, body, fonts, extra_css="", label=""):
    css = (
        fonts.css()
        + f"@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}"
        + f".in{{animation:in .8s {EASE} both}}"
        + ".d1{animation-delay:.08s}.d2{animation-delay:.16s}.d3{animation-delay:.24s}.d4{animation-delay:.32s}"
        + "@media (prefers-reduced-motion:reduce){.in{animation:none}}"
        + extra_css
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">'
        f"<style>{css}</style>{body}</svg>\n"
    )


def brackets(x, y, w, h, color, length=12, stroke=1.5):
    o = stroke / 2
    x0, y0, x1, y1 = x - o - 1, y - o - 1, x + w + o + 1, y + h + o + 1
    paths = [
        f"M{x0} {y0 + length}V{y0}H{x0 + length}",
        f"M{x1 - length} {y0}H{x1}V{y0 + length}",
        f"M{x0} {y1 - length}V{y1}H{x0 + length}",
        f"M{x1 - length} {y1}H{x1}V{y1 - length}",
    ]
    return "".join(
        f'<path d="{p}" fill="none" stroke="{color}" stroke-width="{stroke}"/>'
        for p in paths
    )


def hatch_pattern(color):
    return (
        '<defs><pattern id="hatch" width="9" height="9" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">'
        f'<rect width="1" height="9" fill="{color}"/></pattern></defs>'
    )


def mono_tag(fu, x, y, text, c, tone="normal", size=12, key="mono500"):
    """Tag em mono (padding 7, raio 5). Retorna (svg, largura)."""
    pad, h = 9, 24
    tw = text_width(key, text, size, 0.06)
    w = tw + 2 * pad
    if tone == "strong":
        stroke, fill, color, dash = c["line_strong"], c["tint6"], c["ink"], ""
    elif tone == "dim":
        stroke, fill, color, dash = c["line_strong"], "none", c["fg_faint"], ' stroke-dasharray="3 3"'
    else:
        stroke, fill, color, dash = c["line2"], "none", c["fg_muted"], ""
    out = (
        f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="5" '
        f'fill="{fill}" stroke="{stroke}"{dash}/>'
        f'<text x="{x + pad}" y="{y + h / 2 + size * 0.36}" style="{fam(key)};font-size:{size}px;'
        f'letter-spacing:.06em" fill="{color}">{fu.t(key, text)}</text>'
    )
    return out, w


# ---------------------------------------------------------------- peças

MENU = ["HELLO", "ABOUT", "EXPERIENCE", "STACK", "MODELING", "STATS", "CONTRIBUTIONS"]


def header(c):
    fu = FontUse()
    H = 316
    cx, cy, cw, ch = 40, 30, W - 80, H - 60
    p = 32
    body = [hatch_pattern(c["hatch"]),
            f'<rect width="{W}" height="{H}" rx="12" fill="{c["frame"]}"/>',
            f'<rect width="{W}" height="{H}" rx="12" fill="url(#hatch)"/>',
            f'<rect x="{cx + .5}" y="{cy + .5}" width="{cw - 1}" height="{ch - 1}" rx="10" '
            f'fill="{c["card"]}" stroke="{c["line2"]}"/>',
            brackets(cx, cy, cw, ch, c["brkc"])]

    # pílula + tag de status
    pill = "SOFTWARE DEVELOPER  ·  MATHEMATICAL MODELING"
    pw = text_width("geist", pill, 12, 0.04) + 24 + 14
    py = cy + p
    body.append(
        f'<g class="in"><rect x="{cx + p + .5}" y="{py + .5}" width="{pw - 1}" height="27" rx="14" '
        f'fill="{c["tint2"]}" stroke="{c["line2"]}"/>'
        f'<circle cx="{cx + p + 14}" cy="{py + 14}" r="3" fill="{c["ink"]}"/>'
        f'<text x="{cx + p + 26}" y="{py + 18.3}" style="{fam("geist")};font-size:12px;letter-spacing:.04em" '
        f'fill="{c["ink_dim"]}">{fu.t("geist", pill)}</text>'
    )
    status = "INTERN @ FOURSYS"
    sw = text_width("mono500", status, 12, 0.06) + 18
    t1, _ = mono_tag(fu, cx + cw - p - sw, py + 1.5, status, c, "strong")
    label = "STATUS"
    lw = text_width("mono", label, 11, 0.12)
    body.append(
        t1 + f'<text x="{cx + cw - p - sw - 10 - lw}" y="{py + 18}" style="{fam("mono")};font-size:11px;'
        f'letter-spacing:.12em" fill="{c["fg_faint"]}">{fu.t("mono", label)}</text></g>'
    )

    # título
    title = "LEONARDO LOPES"
    body.append(
        f'<text class="in d1" x="{cx + p - 3}" y="{cy + 150}" style="{fam("anton")};font-size:92px;'
        f'letter-spacing:.005em" fill="{c["ink"]}">{fu.t("anton", title)}</text>'
    )
    sub = "Software developer using mathematics to solve real-world problems."
    body.append(
        f'<text class="in d2" x="{cx + p}" y="{cy + 184}" style="{fam("geist")};font-size:16px" '
        f'fill="{c["fg_muted"]}">{fu.t("geist", sub)}</text>'
    )

    # menu numerado
    ly = cy + ch - 48
    parts = [f'<g class="in d3"><line x1="{cx}" y1="{ly}" x2="{cx + cw}" y2="{ly}" stroke="{c["line"]}"/>']
    x = cx + p
    for i, word in enumerate(MENU, 1):
        num = f"{i:02d}"
        parts.append(
            f'<text x="{x}" y="{ly + 29}" style="{fam("mono")};font-size:11px;letter-spacing:.12em">'
            f'<tspan fill="{c["fg_faint"]}">{fu.t("mono", num)}</tspan>'
            f'<tspan dx="7" fill="{c["fg_muted"]}">{fu.t("mono", word)}</tspan></text>'
        )
        x += text_width("mono", num, 11, 0.12) + 7 + text_width("mono", word, 11, 0.12) + 22
    assert x - 22 <= cx + cw - p, f"menu não cabe: {x}"
    parts.append("</g>")
    body.append("".join(parts))
    return svg(W, H, "".join(body), fu, label="Leonardo Lopes — Software developer and mathematical modeling")


def section(c, number, title):
    fu = FontUse()
    H = 64
    num = f"{number:02d}"
    tx = 44
    tw = text_width("anton", title, 34, 0.005)
    lx = tx + tw + 20
    body = (
        f'<g class="in"><text x="2" y="44" style="{fam("mono")};font-size:13px;letter-spacing:.12em" '
        f'fill="{c["fg_faint"]}">{fu.t("mono", num)}</text>'
        f'<text x="{tx}" y="48" style="{fam("anton")};font-size:34px;letter-spacing:.005em" '
        f'fill="{c["ink"]}">{fu.t("anton", title)}</text>'
        f'<line x1="{lx}" y1="36.5" x2="{W - 10}" y2="36.5" stroke="{c["line_strong"]}" stroke-opacity=".45"/>'
        f'<rect x="{W - 8}" y="33" width="7" height="7" fill="{c["ink_dim"]}"/></g>'
    )
    return svg(W, H, body, fu, label=f"{num} {title.title()}")


STACK = [
    ("LANGUAGES", ["PYTHON", "JAVASCRIPT", "TYPESCRIPT", "C"], "strong"),
    ("WEB", ["REACT", "HTML", "CSS", "ADOBE EXPERIENCE MANAGER"], "strong"),
    ("DATA & MODELING", ["NUMPY", "PANDAS"], "strong"),
    ("LEARNING", ["GO", "LATEX"], "dim"),
]


def stack(c):
    fu = FontUse()
    row_h, top = 52, 52
    H = top + row_h * len(STACK) + 6
    body = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="{c["card"]}" stroke="{c["line2"]}"/>']

    # legenda
    head = [f'<g class="in"><text x="28" y="31" style="{fam("mono")};font-size:11px;letter-spacing:.12em" '
            f'fill="{c["fg_faint"]}">{fu.t("mono", "TECH STACK")}</text>']
    t_dim, w_dim = mono_tag(fu, 0, 0, "LEARNING", c, "dim", size=11)
    t_str, w_str = mono_tag(fu, 0, 0, "PROFICIENT", c, "strong", size=11)
    x = W - 28 - w_dim
    head.append(f'<g transform="translate({x},14)">{t_dim}</g>')
    head.append(f'<g transform="translate({x - 8 - w_str},14)">{t_str}</g>')
    head.append(f'<line x1="0" y1="{top - .5}" x2="{W}" y2="{top - .5}" stroke="{c["line"]}"/></g>')
    body.append("".join(head))

    for i, (label, items, tone) in enumerate(STACK):
        y = top + i * row_h
        row = [f'<g class="in d{min(i + 1, 4)}">']
        row.append(f'<text x="28" y="{y + 31}" style="{fam("mono")};font-size:11px;letter-spacing:.12em" '
                   f'fill="{c["fg_faint"]}">{fu.t("mono", label)}</text>')
        x = 220
        for item in items:
            t, w = mono_tag(fu, x, y + 14, item, c, tone)
            row.append(t)
            x += w + 8
        assert x - 8 <= W - 28, f"linha {label} não cabe: {x}"
        if i < len(STACK) - 1:
            row.append(f'<line x1="28" y1="{y + row_h - .5}" x2="{W - 28}" y2="{y + row_h - .5}" stroke="{c["line"]}"/>')
        row.append("</g>")
        body.append("".join(row))
    return svg(W, H, "".join(body), fu,
               label="Tech stack: Python, JavaScript, TypeScript, C, React, HTML, CSS, "
                     "Adobe Experience Manager, NumPy, Pandas; learning Go and LaTeX")


def button(c, text, primary):
    fu = FontUse()
    size, pad, H = 14, 20, 44
    tw = text_width("geist600", text, size)
    w = round(tw + 2 * pad)
    if primary:
        rect = f'<rect x=".5" y=".5" width="{w - 1}" height="{H - 1}" rx="10" fill="{c["ink"]}" stroke="{c["ink"]}"/>'
        color = c["on_ink"]
    else:
        rect = (f'<rect x=".5" y=".5" width="{w - 1}" height="{H - 1}" rx="10" fill="{c["card"]}" '
                f'stroke="{c["line_strong"]}" stroke-opacity=".6"/>')
        color = c["fg"]
    body = (f'{rect}<text x="{pad}" y="{H / 2 + size * 0.36}" style="{fam("geist600")};font-size:{size}px" '
            f'fill="{color}">{fu.t("geist600", text)}</text>')
    return svg(w, H, body, fu, label=text)


def footer(c):
    fu = FontUse()
    H = 56
    text = "LEONARDO LOPES  ·  BUILT WITH MATH"
    tw = text_width("mono", text, 11, 0.12)
    pw = tw + 28
    body = (
        hatch_pattern(c["hatch"])
        + f'<rect width="{W}" height="{H}" rx="12" fill="{c["frame"]}"/>'
        + f'<rect width="{W}" height="{H}" rx="12" fill="url(#hatch)"/>'
        + f'<rect x="{(W - pw) / 2 + .5}" y="14.5" width="{pw - 1}" height="27" rx="14" fill="{c["card"]}" stroke="{c["line2"]}"/>'
        + f'<text x="{(W - tw) / 2}" y="32" style="{fam("mono")};font-size:11px;letter-spacing:.12em" '
          f'fill="{c["fg_faint"]}">{fu.t("mono", text)}</text>'
    )
    return svg(W, H, body, fu, label="")


SECTIONS = ["HELLO, THERE", "ABOUT ME", "EXPERIENCE", "TECH STACK",
            "MATHEMATICAL MODELING", "STATISTICS", "CONTRIBUTIONS"]


def main():
    for theme, c in THEMES.items():
        files = {
            f"header-{theme}.svg": header(c),
            f"stack-{theme}.svg": stack(c),
            f"footer-{theme}.svg": footer(c),
            f"btn-email-{theme}.svg": button(c, "Email", True),
            f"btn-linkedin-{theme}.svg": button(c, "LinkedIn", False),
            f"btn-instagram-{theme}.svg": button(c, "Instagram", False),
        }
        for i, title in enumerate(SECTIONS, 1):
            files[f"section-{i:02d}-{theme}.svg"] = section(c, i, title)
        for name, content in files.items():
            (OUT / name).write_text(content, encoding="utf-8")
            print(f"{name:28s} {len(content) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
