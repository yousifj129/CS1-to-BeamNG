"""
Side-by-side comparison of our level against working third-party maps.

Focuses on the two things still failing: the Roads group structure and the terrain material.
Prints the actual group tree of each map so the shapes can be compared directly, rather than
reasoned about.
"""

import json
import os
import re
import struct
import zipfile
from collections import Counter, defaultdict

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")

MAPS = [
    ("MINE", os.path.join(REPO, "dist", "cs1_cannes.zip"), "levels/Cannes/"),
    ("polish_roads_v2", os.path.join(REPO_MODS, "polish_roads_repo.zip"), "levels/polish_roads_v2/"),
    ("grille_mbwr_city", os.path.join(REPO_MODS, "grille_mbwr_city.zip"), "levels/grille_mbwr_city/"),
    ("Valo_City", os.path.join(REPO_MODS, "Valo_City.zip"), "levels/valo_city/"),
    ("Generic_City", os.path.join(REPO_MODS, "Generic_City.zip"), "levels/generic_city/"),
]


def read_objects(z, entry):
    text = z.read(entry).decode("utf-8", "replace")
    decoder = json.JSONDecoder()
    out, i = [], 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            o, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        out.append(o)
    return out


for label, path, prefix in MAPS:
    print("=" * 104)
    print(f"{label}   ({os.path.basename(path)})")
    print("=" * 104)
    if not os.path.isfile(path):
        print("   ARCHIVE NOT FOUND\n")
        continue

    z = zipfile.ZipFile(path)
    names = z.namelist()

    # figure out the real level prefix
    roots = sorted({m.group(1) for n in names
                    if (m := re.match(r"levels/([^/]+)/", n, re.I))})
    if prefix.rstrip("/") not in [f"levels/{r}" for r in roots]:
        match = [r for r in roots if r.lower() in prefix.lower() or prefix.lower().endswith(r.lower() + "/")]
        if match:
            prefix = f"levels/{match[0]}/"
    print(f"   level prefix: {prefix}   levels present: {roots}")

    items = [e for e in z.infolist()
             if e.filename.lower().startswith(prefix.lower())
             and e.filename.lower().endswith("items.level.json")]

    # --- road group structure -----------------------------------------------------------
    road_files = []
    for e in items:
        rel = e.filename[len(prefix):]
        objs = read_objects(z, e)
        classes = Counter(str(o.get("class")) for o in objs)
        if classes.get("DecalRoad") or "roads" in rel.lower():
            road_files.append((rel, classes, len(objs),
                               Counter(str(o.get("__parent")) for o in objs if o.get("class") != "SimGroup"),
                               [o.get("name") for o in objs if o.get("class") == "SimGroup"]))
    print(f"\n   ROAD-RELATED items.level.json files: {len(road_files)}")
    for rel, classes, count, parents, groups in road_files[:6]:
        print(f"     {rel}")
        print(f"        declares: {groups if groups else '(none)'}")
        print(f"        classes : {dict(classes)}")
        if parents:
            print(f"        parents : {dict(parents)}")

    # --- TerrainBlock -------------------------------------------------------------------
    for e in items:
        for o in read_objects(z, e):
            if o.get("class") == "TerrainBlock":
                keys = ["terrainFile", "materialTextureSet", "squareSize", "maxHeight", "position"]
                print(f"\n   TerrainBlock in {e.filename[len(prefix):]}")
                for k in keys:
                    if k in o:
                        print(f"      {k}: {o[k]}")

    # --- terrain material ---------------------------------------------------------------
    mat_entries = [e for e in z.infolist()
                   if e.filename.lower().startswith(prefix.lower())
                   and re.search(r"art/terrains?/main\.materials\.json$", e.filename, re.I)]
    for e in mat_entries[:1]:
        data = json.loads(z.read(e).decode("utf-8", "replace"))
        sets = [v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterialTextureSet"]
        mats = [v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterial"]
        print(f"\n   terrain material file: {e.filename[len(prefix):]}  ({len(mats)} materials)")
        for s in sets:
            print(f"      set: {s.get('name')}  base={s.get('baseTexSize')} detail={s.get('detailTexSize')} macro={s.get('macroTexSize')}")
        if mats:
            m = mats[0]
            print(f"      first material: name={m.get('name')!r} internalName={m.get('internalName')!r}")
            print(f"         keys: {sorted(m.keys())[:14]}")
            for k in sorted(m):
                if k.endswith("Tex") and isinstance(m[k], str):
                    kind = "LOCAL" if "/levels/" in m[k] else ("ENGINE" if m[k].startswith("/assets/") else "OTHER")
                    print(f"         {k:<24} {kind:<7} {m[k]}")
                    break

    # --- local terrain textures ---------------------------------------------------------
    tex = [e for e in z.infolist()
           if e.filename.lower().startswith(prefix.lower())
           and re.search(r"art/terrains?/[^/]*\.png$", e.filename, re.I)]
    sizes = Counter()
    for e in tex[:20]:
        raw = z.read(e)[:33]
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", raw[16:24])
            sizes[(w, h)] += 1
    print(f"\n   loose local terrain PNGs: {len(tex)}   sizes: {dict(sizes)}")

    z.close()
    print()
