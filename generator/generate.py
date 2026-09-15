"""
Terra Mirabilis — player documentation generator.

Reads the mod's SQL (via parse.py) and writes a static website into ../docs,
served by GitHub Pages. Standard library only; run it with any Python 3.

    python generator/generate.py

Design mirrors the sibling "Prehistoric Era" docs generator: one small parser,
one generator, output committed under docs/ and served from the repo-root /docs
folder. The mod's art is not redistributed here — the pages use the game's own
inline markup ([ICON_*], [NEWLINE]) rendered to text + emoji chips.
"""

from __future__ import annotations

import os
import re
import sys
import html
import glob
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(SCRIPT_DIR, "..", "docs")   # generated site (committed; served by Pages)


def _resolve_mod_dir():
    """Locate the Terra Mirabilis mod source (read-only input; NOT part of this
    docs repo). Priority: --source/--mod arg, then TM_MOD_DIR env var, then the
    generator's own parent (if it sits inside the mod repo), then a sibling
    `civ6-terra-mira` checkout, then the installed mod folder."""
    def has_core(p):
        return p and os.path.isdir(os.path.join(p, "Core"))

    base = None
    for i, a in enumerate(sys.argv):
        if a in ("--source", "--mod") and i + 1 < len(sys.argv):
            base = sys.argv[i + 1]
        elif a.startswith("--source=") or a.startswith("--mod="):
            base = a.split("=", 1)[1]
    base = base or os.environ.get("TM_MOD_DIR")
    candidates = ([base] if base else []) + [
        os.path.join(SCRIPT_DIR, ".."),                            # generator inside the mod repo
        # Canonical source: the mod subfolder of the civ6-tweaks monorepo clone.
        os.path.join(SCRIPT_DIR, "..", "..", "civ6-tweaks", "terra-mirabilis-2026"),
        os.path.join(SCRIPT_DIR, "..", "..", "civ6-terra-mira"),   # legacy standalone repo (deprecated)
        os.path.join(os.environ.get("USERPROFILE", ""),
                     r"OneDrive\Documents\My Games\Sid Meier's Civilization VI\Mods\TerraMirabilis2026"),
        os.path.join(os.environ.get("USERPROFILE", ""),
                     r"Documents\My Games\Sid Meier's Civilization VI\Mods\TerraMirabilis2026"),
    ]
    for c in candidates:
        if has_core(c):
            return os.path.abspath(c)
    raise SystemExit(
        "Could not find the Terra Mirabilis mod source (a folder containing Core/).\n"
        "Pass it explicitly:  python generator/generate.py --source \"C:\\\\path\\\\to\\\\mod\"\n"
        "or set the TM_MOD_DIR environment variable.")


ROOT = _resolve_mod_dir()   # mod source (input) — NOT part of this docs repo

# --------------------------------------------------------------------------
# Site configuration
# --------------------------------------------------------------------------

NOINDEX = False  # True -> ask search engines not to index (quiet link sharing)
SITE_URL = "https://cru121.github.io/terra-mirabilis-docs/"  # used only for sitemap.xml / robots.txt

ORIGINAL_URL = "https://github.com/deliverator23/TerraMirabilis"
ORIGINAL_AUTHORS = "Deliverator &amp; ChimpanG"
UPDATE_AUTHOR = "cru121"

# Prominent call-to-action links on the About page.
# /releases/latest always resolves to the newest release, so this link stays
# correct across future updates — no need to edit it when you ship a new version.
DOWNLOAD_URL = "https://github.com/cru121/civ6-tweaks/releases/latest"
MAINTAINER_GITHUB = "https://github.com/cru121/civ6-tweaks/tree/main/terra-mirabilis-2026"
WORKSHOP_URL = ""       # this mod is GitHub-only; set if it ever ships on the Steam Workshop
# The ORIGINAL Terra Mirabilis (support the original authors) — shown as small tiles.
ORIGINAL_WORKSHOP = "https://steamcommunity.com/sharedfiles/filedetails/?id=1461463960"


def read_mod_meta() -> dict:
    """Pull the display name / authors from the .modinfo, version from the README."""
    meta = {"name": "Terra Mirabilis", "authors": ORIGINAL_AUTHORS, "base": "2.21.3"}
    mi = glob.glob(os.path.join(ROOT, "*.modinfo"))
    if mi:
        txt = parse._read_text(mi[0])
        m = re.search(r"<Name>(.*?)</Name>", txt, re.DOTALL)
        if m:
            meta["name"] = re.sub(r"\[NEWLINE\]", " ", m.group(1)).strip()
    return meta


MOD = read_mod_meta()

# --------------------------------------------------------------------------
# Inline markup rendering ([ICON_*], [NEWLINE], {LOC_*}, [COLOR]…)
# --------------------------------------------------------------------------

# Token (case-insensitive on the part after ICON_) -> (emoji, label)
ICON_MAP = {
    "FOOD": ("🌾", "Food"),
    "PRODUCTION": ("🔨", "Production"),
    "GOLD": ("💰", "Gold"),
    "SCIENCE": ("🔬", "Science"),
    "CULTURE": ("🎭", "Culture"),
    "FAITH": ("✨", "Faith"),
    "HOUSING": ("🏠", "Housing"),
    "AMENITIES": ("😊", "Amenities"),
    "AMENITY": ("😊", "Amenity"),
    "TOURISM": ("🧳", "Tourism"),
    "GREATWORK": ("🖼️", "Great Work"),
    "GREATADMIRAL": ("⚓", "Great Admiral"),
    "GREATPERSON": ("🌟", "Great Person"),
    "TRADEROUTE": ("🔁", "Trade Route"),
    "CAPITAL": ("⭐", "Capital"),
    "STRENGTH": ("⚔️", "Strength"),
    "MOVEMENT": ("👣", "Movement"),
    "RANGEDSTRENGTH": ("🏹", "Ranged Strength"),
    "RELIGION": ("🙏", "Religion"),
    "GreatWork_Artifact".upper(): ("🏺", "Artifact"),
    "BULLET": ("•", ""),
}

