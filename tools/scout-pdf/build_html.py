"""Builds the print edition of a Scout page (one HTML section per PDF page).

Usage: python3 build_html.py data.json scout.html print.css
Input: data.json scraped from the Scout page by scrape.js.
Every overview page is one drive-time / minimum-size setting; every site page is
one site at the setting the Scout page opens with. Links between them are plain
#fragments, which Chromium turns into PDF links.
"""
import html
import json
import re
import sys
from urllib.parse import quote

D = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
E = html.escape

DRIVES, SIZES = [60, 90, 120], [50, 100, 250]
CL = D["client"]
DEFAULT = (D["defaults"]["drive"], D["defaults"]["size"])
DEFAULT_LBL = f"{DEFAULT[0]} min · {DEFAULT[1]} kWp"
MAIL = CL["contactEmail"]
MAILTO = "mailto:" + MAIL + "?subject=" + quote("Scout for " + CL["name"])

S = {(s["drive"], s["size"]): s for s in D["settings"]}
BASE = S[DEFAULT]
ROWS = BASE["rows"]
IDS = [r["id"] for r in ROWS]
NAME = {r["id"]: r["name"] for r in ROWS}
NUM = {r["id"]: r["n"] for r in ROWS}
NAME2ID = {r["name"]: r["id"] for r in ROWS}


def tier(why):
    m = re.search(r"tier ([ABC])", why)
    return m.group(1) if m else ""


def short_reason(why):
    if why.startswith("Outside your"):
        return "Too far"
    if why.startswith("Room for about"):
        return "Too small"
    return "Dropped"


# verdict of every site at every setting
V = {i: {} for i in IDS}
for key, s in S.items():
    for r in s["rows"]:
        V[r["id"]][key] = {"keep": r["keep"], "tier": tier(r["why"]) if r["keep"] else "", "why": r["why"]}


def sid(key):
    return f"set-{key[0]}-{key[1]}"


def linkify(text):
    """Escape text and turn site names in it into links to their pages."""
    out = E(text)
    for name in sorted(NAME2ID, key=len, reverse=True):
        esc = E(name)
        if esc in out:
            out = out.replace(esc, f'<a class="inl" href="#site-{NAME2ID[name]}">{esc}</a>')
    return out


def topbar(nav):
    return (
        '<header class="top"><div class="brand"><i class="sq"></i><span class="b1">Swarm Solar</span>'
        f'<span class="b2">Scout</span><span class="b3">for {E(CL["name"])}</span></div>'
        f'<nav class="nav">{nav}</nav></header>'
    )


FOOT = (
    '<footer class="foot"><span>Sample sweep. The companies and people in it are illustrative.</span>'
    f'<a href="{MAILTO}">{MAIL}</a></footer>'
)


def radar_svg(s):
    svg = D["rings"]
    svg = re.sub(r'<circle class="pulse"[^>]*>(</circle>)?', "", svg)
    svg = svg.replace(' id="rings"', "")
    r = s["limitFrac"] * 100
    extra = [f'<circle class="lim" cx="100" cy="100" r="{r:.2f}"></circle>']
    ly = 100 + r
    extra.append(
        f'<g class="limlbl"><rect x="88" y="{ly - 4.2:.2f}" width="24" height="8.4" rx="2"></rect>'
        f'<text x="100" y="{ly + 1.6:.2f}" text-anchor="middle">{E(s["limitLbl"])}</text></g>'
    )
    for b in s["blips"]:
        name = b["title"].split(",")[0]
        i = NAME2ID[name]
        x, y = b["left"] * 2, b["top"] * 2
        cls = "keep" if b["keep"] else "drop"
        if b["keep"]:
            extra.append(f'<circle class="glow" cx="{x:.2f}" cy="{y:.2f}" r="6.2"></circle>')
        extra.append(
            f'<g class="dot {cls}"><circle cx="{x:.2f}" cy="{y:.2f}" r="3.9"></circle>'
            f'<text x="{x:.2f}" y="{y + 1.25:.2f}" text-anchor="middle">{int(NUM[i])}</text></g>'
        )
    return svg.replace("</svg>", "".join(extra) + "</svg>")


def seg(kind, key):
    vals = DRIVES if kind == "drive" else SIZES
    cells = []
    for v in vals:
        k = (v, key[1]) if kind == "drive" else (key[0], v)
        on = " on" if k == key else ""
        label = f"{v} min" if kind == "drive" else f"{v} kWp"
        cells.append(f'<a class="segb{on}" href="#{sid(k)}">{label}</a>')
    return '<div class="seg">' + "".join(cells) + "</div>"


