# Terra Mirabilis — documentation site

An **unofficial, fan-made** player reference for the Civilization VI mod
**Terra Mirabilis** (2026 community update) — every Natural Wonder's yields,
special effect, placement rules, flavour and history, plus an About page with the
mod's universal mechanics and install steps. Browse any wonder without launching
the game.

All wonder designs, text and art belong to their creators: the original
**Terra Mirabilis** by **Deliverator** and **ChimpanG** (special thanks CIVITAS),
with the 2026 community bug-fix update by **cru121**. This repository holds only a
small generator and the web pages it produces — it is not affiliated with or
endorsed by the original authors or Firaxis.

## Live site

Served by GitHub Pages from the [`docs/`](docs/) folder:

> **https://cru121.github.io/terra-mirabilis-docs/**

The mod itself lives at
<https://github.com/cru121/civ6-tweaks/tree/main/terra-mirabilis-2026>.

## What's in here

| Path | What it is |
| --- | --- |
| `generator/parse.py` | Dependency-free SQL extraction (standard library only). |
| `generator/generate.py` | The generator: reads the mod's SQL and writes the site. |
| `docs/` | **The generated website** — what GitHub Pages serves (repo-root `/docs`). |
| `build-docs.ps1` | Convenience wrapper: find Python, rebuild `docs/`, optionally preview. |

The mod's own source files (`Core/`, art, `*.modinfo`) are **not** committed here
— that would redistribute the mod. The generator reads them from a separate mod
checkout at build time.

## Rebuilding after a mod change

Requires only **Python 3** (no third-party packages). The generator locates the
mod source automatically — a sibling `civ6-terra-mira` checkout, or the installed
mod — or you can point at it explicitly.

```powershell
.\build-docs.ps1                       # rebuild docs\ (auto-locate the mod)
.\build-docs.ps1 -Source "C:\path\to\mod"   # ...or point at the mod (folder with Core\)
.\build-docs.ps1 -Serve                # ...then preview at http://localhost:8791
```

Or call the generator directly:

```
python generator/generate.py --source "C:\path\to\mod"
```

Then commit and push `docs/`; the live site updates:

```
git add docs && git commit -m "Rebuild docs" && git push
```

## One-time GitHub Pages setup

Repo **Settings → Pages → Build and deployment → Deploy from a branch**, branch
**`main`**, folder **`/docs`**. The `docs/.nojekyll` file is already present so
GitHub serves the HTML as-is.

## Notes

- **`NOINDEX`** near the top of `generator/generate.py` (currently `False`) adds a
  `noindex` tag to every page when set `True` — reachable by link but kept out of
  search results.
- The pages use the game's own inline markup (`[ICON_*]`, `[NEWLINE]`) rendered to
  text + emoji chips; no mod art is redistributed.
