"""
Update three rules that assumed "engine textures only".

They were written when the goal was strictly built-in content, and they now fail against the supplied
ground texture -- which is intentional and authorised.  Rather than loosening them into meaning
nothing, each is rewritten to state the actual current requirement:

* the ground colour may be the supplied image; everything else stays on the engine;
* the ground colour is the ONLY texture the mod ships;
* engine-referenced textures must all resolve in the install (the custom one is checked separately,
  against the mod itself, by the custom-ground-texture rule).
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

# ---- 1. the "5 local + 10 engine" split, then "all 15 engine" ---------------------------------
start = src.index("        # polish_roads_v2 ships five textures locally")
end = src.index('              "all base textures are tileable grass sets")', start)
end = src.index("\n", end) + 1

NEW1 = '''        # The ground COLOUR is the supplied image, shipped inside the level -- a level normally
        # provides its own large colour texture for this slot and the engine ships nothing green
        # enough.  The other 14 slots stay on engine content: normal, roughness, ao and height are
        # detail maps that modulate whatever colour is underneath, which is how engine materials are
        # built.  Those five base-family maps must therefore still resolve in the install.
        ground_local = [k for k in fields if mat[k].startswith("/levels/")]
        engine_ok = [k for k in fields if mat[k].startswith("/assets/")]
        check(len(ground_local) == 1,
              "exactly one texture is shipped in the level (the ground colour)",
              f"shipped: {sorted(ground_local)}")
        check(len(engine_ok) == 14,
              "the other 14 texture slots reference engine content",
              f"engine-referenced: {len(engine_ok)}")
        check(
            "t_grass_ground_b" in str(mat.get("baseColorBaseTex", "")),
            "the ground colour slot points at the supplied texture",
            str(mat.get("baseColorBaseTex")),
        )
'''
src = src[:start] + NEW1 + src[end:]

# ---- 2. "no texture is copied into the mod" ---------------------------------------------------
OLD2 = '''check(len([n for n in names if n.endswith(".png") and "art/terrains" in n]) == 0,
      "no texture is copied into the mod")'''
NEW2 = '''shipped_textures = [
    n for n in names
    if n.lower().endswith(".png") and "art/terrains" in n.lower()
    and "t_grass_ground_b" not in n.lower()
]
check(not shipped_textures,
      "the mod ships no texture other than the supplied ground colour",
      f"{shipped_textures}" if shipped_textures else "one texture shipped, as intended")'''
if OLD2 not in src:
    raise SystemExit("copied-texture rule anchor not found")
src = src.replace(OLD2, NEW2, 1)

# ---- 3. "every base texture resolves in the install" ------------------------------------------
OLD3 = """        check(not missing, "every base texture resolves in the install", f"{len(missing)} missing")"""
NEW3 = """        # The shipped ground colour is checked against the mod by its own rule below, so it is
        # excluded here; everything else must come from the install.
        missing = [p for p in missing if not p.startswith("/levels/")]
        check(not missing, "every ENGINE base texture resolves in the install",
              f"{len(missing)} missing" + (f": {missing[:3]}" if missing else ""))"""
if OLD3 not in src:
    raise SystemExit("resolve rule anchor not found")
src = src.replace(OLD3, NEW3, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("updated three rules; syntax OK")