def overview(key):
    s = S[key]
    RS = 540
    hits = []
    for b in s["blips"]:
        i = NAME2ID[b["title"].split(",")[0]]
        x, y = b["left"] / 100 * RS, b["top"] / 100 * RS
        hits.append(
            f'<a class="hit" href="#site-{i}" style="left:{x - 13:.1f}px;top:{y - 13:.1f}px" '
            f'aria-label="{E(NAME[i])}"></a>'
        )
    keep = [r for r in s["rows"] if r["keep"]]
    drop = [r for r in s["rows"] if not r["keep"]]
    qrows = []
    for r in keep:
        m = re.match(r"(\d[\d,]* kWp), tier ([ABC])\. (.*?), (.*)$", r["why"])
        kwp, t, who = (m.group(1), m.group(2), m.group(3)) if m else ("", tier(r["why"]), "")
        qrows.append(
            f'<a class="qrow" href="#site-{r["id"]}"><span class="n">{r["n"]}</span>'
            f'<span class="nm">{E(r["name"])}</span><span class="who">{E(who)}</span>'
            f'<span class="kw">{E(kwp)}</span><span class="tier">{t}</span></a>'
        )
    chips = "".join(
        f'<a class="dchip" href="#site-{r["id"]}"><span class="n">{r["n"]}</span>{E(r["name"])}</a>' for r in drop
    )
    is_default = key == DEFAULT
    if is_default:
        h1 = D["hook"]
        nav = f'<span class="navtxt">Sample sweep from {E(CL["depot"])}, {E(CL["town"])}</span><a class="navb go" href="#plan">Shortlist and plan</a>'
    else:
        h1 = f'At {key[0]} minutes and {key[1]} kWp, Scout keeps {len(keep)} of 16 sites.'
        nav = f'<a class="navb" href="#{sid(DEFAULT)}">Back to {DEFAULT_LBL}</a>'
    diff = ""
    if not is_default:
        base_keep = {r["id"] for r in BASE["rows"] if r["keep"]}
        drops = [r for r in s["rows"] if not r["keep"] and r["id"] in base_keep]
        adds = [r for r in s["rows"] if r["keep"] and r["id"] not in base_keep]
        parts = []
        if drops:
            parts.append("Drops " + ", ".join(f'<a class="inl" href="#site-{r["id"]}">{E(r["name"])}</a> ({short_reason(r["why"]).lower()})' for r in drops))
        if adds:
            parts.append("Adds " + ", ".join(f'<a class="inl" href="#site-{r["id"]}">{E(r["name"])}</a>' for r in adds))
        diff = f'<p class="diff"><span>Compared with {DEFAULT_LBL}</span>{"; ".join(parts)}</p>'
    c = s["counts"]
    ppl_n, ppl_d = (c["ppl"].split("/") + [""])[:2]
    return f'''
<section class="page ov" id="{sid(key)}">
  {topbar(nav)}
  <div class="ovgrid">
    <div class="scope">
      <p class="scopehead">Rings show minutes of driving from the depot. North is up.</p>
      <div class="radarbox">
        <div class="radar">{radar_svg(s)}{"".join(hits)}</div>
        <div class="ro p-tl"><span class="k">Sites read</span><span class="v">16</span></div>
        <div class="ro p-tr"><span class="k">Qualified</span><span class="v fl">{c["keep"]}</span></div>
        <div class="ro p-bl"><span class="k">Dropped</span><span class="v">{c["drop"]}</span></div>
        <div class="ro p-br"><span class="k">Contacts kept</span><span class="v">{ppl_n}<small>/{ppl_d}</small></span></div>
      </div>
      <p class="legend"><span><i class="lg dep"></i>Depot, {E(CL["town"])}</span><span><i class="lg kp"></i>Qualified</span><span><i class="lg dr"></i>Dropped</span><span><i class="lg lm"></i>Drive-time limit</span></p>
    </div>
    <div class="side">
      <p class="kick">{"Territory sweep" if is_default else "Another setting"}</p>
      <h1 class="{"hook" if is_default else "dyn"}">{E(h1)}</h1>
      <p class="sugg"><span>Suggested starting point</span>{E(s["plan"]["head"])}</p>{diff}
      <div class="setrow">
        <div><p class="segk">Drive time from the depot</p>{seg("drive", key)}</div>
        <div><p class="segk">Smallest system worth quoting</p>{seg("size", key)}</div>
      </div>
      <h3 class="lh">Qualified <span>{len(keep)}</span><em>Tap a dot, a site or a setting to explore</em></h3>
      <div class="qlist">{"".join(qrows)}</div>
      <h3 class="lh">Dropped <span>{len(drop)}</span></h3>
      <div class="dchips">{chips}</div>
    </div>
  </div>
  {FOOT}
</section>'''