_ICON_RE = re.compile(r"\[ICON_([A-Za-z0-9_]+)\]")
_COLOR_RE = re.compile(r"\[COLOR[^\]]*\]|\[ENDCOLOR\]", re.IGNORECASE)
_OTHER_TAG_RE = re.compile(r"\[/?[A-Za-z][^\]]*\]")
_TOKEN_RE = re.compile(r"\{(LOC_[A-Za-z0-9_]+)\}")
_RUNTIME_PARAM_RE = re.compile(r"\{\d+_[A-Za-z][A-Za-z0-9_]*\}")


def _icon_chip(token: str) -> str:
    key = token.upper()
    if key in ICON_MAP:
        emoji, label = ICON_MAP[key]
        return emoji if not label else f'<span class="ico" title="{html.escape(label)}">{emoji}</span>'
    if key.startswith("RESOURCE_"):
        return ""  # resource icons are always followed by the resource name in prose
    return ""  # unknown decorative icon -> drop rather than show broken markup


def resolve_tokens(text: str, loc: dict) -> str:
    def sub(m):
        return loc.get(m.group(1), "")
    for _ in range(4):
        new = _TOKEN_RE.sub(sub, text)
        if new == text:
            break
        text = new
    return text


def _clean(text: str, loc: dict) -> str:
    text = resolve_tokens(text, loc)
    text = _RUNTIME_PARAM_RE.sub("", text)
    text = html.escape(text)
    text = _ICON_RE.sub(lambda m: _icon_chip(m.group(1)), text)
    text = _COLOR_RE.sub("", text)
    text = _OTHER_TAG_RE.sub(lambda m: "\n" if m.group(0).upper() == "[NEWLINE]" else "", text)
    return text


def render_paras(loc_key: str, loc: dict) -> str:
    raw = loc.get(loc_key)
    if not raw:
        return ""
    text = _clean(raw, loc)
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paras)


def render_inline(loc_key: str, loc: dict) -> str:
    raw = loc.get(loc_key)
    if not raw:
        return ""
    return re.sub(r"\s+", " ", _clean(raw, loc).replace("\n", " ")).strip()


def text_of(loc_key: str, loc: dict) -> str:
    """Raw, UNescaped plain text (tokens resolved, markup + icons stripped).
    For card teasers, the search index and meta descriptions — callers escape it
    exactly once at the point of insertion, avoiding double-escaping (which turned
    an apostrophe into a literal '&#x27;')."""
    raw = loc.get(loc_key)
    if not raw:
        return ""
    t = resolve_tokens(raw, loc)
    t = _RUNTIME_PARAM_RE.sub("", t)
    t = t.replace("[NEWLINE]", " ")
    t = _ICON_RE.sub("", t)
    t = _COLOR_RE.sub("", t)
    t = _OTHER_TAG_RE.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------
# Names and content-pack labels
# --------------------------------------------------------------------------

# Base-game / expansion wonders keep their Firaxis names, which the mod does not
# ship in its own localisation — supply them here. New TM wonders resolve their
# name from the mod's LOC_*_NAME and never reach this table.
NAME_FALLBACK = {
    "FEATURE_BARRIER_REEF": "Great Barrier Reef",
    "FEATURE_CHOCOLATEHILLS": "Chocolate Hills",
    "FEATURE_CLIFFS_DOVER": "Cliffs of Dover",
    "FEATURE_CRATER_LAKE": "Crater Lake",
    "FEATURE_DEAD_SEA": "Dead Sea",
    "FEATURE_DELICATE_ARCH": "Delicate Arch",
    "FEATURE_DEVILSTOWER": "Mato Tipila (Devils Tower)",
    "FEATURE_EVEREST": "Mount Everest",
    "FEATURE_EYE_OF_THE_SAHARA": "Eye of the Sahara",
    "FEATURE_EYJAFJALLAJOKULL": "Eyjafjallajökull",
    "FEATURE_FOUNTAIN_OF_YOUTH": "Fountain of Youth",
    "FEATURE_GALAPAGOS": "Galápagos",
    "FEATURE_GIANTS_CAUSEWAY": "Giant's Causeway",
    "FEATURE_GOBUSTAN": "Gobustan",
    "FEATURE_HA_LONG_BAY": "Ha Long Bay",
    "FEATURE_IKKIL": "Ik-Kil Cenote",
    "FEATURE_KILIMANJARO": "Mount Kilimanjaro",
    "FEATURE_LAKE_RETBA": "Lake Retba",
    "FEATURE_LYSEFJORDEN": "Lysefjorden",
    "FEATURE_MATTERHORN": "Matterhorn",
    "FEATURE_PAITITI": "Paititi",
    "FEATURE_PAMUKKALE": "Pamukkale",
    "FEATURE_PANTANAL": "Pantanal",
    "FEATURE_PIOPIOTAHI": "Piopiotahi (Milford Sound)",
    "FEATURE_RORAIMA": "Mount Roraima",
    "FEATURE_TSINGY": "Tsingy de Bemaraha",
    "FEATURE_UBSUNUR_HOLLOW": "Ubsunur Hollow",
    "FEATURE_ULURU": "Uluru",
    "FEATURE_VESUVIUS": "Mount Vesuvius",
    "FEATURE_WHITEDESERT": "Sahara el Beyda (White Desert)",
    "FEATURE_YOSEMITE": "Yosemite",
    "FEATURE_ZHANGYE_DANXIA": "Zhangye Danxia",
}

