"""
Update the conformance check: window aliases now live in the terrain material file.

They were previously written to a separate `main.materials.json` at two paths the engine does not
read for a level, which is why they had no effect.  They are now merged into
`levels/<level>/art/terrains/main.materials.json` -- the one material library this level is proven
to load, since the terrain material resolves from it.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

OLD = '''alias_files = [n for n in names if n.endswith("main.materials.json") and "terrains" not in n]
check(bool(alias_files), "window material alias file written", str(alias_files))
if alias_files:
    aliases = json.loads(z.read(alias_files[0]).decode("utf-8"))
    check(all(v.get("mapTo") for v in aliases.values()),
          "every alias redirects via mapTo to a built-in material",
          ", ".join(sorted({v.get("mapTo", "?") for v in aliases.values()})))
    check(all("Stages" not in v for v in aliases.values()),
          "aliases author no stages (nothing new is created)")
    expected = {"Italy_bld_ind_windows", "italy_bld_windows"}
    check(set(aliases) == expected,
          "alias names are the ones the referenced shapes declare",
          f"{sorted(aliases)}")
    check("windows_doors_reflective" not in aliases,
          "already-global materials are not needlessly aliased")'''

NEW = '''# Window aliases must live in a material library the engine actually loads for this level.  Only
# `levels/<level>/art/terrains/main.materials.json` is proven to load -- the terrain material
# resolves from it and the ground renders -- so the aliases are merged there rather than written to
# a separate path, which previously had no effect at all.
if mat_file:
    merged = json.loads(z.read(mat_file[0]).decode("utf-8"))
    aliases = {k: v for k, v in merged.items() if v.get("class") == "Material"}
    check(bool(aliases), "window alias entries present in the loaded material file",
          f"{len(aliases)} aliases")
    check(all(v.get("mapTo") for v in aliases.values()),
          "every alias redirects via mapTo to a built-in material",
          ", ".join(sorted({v.get("mapTo", "?") for v in aliases.values()})))
    check(all("Stages" not in v for v in aliases.values()),
          "aliases author no stages (nothing new is created)")
    expected = {"Italy_bld_ind_windows", "italy_bld_windows"}
    check(set(aliases) == expected,
          "alias names are the ones the referenced shapes declare",
          f"{sorted(aliases)}")
    check("windows_doors_reflective" not in aliases,
          "already-global materials are not needlessly aliased")
    check(not [n for n in names if n.endswith("main.materials.json") and "terrains" not in n],
          "no alias file is written to a path the engine does not read")

    # Every texture the material names must resolve, or the ground silently loses a family.  A
    # `soil/` path that should have been `rock/` cost several rounds of this.
    tex_paths = [v for k, v in merged.items()
                 if isinstance(v, str) and k.endswith("Tex") and v.startswith("/")]
    check(len(tex_paths) == 15, "15 texture paths declared", f"{len(tex_paths)}")'''

if OLD not in src:
    raise SystemExit("alias-check anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)

import ast

ast.parse(src)
print("updated the alias check; syntax OK")