def pairs(text):
    lines = [l for l in text.split("\n") if l.strip()]
    return [(lines[i], lines[i + 1]) for i in range(0, len(lines) - 1, 2)]


def plan_pages():
    p = BASE["plan"]
    def fig_value(v):
        return re.sub(r"(\d)of", r"\1 of", v)

    figs = "".join(
        f'<div class="fig"><span class="k">{E(f["k"])}</span><span class="v{" fl" if f["k"] == "Qualified" else ""}">'
        f'{E(fig_value(f["v"]))}</span></div>'
        for f in p["figs"]
    )
    trs = []
    for cells in p["short"]:
        co = cells[0].split("\n")
        i = NAME2ID.get(co[0], "")
        loc = cells[2].split("\n")
        sysv = cells[3].split("\n")
        fc = cells[4].split("\n")
        trs.append(
            f'<a class="trow" href="#site-{i}"><span class="c1"><b>{E(co[0])}</b><i>{E(co[1] if len(co) > 1 else "")}</i></span>'
            f'<span>{E(cells[1])}</span>'
            f'<span>{E(loc[0])}<i>{E(loc[1] if len(loc) > 1 else "")}</i></span>'
            f'<span>{E(sysv[0])}<i>{E(sysv[1] if len(sysv) > 1 else "")}</i></span>'
            f'<span>{E(fc[0])}<i>{E(fc[1] if len(fc) > 1 else "")}</i></span>'
            f'<span class="tier">{E(cells[5])}</span><span class="nx">{E(cells[6])}</span></a>'
        )
    spec = "".join(f'<div class="sp"><dt>{E(x["k"])}</dt><dd>{linkify(x["v"])}</dd></div>' for x in p["spec"])

    def tally(text):
        items = pairs(text)
        top = max(int(n) for _, n in items) if items else 1
        return "".join(
            f'<div class="tl"><span class="tk">{E(k)}</span><span class="bar"><i style="width:{int(n) / top * 100:.0f}%"></i></span>'
            f'<span class="tn">{E(n)}</span></div>'
            for k, n in items
        )

    back = f'<a class="navb" href="#{sid(DEFAULT)}">Back to the radar</a>'
    nav_plan = back + '<a class="navb" href="#campaign">Campaign 01 ›</a>'
    nav_camp = back + '<a class="navb" href="#plan">‹ Shortlist</a>'
    return f'''
<section class="page pl" id="plan">
  {topbar(nav_plan)}
  <div class="rule"><i class="sq"></i><span>Suggested starting point</span><b></b></div>
  <div class="pltop">
    <div><h2>{E(p["head"])}</h2><p class="pwhy">{E(p["why"])}</p></div>
    <div class="figs">{figs}</div>
  </div>
  <h3 class="sh">Qualified shortlist <span>{E(p["shortN"])}</span></h3>
  <div class="tbl">
    <div class="thead"><span>Company</span><span>Sector</span><span>Location</span><span>System</span><span>First contact</span><span>Tier</span><span>Next step</span></div>
    {"".join(trs)}
  </div>
  <p class="note">Tier A is 250 kWp and up, tier B is 100 to 249 kWp, tier C is under 100 kWp. Tap a row to open the site.</p>
  {FOOT}
</section>
<section class="page cp" id="campaign">
  {topbar(nav_camp)}
  <div class="cpgrid">
    <div>
      <div class="rule"><i class="sq"></i><span>Campaign 01</span><b></b></div>
      <dl class="spec">{spec}</dl>
    </div>
    <div>
      <div class="rule"><i class="sq"></i><span>What Scout filtered out</span><b></b></div>
      <p class="tg">Sites</p><div class="tally">{tally(p["tSites"])}</div>
      <p class="tg">People</p><div class="tally">{tally(p["tPeople"])}</div>
      <div class="next">
        <p>{E(p["next"])}</p>
        <a class="cta" href="{MAILTO}">Want Scout on your real territory? Email {E(CL["contactName"])}</a>
      </div>
    </div>
  </div>
  {FOOT}
</section>'''


CHECK_OK = '<svg viewBox="0 0 12 12"><path d="M2.4 6.3l2.4 2.4 4.8-5.2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
CHECK_NO = '<svg viewBox="0 0 12 12"><path d="M3.2 3.2l5.6 5.6M8.8 3.2L3.2 8.8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'