# Which game content a wonder needs, and the rank used to pick the minimum
# (earliest) requirement when a wonder has yield rows for several rulesets.
DLC_LABEL = {
    "BASE": "Base game",
    "DLC2": "Vikings Scenario Pack",
    "DLC3": "Australia Pack",
    "DLC6": "Khmer &amp; Indonesia Pack",
    "DLC7": "Maya &amp; Gran Colombia Pack",
    "XP1": "Rise &amp; Fall",
    "XP2": "Gathering Storm",
}
DLC_SHORT = {
    "BASE": "Base", "DLC2": "DLC", "DLC3": "DLC", "DLC6": "DLC", "DLC7": "DLC",
    "XP1": "R&amp;F", "XP2": "GS",
}
DLC_RANK = {"BASE": 0, "DLC2": 1, "DLC3": 2, "DLC6": 3, "DLC7": 4, "XP1": 5, "XP2": 6}

YIELD_EMOJI = {
    "YIELD_FOOD": ("🌾", "Food"),
    "YIELD_PRODUCTION": ("🔨", "Production"),
    "YIELD_GOLD": ("💰", "Gold"),
    "YIELD_SCIENCE": ("🔬", "Science"),
    "YIELD_CULTURE": ("🎭", "Culture"),
    "YIELD_FAITH": ("✨", "Faith"),
}

TERRAIN_LABEL = {
    "GRASS": "Grassland", "PLAINS": "Plains", "DESERT": "Desert",
    "TUNDRA": "Tundra", "SNOW": "Snow", "COAST": "Coast", "OCEAN": "Ocean",
}


def terrain_label(tok: str) -> str:
    if tok.endswith("_HILLS"):
        return TERRAIN_LABEL.get(tok[:-6], tok[:-6].title()) + " Hills"
    if tok.endswith("_MOUNTAIN"):
        return TERRAIN_LABEL.get(tok[:-9], tok[:-9].title()) + " Mountains"
    return TERRAIN_LABEL.get(tok, tok.replace("_", " ").title())


def slug_of(feature: str) -> str:
    return feature[len("FEATURE_"):].lower().replace("_", "-")


# A few wonders' FeatureType is spelled differently from the stem used in their
# localisation keys (e.g. FEATURE_CHOCOLATEHILLS but LOC_..._CHOCOLATE_HILLS_...).
STEM_ALIAS = {
    "FEATURE_CHOCOLATEHILLS": "CHOCOLATE_HILLS",
    "FEATURE_IKKIL": "IK_KIL",
    "FEATURE_WHITEDESERT": "SAHARA_EL_BEYDA",
}


def stem_of(feature: str) -> str:
    return STEM_ALIAS.get(feature, feature[len("FEATURE_"):])


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

class Wonder:
    def __init__(self, feature):
        self.feature = feature
        self.slug = slug_of(feature)
        self.new = False
        self.reqs = set()
        self.yields = {}          # YIELD_TYPE -> amount (current ruleset)
        self.master = None        # TM_Master row (new wonders only)
        self.terrains = []        # valid terrain tokens
        self.impassable = False   # impassable => tile yields land on ADJACENT plots

    @property
    def name(self):
        return self._name

    @property
    def required(self):
        if not self.reqs:
            return "BASE"
        return min(self.reqs, key=lambda r: DLC_RANK.get(r, 99))


def build_model(tables, loc):
    wonders = {}

    def get(f):
        return wonders.setdefault(f, Wonder(f))

    for r in tables.get("TM_FeatureYields", []):
        f = r.get("FeatureType")
        if not f:
            continue
        w = get(f)
        if r.get("Version") == "TERRA_MIRABILIS":
            w.new = True
        if r.get("Required"):
            w.reqs.add(r["Required"])
        # Current-ruleset tile yields: skip rows the game removes under an expansion.
        if r.get("Removed") in (None, "",):
            yt = r.get("YieldType")
            try:
                amt = int(r.get("YieldChange"))
            except (TypeError, ValueError):
                amt = None
            if yt and amt:
                w.yields[yt] = w.yields.get(yt, 0) + amt
            if str(r.get("Impassable")) == "1":
                w.impassable = True

    for r in tables.get("TM_Master", []):
        f = r.get("FeatureType")
        if f:
            w = get(f)
            w.new = True
            w.master = r
            if str(r.get("Impassable")) == "1":
                w.impassable = True

    for r in tables.get("TM_Placement", []):
        if r.get("Reference") == "VALID_TERRAINS" and r.get("Type") == "TERRAIN":
            f = r.get("FeatureType")
            if f in wonders and r.get("Object") not in wonders[f].terrains:
                wonders[f].terrains.append(r["Object"])

    def first_key(candidates):
        """Return the first localisation key that actually exists."""
        for k in candidates:
            if loc.get(k):
                return k
        return candidates[0]

    for f, w in wonders.items():
        stem = stem_of(f)
        loc_name = loc.get(f"LOC_FEATURE_{stem}_NAME") or loc.get(f"LOC_TM_FEATURE_{stem}_NAME")
        w._name = loc_name or NAME_FALLBACK.get(f) or stem.replace("_", " ").title()
        # Some wonders only ship expansion-specific text (e.g. Krakatoa's base
        # DESCRIPTION/EFFECT are absent; only the XP2/XP1 variants exist).
        w.desc_key = first_key([
            f"LOC_TM_FEATURE_{stem}_DESCRIPTION",
            f"LOC_TM_FEATURE_{stem}_XP2_DESCRIPTION",
            f"LOC_TM_FEATURE_{stem}_XP1_DESCRIPTION",
        ])
        w.effect_key = first_key([
            f"LOC_TM_FEATURE_{stem}_EFFECT",
            f"LOC_TM_FEATURE_{stem}_EFFECT_XP2",
            f"LOC_TM_FEATURE_{stem}_EFFECT_XP1",
            f"LOC_TM_FEATURE_{stem}_XP2_EFFECT",
        ])
        w.desc = render_paras(w.desc_key, loc)
        w.effect = render_paras(w.effect_key, loc)
        w.desc_text = text_of(w.desc_key, loc)
        w.effect_text = text_of(w.effect_key, loc)
        # The mod's own wording ("... impassable natural wonder ...") is the most
        # reliable signal for reworked wonders that carry no TM_FeatureYields rows.
        if "impassable" in w.desc_text.lower():
            w.impassable = True
        w.quote = render_inline(f"LOC_TM_FEATURE_{stem}_QUOTE", loc)
        w.history = [render_paras(k, loc) for k in (
            f"LOC_PEDIA_FEATURES_PAGE_FEATURE_{stem}_CHAPTER_HISTORY_PARA_1",
            f"LOC_PEDIA_FEATURES_PAGE_FEATURE_{stem}_CHAPTER_HISTORY_PARA_2",
            f"LOC_PEDIA_FEATURES_PAGE_FEATURE_{stem}_CHAPTER_HISTORY_PARA_3",
        )]
        w.history = [h for h in w.history if h]
        w.search = " ".join(filter(None, [w._name, w.desc_text, w.effect_text])).lower()

    return sorted(wonders.values(), key=lambda w: w._name)


# --------------------------------------------------------------------------
# HTML building blocks
# --------------------------------------------------------------------------

def page(title, body, *, depth=0, desc="", active=""):
    """Wrap body in the site shell. depth = how many folders deep (for asset paths)."""
    up = "../" * depth
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    robots = '<meta name="robots" content="noindex, nofollow">' if NOINDEX else ""
    metadesc = f'<meta name="description" content="{html.escape(desc)}">' if desc else ""
    nav = "".join(
        f'<a href="{up}{href}" class="{"active" if active == key else ""}">{label}</a>'
        for key, href, label in (("home", "index.html", "Wonders"),
                                  ("about", "about.html", "About the mod"))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{robots}
{metadesc}
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{up}assets/style.css">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{up}index.html">🌋 <span>Terra Mirabilis</span></a>
  <nav class="topnav">{nav}</nav>
</header>
<main>
{body}
</main>
<footer class="site-footer">
  <p>Unofficial fan reference for <a href="{ORIGINAL_URL}" target="_blank" rel="noopener">Terra Mirabilis</a>,
     a Civilization VI mod by {ORIGINAL_AUTHORS} (2026 community update by {UPDATE_AUTHOR}).
     Not affiliated with or endorsed by the original authors or Firaxis. All wonder designs, text and art belong to their creators.</p>
  <p class="muted">Generated {stamp} from the mod's own data files.</p>
</footer>
</body>
</html>"""


def badge(text, kind=""):
    cls = f"badge {kind}".strip()
    return f'<span class="{cls}">{text}</span>'


def wonder_badges(w, *, short=False):
    out = [badge("New", "new") if w.new else badge("Reworked", "rework")]
    req = w.required
    out.append(badge((DLC_SHORT if short else DLC_LABEL)[req], "dlc"))
    if not short:
        if w.master:
            tiles = w.master.get("Tiles")
            if tiles and str(tiles) != "1":
                out.append(badge(f"{tiles} tiles"))
            if str(w.master.get("Impassable")) == "1":
                out.append(badge("Impassable"))
            if str(w.master.get("AddsFreshWater")) == "1":
                out.append(badge("Fresh water", "water"))
            if str(w.master.get("Coast")) == "1":
                out.append(badge("Coastal", "water"))
    return "".join(out)


def yield_scope_label(w):
    """Where a wonder's tile yields land. Impassable wonders can't be worked, so
    the yields go to each ADJACENT plot; passable wonders yield on their own tile."""
    return "on adjacent tiles" if w.impassable else "on the wonder tile"


def yield_chips(w, *, scope=False):
    order = ["YIELD_FOOD", "YIELD_PRODUCTION", "YIELD_GOLD",
             "YIELD_SCIENCE", "YIELD_CULTURE", "YIELD_FAITH"]
    chips = []
    for yt in order:
        amt = w.yields.get(yt)
        if amt:
            emoji, label = YIELD_EMOJI[yt]
            chips.append(f'<span class="yield" title="{label}">{emoji}&nbsp;+{amt}</span>')
    if not chips:
        return ""
    scope_html = ""
    if scope:
        cls = "scope adj" if w.impassable else "scope tile"
        scope_html = f'<span class="{cls}">{yield_scope_label(w)}</span>'
    return f'<div class="yields">{"".join(chips)}{scope_html}</div>'


def card(w):
    teaser = w.effect_text or w.desc_text
    return f"""<a class="card" href="wonders/{w.slug}.html"
   data-name="{html.escape(w._name.lower())}" data-cat="{'new' if w.new else 'rework'}"
   data-req="{w.required}" data-search="{html.escape(w.search)}">
  <div class="card-head"><h3>{html.escape(w._name)}</h3></div>
  <div class="badges">{wonder_badges(w)}</div>
  {yield_chips(w, scope=True)}
  <p class="teaser">{html.escape(teaser[:160]) + ('…' if len(teaser) > 160 else '')}</p>
</a>"""


def build_index(wonders):
    new = [w for w in wonders if w.new]
    rework = [w for w in wonders if not w.new]
    intro = ("Terra Mirabilis reworks every Natural Wonder in Civilization&nbsp;VI and adds a set of "
             "brand-new ones. Browse each wonder's yields, special effect, placement rules and history "
             "below — no need to launch the game.")
    controls = f"""
<div class="controls">
  <input id="search" type="search" placeholder="Search wonders, yields or effects…" aria-label="Search">
  <div class="chips" id="filters">
    <button class="chip active" data-filter="all">All <span class="count">{len(wonders)}</span></button>
    <button class="chip" data-filter="new">New <span class="count">{len(new)}</span></button>
    <button class="chip" data-filter="rework">Reworked <span class="count">{len(rework)}</span></button>
  </div>
</div>"""

    def section(title, sub, items, anchor):
        cards = "".join(card(w) for w in items)
        return f"""<section id="{anchor}">
  <h2>{title} <span class="muted">· {len(items)}</span></h2>
  <p class="section-sub">{sub}</p>
  <div class="grid">{cards}</div>
</section>"""

    body = f"""
<section class="hero">
  <h1>Natural Wonders of Terra Mirabilis</h1>
  <p class="lede">{intro}</p>
</section>
{controls}
<p class="noresults" id="noresults" hidden>No wonders match your search.</p>
{section("New wonders", "Fan-favourite wonders this mod adds to the game.", new, "new")}
{section("Reworked wonders", "Base-game and expansion wonders, rebalanced by the mod.", rework, "reworked")}
<script>
(function(){{
  var q=document.getElementById('search'), chips=document.querySelectorAll('#filters .chip');
  var cards=[].slice.call(document.querySelectorAll('.card'));
  var sections=[].slice.call(document.querySelectorAll('main section[id]'));
  var nores=document.getElementById('noresults');
  var filter='all', term='';
  function apply(){{
    var shown=0;
    cards.forEach(function(c){{
      var okCat = filter==='all' || c.dataset.cat===filter;
      var okTerm = !term || c.dataset.search.indexOf(term)>-1 || c.dataset.name.indexOf(term)>-1;
      var vis = okCat && okTerm; c.hidden=!vis; if(vis) shown++;
    }});
    sections.forEach(function(s){{
      var any=s.querySelector('.card:not([hidden])'); s.hidden=!any;
    }});
    nores.hidden = shown>0;
  }}
  q.addEventListener('input', function(){{ term=q.value.trim().toLowerCase(); apply(); }});
  chips.forEach(function(ch){{ ch.addEventListener('click', function(){{
    chips.forEach(function(o){{o.classList.remove('active');}}); ch.classList.add('active');
    filter=ch.dataset.filter; apply();
  }});}});
}})();
</script>"""
    return page("Terra Mirabilis — Natural Wonders reference", body, active="home",
                desc="Browse every Terra Mirabilis natural wonder — yields, effects, placement and history.")


def cta(url, label, sub, primary=False):
    cls = "cta primary" if primary else "cta"
    if url:
        return (f'<a class="{cls}" href="{url}" target="_blank" rel="noopener">'
                f'<span class="cta-label">{label}</span><span class="cta-sub">{sub}</span></a>')
    return (f'<span class="{cls} disabled" title="Link not set yet">'
            f'<span class="cta-label">{label}</span><span class="cta-sub">link coming soon</span></span>')


def mini_tile(url, label):
    """A small, non-prominent link tile (e.g. the original mod's pages)."""
    if not url:
        return ""
    return f'<a class="mini-tile" href="{url}" target="_blank" rel="noopener">{label}</a>'


def build_about(wonders):
    new = sum(1 for w in wonders if w.new)
    # Each mechanic is (title, description, is_new). New-to-the-2026-update
    # mechanics get a "New" tag and accent styling, and lead the grid.
    mechanics = [
        ("Terrain-type interactions",
         "Many wonders visually <strong>are</strong> a terrain type but are coded as their own feature, "
         "so effects that key on the real type used to ignore them. This update teaches them across five "
         "classes — e.g. <strong>Mountain</strong> wonders feed adjacent Terrace Farms, <strong>Reef</strong> "
         "powers an Aquarium, <strong>Geothermal</strong> wonders enable Thermal Baths, and "
         "<strong>Marsh</strong> / <strong>Lake</strong> wonders unlock their matching pantheons and wonders.",
         True),
        ("Wonders power up your districts",
         "Every Natural Wonder gives a <strong>standard +1 adjacency bonus</strong> to an adjacent "
         "Specialty District — Holy Site (Faith), Campus (Science), Theater (Culture), "
         "Industrial Zone (Production), and Commercial Hub / Harbor (Gold).",
         False),
        ("...and their buildings",
         "Buildings inside a Specialty District that sits next to a Natural Wonder gain "
         "<strong>+1 to the district's base yield</strong>, so a wonder-side district keeps scaling.",
         False),
        ("More wonders on every map",
         "The number of Natural Wonders per map size is <strong>roughly doubled</strong> "
         "(e.g. 10 instead of 5 on a Standard map — placement permitting), and they may spawn "
         "a little closer together.",
         False),
        ("Ownership effects",
         "Most wonders grant a unique <strong>ownership effect</strong> to whoever controls a tile "
         "(shown on each wonder's page), on top of their tile yields.",
         False),
        ("National Parks pull their weight",
         "National Parks provide <strong>Gold equal to their Tourism</strong> and extra Amenities to "
         "their city.",
         False),
        ("A livelier settle race",
         "Wonders are more desirable to the AI (higher adjacent fertility) and grant more Era Score "
         "and reveal XP, so racing to a wonder matters more.",
         False),
    ]

    def mech_card(t, d, is_new):
        cls = "mech is-new" if is_new else "mech"
        tag = '<span class="new-tag">New</span>' if is_new else ""
        return f'<div class="{cls}">{tag}<h3>{t}</h3><p>{d}</p></div>'

    mech_html = "".join(mech_card(*m) for m in mechanics)

    # Release history is maintained by hand — the generator reads the mod's data
    # files, not GitHub. Add the newest release at the top when one ships.
    v2_fixes = [
        "<strong>Ubsunur Hollow</strong> — earning a Great General now grants its free Inspiration, "
        "delivered by the mod's first gameplay script (the original data-only effect could only ever "
        "grant a Eureka).",
    ]
    v1_fixes = [
        "<strong>Mount Kailash</strong> — culture no longer stacks endlessly on every save/reload.",
        "<strong>Krakatoa</strong> — earning a Great Admiral now actually grants its free Eureka.",
        "<strong>Matterhorn</strong> &amp; <strong>Grand Mesa</strong> — their movement effects now work "
        "and are visible as unit abilities.",
        "<strong>Victoria Falls</strong> — placement loosened so it reliably spawns.",
        "<strong>Lençóis Maranhenses</strong> — yields now apply in the base game, not only Gathering Storm.",
    ]
    fixes_list = lambda items: "".join(f"<li>{f}</li>" for f in items)
    v2_fixes_html, v1_fixes_html = fixes_list(v2_fixes), fixes_list(v1_fixes)

    # Original-mod links now live as tiles up top, so the credits carry no links.
    lower_html = ""

    body = f"""
<section class="hero">
  <h1>About Terra Mirabilis</h1>
  <p class="lede">Terra Mirabilis is a Civilization&nbsp;VI mod that <strong>reworks every Natural
  Wonder</strong> and adds {new} brand-new ones — richer yields, unique ownership effects, and
  wonders that finally interact with your empire. This is the community <strong>2026 bug-fix
  update</strong> of the original mod.</p>
</section>

<div class="cta-row">
  {cta(DOWNLOAD_URL, "⬇ Download the mod", "Latest release ZIP", primary=True)}
  {cta(MAINTAINER_GITHUB, "◧ View on GitHub", "Source, notes &amp; issues")}
  {cta(WORKSHOP_URL, "★ Steam Workshop", "Subscribe &amp; rate") if WORKSHOP_URL else ""}
</div>
<div class="mini-row">
  <span class="mini-label">The original mod:</span>
  {mini_tile(ORIGINAL_WORKSHOP, "★ Steam Workshop")}
  {mini_tile(ORIGINAL_URL, "◧ GitHub")}
</div>

<section class="block">
  <h2>Install</h2>
  <p class="section-sub">This is a drop-in mod folder — no Steam Workshop subscription needed.</p>
  <ol class="install">
    <li><strong>Download</strong> the latest release ZIP (it contains the full mod, including art).</li>
    <li><strong>Extract</strong> the <code>TerraMirabilis2026</code> folder into your Civ&nbsp;VI
      <strong>Mods</strong> directory:<br>
      <code>Documents\\My Games\\Sid Meier's Civilization VI\\Mods\\</code>
      (if your Documents are in OneDrive, it's under <code>OneDrive\\Documents\\…</code>).<br>
      You should end up with <code>…\\Mods\\TerraMirabilis2026\\</code> containing
      <code>NaturalWondersMod.modinfo</code>.</li>
    <li><strong>Enable</strong> it in-game: <em>Additional Content → Terra Mirabilis (2026 update)</em>.</li>
  </ol>
  <p class="note"><strong>Don't run it alongside the original Terra Mirabilis</strong> — disable or
  unsubscribe the original first (this update ships a fresh mod id, so the game would otherwise try to
  load both). It works with any mix of DLC and expansions; content gates itself to what you own.</p>
</section>

<section class="block">
  <h2>The 2026 community update</h2>
  <p class="section-sub">An unofficial continuation of the abandoned original, fixing long-standing
  Workshop-reported bugs. It ships as GitHub releases — <strong>two so far</strong> — and the
  download button above always grabs the newest.</p>
  <p><strong>Latest release (v2)</strong> adds one more fix on top of v1:</p>
  <ul class="fixes">{v2_fixes_html}</ul>
  <p><strong>First release (v1)</strong> fixed a batch of long-standing bugs:</p>
  <ul class="fixes">{v1_fixes_html}</ul>
</section>

<section class="block">
  <h2>How the mod works</h2>
  <p class="section-sub">Beyond each wonder's own yields and effect, Terra Mirabilis changes some
  universal rules of the game:</p>
  <div class="mech-grid">{mech_html}</div>
  <p class="note">Nearly all of this is <strong>configurable</strong> — the mod ships a settings file
  where each of these can be toggled or tuned, and individual wonders can be turned off. Defaults are
  described above.</p>
</section>

<section class="block credits">
  <h2>Credits</h2>
  <p>Original <strong>Terra Mirabilis</strong> by {ORIGINAL_AUTHORS} (special thanks CIVITAS).
  Unofficial 2026 update by {UPDATE_AUTHOR}. Not affiliated with or endorsed by the original authors,
  Firaxis or 2K. All wonder designs, text and art belong to their creators.</p>
  {f'<p class="muted small">{lower_html}</p>' if lower_html else ""}
</section>"""
    return page("About — Terra Mirabilis", body, active="about",
                desc="What Terra Mirabilis is, its universal mechanics, and the 2026 community update.")


def dl(pairs):
    rows = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in pairs if v)
    return f'<dl class="facts">{rows}</dl>' if rows else ""


def build_detail(w, wonders):
    facts = []
    facts.append(("Requires", DLC_LABEL[w.required]))
    facts.append(("Category", "New wonder (added by Terra Mirabilis)" if w.new
                  else "Reworked base-game wonder"))
    facts.append(("Passability",
                  "Impassable — can't be worked, so its tile yields go to adjacent plots"
                  if w.impassable else "Passable — its tile can be worked for the yields below"))
    if w.master:
        tiles = str(w.master.get("Tiles") or "1")
        facts.append(("Size", f"{tiles} tile" + ("s" if tiles != "1" else "")))
        extras = []
        if str(w.master.get("AddsFreshWater")) == "1":
            extras.append("provides fresh water")
        if str(w.master.get("Coast")) == "1":
            extras.append("must be coastal")
        if str(w.master.get("Lake")) == "1":
            extras.append("forms a lake")
        if str(w.master.get("RequiresRiver")) == "1":
            extras.append("sits on a river")
        if extras:
            facts.append(("Notes", ", ".join(extras).capitalize()))
    if w.terrains:
        friendly = ", ".join(sorted({terrain_label(t) for t in w.terrains}))
        facts.append(("Spawns on", friendly))

    quote = f'<blockquote class="quote">{w.quote}</blockquote>' if w.quote else ""
    effect_block = ""
    if w.effect:
        effect_block = f'<section class="block"><h2>Special effect</h2>{w.effect}</section>'
    desc_block = ""
    if w.desc:
        desc_block = f'<section class="block"><h2>Overview</h2>{w.desc}</section>'
    hist_block = ""
    if w.history:
        hist_block = f'<section class="block history"><h2>History</h2>{"".join(w.history)}</section>'

    yields = yield_chips(w, scope=True)
    if yields:
        caption = ("Each adjacent tile gains these yields — the wonder tile itself is impassable."
                   if w.impassable else "The wonder's own tile gains these yields.")
        yields_block = f'<div class="detail-yields">{yields}<p class="scope-caption">{caption}</p></div>'
    else:
        yields_block = ""

    body = f"""
<p class="crumb"><a href="../index.html">← All wonders</a></p>
<article class="detail">
  <header class="detail-head">
    <h1>{html.escape(w._name)}</h1>
    <div class="badges">{wonder_badges(w)}</div>
    {yields_block}
  </header>
  {quote}
  {desc_block}
  {effect_block}
  <section class="block"><h2>Placement &amp; requirements</h2>{dl(facts)}</section>
  {hist_block}
</article>"""
    metadesc = w.effect_text or w.desc_text
    return page(f"{w._name} — Terra Mirabilis", body, depth=1, desc=metadesc[:200])


# --------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------

STYLE = """
:root{
  --bg:#f6f4ef; --panel:#fffdf9; --ink:#20242b; --muted:#6b7280; --line:#e4ded2;
  --accent:#2f7d5b; --accent2:#b4622a; --new:#2f7d5b; --rework:#b4622a; --water:#2f6d99;
  --shadow:0 1px 2px rgba(20,24,30,.05),0 6px 20px rgba(20,24,30,.06);
}
@media (prefers-color-scheme:dark){
  :root{ --bg:#14171c; --panel:#1c2027; --ink:#e8eaed; --muted:#9aa2ad; --line:#2b313a;
    --accent:#57b98a; --accent2:#d98a53; --new:#57b98a; --rework:#d98a53; --water:#5aa2d6;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.35); }
}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.muted{color:var(--muted)}
.site-header{display:flex;align-items:center;gap:14px;padding:14px 20px;
  border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:5}
.brand{font-weight:700;font-size:19px;color:var(--ink);display:flex;align-items:center;gap:8px}
.brand:hover{text-decoration:none}
.topnav{display:flex;gap:6px;margin-left:auto}
.topnav a{color:var(--muted);font-size:14px;font-weight:600;padding:6px 12px;border-radius:8px}
.topnav a:hover{text-decoration:none;background:var(--bg);color:var(--ink)}
.topnav a.active{color:var(--ink);background:var(--bg)}
main{max-width:1080px;margin:0 auto;padding:24px 20px 48px}
.hero h1{font-size:30px;margin:8px 0 6px;letter-spacing:-.01em}
.lede{font-size:18px;color:var(--muted);max-width:70ch;margin:0}
.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:24px 0 8px;
  position:sticky;top:57px;background:var(--bg);padding:10px 0;z-index:4}
#search{flex:1 1 280px;min-width:0;padding:10px 14px;border:1px solid var(--line);
  border-radius:10px;background:var(--panel);color:var(--ink);font-size:15px}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;
  padding:8px 14px;border-radius:999px;font-size:14px;font-weight:600}
.chip .count{color:var(--muted);font-weight:600;margin-left:4px}
.chip.active{background:var(--accent);border-color:var(--accent);color:#fff}
.chip.active .count{color:rgba(255,255,255,.85)}
section{margin-top:28px}
section h2{font-size:20px;margin:0 0 2px}
.section-sub{margin:0 0 14px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{display:flex;flex-direction:column;gap:8px;background:var(--panel);border:1px solid var(--line);
  border-radius:14px;padding:16px;color:var(--ink);box-shadow:var(--shadow);transition:transform .08s,border-color .08s}
.card:hover{text-decoration:none;transform:translateY(-2px);border-color:var(--accent)}
.card-head h3{margin:0;font-size:17px}
.badges{display:flex;flex-wrap:wrap;gap:6px}
.badge{font-size:11.5px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;
  padding:3px 8px;border-radius:6px;background:var(--line);color:var(--ink)}
.badge.new{background:color-mix(in srgb,var(--new) 20%,transparent);color:var(--new)}
.badge.rework{background:color-mix(in srgb,var(--rework) 20%,transparent);color:var(--rework)}
.badge.dlc{background:transparent;border:1px solid var(--line);color:var(--muted)}
.badge.water{background:color-mix(in srgb,var(--water) 20%,transparent);color:var(--water)}
.yields{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.yield{font-size:13px;font-weight:600;background:var(--bg);border:1px solid var(--line);
  padding:2px 8px;border-radius:7px;white-space:nowrap}
.scope{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;
  padding:2px 7px;border-radius:6px}
.scope.tile{background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--accent)}
.scope.adj{background:color-mix(in srgb,var(--accent2) 18%,transparent);color:var(--accent2)}
.scope-caption{margin:8px 0 0;font-size:13px;color:var(--muted)}
.teaser{margin:2px 0 0;color:var(--muted);font-size:14px}
.noresults{color:var(--muted);margin-top:20px}
.ico{font-style:normal}
/* detail */
.crumb{margin:0 0 12px}
.detail{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:26px 28px;box-shadow:var(--shadow);max-width:820px}
.detail-head h1{margin:0 0 10px;font-size:28px}
.detail-yields{margin-top:12px}
.detail-yields .yields{gap:8px}
.detail-yields .yield{font-size:15px;padding:4px 10px}
.block{margin-top:24px}
.block h2{font-size:16px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
  border-bottom:1px solid var(--line);padding-bottom:6px;margin:0 0 10px}
.block p{margin:0 0 10px}
.quote{margin:20px 0 0;padding:12px 18px;border-left:3px solid var(--accent2);
  color:var(--muted);font-style:italic}
.facts{display:grid;grid-template-columns:1fr;gap:0;margin:0}
.facts>div{display:grid;grid-template-columns:150px 1fr;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}
.facts>div:last-child{border-bottom:0}
.facts dt{margin:0;color:var(--muted);font-weight:600}
.facts dd{margin:0}
.history p{color:var(--ink)}
/* about page */
.cta-row{display:flex;flex-wrap:wrap;gap:14px;margin:22px 0 8px}
.cta{display:flex;flex-direction:column;gap:2px;padding:14px 22px;border-radius:12px;
  border:1px solid var(--line);background:var(--panel);color:var(--ink);min-width:220px;
  box-shadow:var(--shadow)}
.cta:hover{text-decoration:none;border-color:var(--accent);transform:translateY(-2px)}
.cta.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.cta.primary .cta-sub{color:rgba(255,255,255,.85)}
.cta-label{font-size:17px;font-weight:700}
.cta-sub{font-size:13px;color:var(--muted)}
.cta.disabled{opacity:.55;cursor:not-allowed;box-shadow:none}
.mini-row{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:12px 0 4px}
.mini-label{font-size:13px;color:var(--muted)}
.mini-tile{font-size:13px;font-weight:600;color:var(--muted);padding:6px 12px;border-radius:9px;
  border:1px solid var(--line);background:var(--panel)}
.mini-tile:hover{text-decoration:none;border-color:var(--accent);color:var(--ink)}
.mech-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:6px}
.mech{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.mech h3{margin:0 0 6px;font-size:15px}
.mech p{margin:0;color:var(--muted);font-size:14px}
.mech.is-new{border-color:var(--new);background:color-mix(in srgb,var(--new) 8%,var(--panel))}
.mech.is-new h3{color:var(--new)}
.new-tag{display:inline-block;margin:0 0 8px;padding:2px 8px;border-radius:6px;background:var(--new);
  color:#fff;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase}
.note{margin-top:16px;padding:12px 16px;border-radius:10px;
  background:color-mix(in srgb,var(--accent) 8%,transparent);border:1px solid var(--line);font-size:14px}
.fixes{margin:0;padding-left:20px}
.fixes li{margin:6px 0}
.install{margin:0;padding-left:22px}
.install li{margin:10px 0}
code{background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:1px 6px;
  font-size:13px;font-family:ui-monospace,"Cascadia Code",Consolas,monospace}
.credits p{max-width:75ch}
.small{font-size:13px}
.site-footer{max-width:1080px;margin:0 auto;padding:24px 20px 40px;color:var(--muted);font-size:13px}
.site-footer p{margin:4px 0;max-width:80ch}
@media (max-width:520px){
  .facts>div{grid-template-columns:1fr;gap:2px}
  .controls{position:static}
}
"""


def write(relpath, content):
    dest = os.path.join(DOCS, relpath)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def build_sitemap(wonders):
    base = SITE_URL.rstrip("/") + "/"
    urls = [base, f"{base}about.html"] + [f"{base}wonders/{w.slug}.html" for w in wonders]
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}</urlset>\n")


# --------------------------------------------------------------------------

LOC = {}


def main():
    global LOC
    print("Reading mod data...")
    tables = parse.load_sql_tree(os.path.join(ROOT, "Core"))
    LOC = parse.load_text(tables)
    wonders = build_model(tables, LOC)
    new = sum(1 for w in wonders if w.new)
    print(f"  {len(wonders)} wonders ({new} new, {len(wonders) - new} reworked)")

    write("index.html", build_index(wonders))
    write("about.html", build_about(wonders))
    for w in wonders:
        write(f"wonders/{w.slug}.html", build_detail(w, wonders))
    write("assets/style.css", STYLE)
    write(".nojekyll", "")
    write("sitemap.xml", build_sitemap(wonders))
    write("robots.txt", "User-agent: *\n" +
          ("Disallow: /\n" if NOINDEX else f"Allow: /\nSitemap: {SITE_URL.rstrip('/')}/sitemap.xml\n"))
    print(f"  wrote {len(wonders) + 6} files into docs/")
    print("Done.")


if __name__ == "__main__":
    main()