def site_page(pos):
    i = IDS[pos]
    c = D["sites"][i]
    keep = "keep" in c["verdictClass"]
    prev_i, next_i = IDS[pos - 1] if pos > 0 else None, IDS[pos + 1] if pos + 1 < len(IDS) else None
    nav = f'<a class="navb" href="#{sid(DEFAULT)}">Back to the radar</a>'
    nav += f'<a class="navb" href="#site-{prev_i}">‹ {NUM[prev_i]}</a>' if prev_i else '<span class="navb off">‹</span>'
    nav += f'<a class="navb" href="#site-{next_i}">{NUM[next_i]} ›</a>' if next_i else '<span class="navb off">›</span>'
    tags = "".join(f'<span class="chip {E(t["cls"])}">{E(t["text"])}</span>' for t in c["tags"])
    checks = "".join(
        f'<li class="ck {"pass" if "pass" in x["cls"] else "fail"}"><span class="ci">{CHECK_OK if "pass" in x["cls"] else CHECK_NO}</span>'
        f'<span><span class="k">{E(x["k"])}</span><span class="v">{E(x["v"])}</span></span></li>'
        for x in c["checks"]
    )
    if c["people"]:
        people = "".join(
            f'<li class="ps {E(x["cls"].replace("person ", "").replace("person--", "ps--"))}"><span class="av">{E(x["av"])}</span>'
            f'<span class="pn">{E(x["name"])}<span class="pr">, {E(x["role"])}</span></span>'
            f'<span class="pt {E(x["tagCls"].replace("tag ", ""))}">{E(x["tag"])}</span><span class="pw">{E(x["why"])}</span></li>'
            for x in c["people"]
        )
        people = f'<ul class="people">{people}</ul>'
    else:
        people = f'<p class="skip">{E(c["skip"])}</p>'
    grid = ['<div class="gr"><span></span>' + "".join(f'<span class="gh">{s} kWp</span>' for s in SIZES) + "</div>"]
    for d in DRIVES:
        cells = []
        for s in SIZES:
            v = V[i][(d, s)]
            txt = f"Kept · {v['tier']}" if v["keep"] else short_reason(v["why"])
            cls = ("k" if v["keep"] else "d") + (" cur" if (d, s) == DEFAULT else "")
            cells.append(f'<a class="gc {cls}" href="#{sid((d, s))}">{txt}</a>')
        grid.append(f'<div class="gr"><span class="gh">{d} min</span>{"".join(cells)}</div>')
    st = c["stats"]
    plate = c["plate"].replace(' id="cPlate"', "")
    return f'''
<section class="page st" id="site-{i}">
  {topbar(nav)}
  <div class="sthead">
    <div class="idx"><span>{E(c["idx"])}</span><span class="verdict {"vk" if keep else "vd"}">{E(c["verdict"])}</span></div>
    <h1>{E(c["name"])}</h1>
    <div class="tags">{tags}</div>
  </div>
  <div class="stgrid">
    <div class="col1">
      <figure class="pf">{plate}<figcaption>{E(c["plateCap"])}</figcaption></figure>
      <div class="stats">
        <div><span class="k">System size</span><span class="v">{E(st["kwp"])}</span></div>
        <div><span class="k">Solar output</span><span class="v">{E(st["out"])}</span></div>
        <div><span class="k">Site usage</span><span class="v">{E(st["use"])}</span></div>
        <div><span class="k">Power bill</span><span class="v">{E(st["bill"])}</span></div>
      </div>
      <p class="snote">Yearly figures. Output and bill are estimates.</p>
    </div>
    <div class="col2">
      <p class="colk">Checks</p>
      <ol class="checks">{checks}</ol>
    </div>
    <div class="col3">
      <p class="colk">People at the company <span>{E(c["peopleN"])}</span></p>
      {people}
      <p class="why {"wk" if keep else "wd"}">{E(c["why"])}</p>
      <p class="colk">At other settings <span>tap to see the sweep</span></p>
      <div class="grid">{"".join(grid)}</div>
    </div>
  </div>
  {FOOT}
</section>'''


css_rules = [r for r in D["css"]["rules"] if r.startswith(".rings") or r.startswith(".plate .") or r.startswith(".plate {")]
CSS = "\n".join(D["css"]["fontFaces"]) + "\n" + "\n".join(css_rules) + "\n" + open(sys.argv[3]).read()

pages = [overview(DEFAULT), plan_pages()] + [site_page(p) for p in range(len(IDS))]
pages += [overview(k) for d in DRIVES for s_ in SIZES for k in [(d, s_)] if k != DEFAULT]

doc = f'''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><title>{E(D["title"])}</title>
<style>{CSS}</style></head><body>{"".join(pages)}</body></html>'''
open(OUT, "w", encoding="utf-8").write(doc)
print("pages:", doc.count('<section class="page'), "| bytes:", len(doc.encode()))
