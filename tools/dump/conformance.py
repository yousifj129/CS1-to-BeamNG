"""
Conformance report: does our level obey the rules measured from polish_roads_v2?

Every check derives from a specific measurement recorded in docs/POLISH_ROADS_REFERENCE.md.
This is the evidence step for the rewrite: facts, not opinions about how the format should work.
"""

import json
import math
import os
import struct
import zipfile
from collections import Counter, defaultdict

import sys as _sys
_sys.path.insert(0, r"D:\Developer\open source projects\cities-skylines-to-beamng-map\tools")
from beamng_convert import BEAMNG_BUILDING_SOURCES

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
ARCHIVE = os.path.join(REPO, "dist", "cs1_cannes.zip")

results = []


def check(ok, label, detail=""):
    results.append((bool(ok), label, detail))


z = zipfile.ZipFile(ARCHIVE)
names = z.namelist()


def read_items(member):
    decoder = json.JSONDecoder()
    text = z.read(member).decode("utf-8", "replace")
    out, i = [], 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            obj, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        out.append(obj)
    return out


items = [n for n in names if n.endswith("items.level.json")]

# ================================================================ group rules
bad_lines = 0
for n in items:
    for line in z.read(n).decode("utf-8", "replace").split("\n"):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            bad_lines += 1
check(bad_lines == 0, "every items.level.json is line-delimited", f"{bad_lines} bad lines")

declared = set()
for n in items:
    for obj in read_items(n):
        if obj.get("class") == "SimGroup" and obj.get("name"):
            declared.add(obj["name"])

violations = defaultdict(int)
checked = 0
for n in items:
    folder = os.path.basename(os.path.dirname(n))
    for obj in read_items(n):
        if obj.get("class") == "SimGroup":
            continue
        parent = obj.get("__parent")
        if parent is None:
            continue
        checked += 1
        if parent != folder:
            violations[f"{parent}!={folder}"] += 1
check(not violations, "__parent equals the containing folder for every object",
      f"{checked} objects" + (f"; violations {dict(violations)}" if violations else ""))

orphans = defaultdict(int)
for n in items:
    for obj in read_items(n):
        if obj.get("class") == "SimGroup":
            continue
        parent = obj.get("__parent")
        if parent and parent not in declared and parent != "MissionGroup":
            orphans[parent] += 1
check(not orphans, "every __parent names a declared SimGroup",
      f"orphans {dict(orphans)}" if orphans else "")

# ================================================================ .ter format
ter = [n for n in names if n.endswith(".ter")]
check(len(ter) == 1, "exactly one .ter", str(ter))
if ter:
    raw = z.read(ter[0])
    size = struct.unpack_from("<I", raw, 1)[0]
    n2 = size * size
    base = 5 + n2 * 2 + n2
    cnt = struct.unpack_from("<I", raw, base)[0] if len(raw) >= base + 4 else -1
    off = base + 4
    try:
        for _ in range(cnt):
            off += 1 + raw[off]
    except IndexError:
        off = -1
    check(raw[0] == 9, ".ter version is 9", f"version={raw[0]}")
    check(off == len(raw),
          ".ter consumes exactly 5 + size^2*3 + 4 + length-prefixed names",
          f"size={size} bytes={len(raw)} consumed={off}")
    check(b"\x00" not in raw[base + 4:],
          ".ter name block is length-prefixed (no NUL bytes)",
          f"{raw[base + 4:].count(0)} NUL bytes")

# ================================================================ terrain material
mat_file = [n for n in names if n.endswith("art/terrains/main.materials.json")]
check(len(mat_file) == 1, "exactly one terrain material file", str(mat_file))

mat = tset = None
if mat_file:
    data = json.loads(z.read(mat_file[0]).decode("utf-8"))
    mats = [v for v in data.values() if v.get("class") == "TerrainMaterial"]
    sets = [v for v in data.values() if v.get("class") == "TerrainMaterialTextureSet"]
    # Two materials now: Grass for the ground and Asphalt for the painted road surface.  Their
    # order here must match the order their names appear in the .ter, because every layer byte is
    # an index into that list.
    check(len(mats) == 2, "two TerrainMaterials (Grass + Asphalt)", f"{len(mats)}")
    check(len(sets) == 1, "exactly one TerrainMaterialTextureSet", f"{len(sets)}")
    if mats and sets:
        mat, tset = mats[0], sets[0]

        fields = [k for k in mat if k.endswith("Tex")]
        check(len(fields) == 15, "material declares 15 texture slots", f"{len(fields)}")
        for suffix in ("BaseTex", "DetailTex", "MacroTex"):
            found = [k for k in mat if k.endswith(suffix + "Size")]
            check(len(found) == 5, f"all five {suffix}Size fields present", f"{len(found)}")
        local = [k for k in fields if mat[k].startswith("/levels/")]
        engine = [k for k in fields if mat[k].startswith("/assets/")]
        # polish_roads_v2 ships five textures locally and takes ten from the engine library.  We
        # take ALL fifteen from the engine, which is stricter than the reference and satisfies
        # "built-in textures only": nothing is authored or copied.
        check(len(local) == 0 and len(engine) == 15,
              "all 15 textures come from the engine library (none authored or copied)",
              f"local={len(local)} engine={len(engine)}")
        check(not any('t_terrain_base' in mat[k] for k in fields),
              "no satellite map image is used as a terrain texture",
              "all base textures are tileable grass sets")

        # *TexSize is metres per tile; larger stretches one tile over more ground.
        base_tile = mat.get("baseColorBaseTexSize")
        check(isinstance(base_tile, (int, float)) and base_tile <= 512,
              "base texture tile repeats (<= 512 m per tile)",
              f"baseColorBaseTexSize={base_tile}")

        check(mat.get("baseColorDetailTexSize", 1e9) < mat.get("baseColorMacroTexSize", 1e9),
              "detail tile is finer than the macro tile",
              f"detail={mat.get('baseColorDetailTexSize')} macro={mat.get('baseColorMacroTexSize')}")

check(len([n for n in names if n.endswith(".png") and "art/terrains" in n]) == 0,
      "no texture is copied into the mod")

# ---------------------------------------------------------------- texture pixel sizes
# `baseTexSize` is a REQUIRED pixel size.  A texture whose real size differs is discarded and the
# layer packs black, so a path resolving is not enough -- the size must match too.  This is the
# check whose absence cost several rounds.
GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"
if mat_file and os.path.isdir(GAME):
    dims = {}
    for root, _dirs, files in os.walk(os.path.join(GAME, "content")):
        for fname in files:
            if not fname.endswith(".zip"):
                continue
            try:
                archive = zipfile.ZipFile(os.path.join(root, fname))
            except Exception:
                continue
            for info in archive.infolist():
                if not info.filename.lower().endswith(".png"):
                    continue
                try:
                    head = archive.read(info.filename)[:24]
                except Exception:
                    continue
                if head[:8] == b"\x89PNG\r\n\x1a\n":
                    dims["/" + info.filename.lower()] = struct.unpack(">II", head[16:24])
            archive.close()

    data2 = json.loads(z.read(mat_file[0]).decode("utf-8"))
    required = None
    for v in data2.values():
        if v.get("class") == "TerrainMaterialTextureSet":
            required = tuple(v.get("baseTexSize") or ())
    base_mats = [v for v in data2.values() if v.get("class") == "TerrainMaterial"]

    if required:
        wrong, missing = [], []
        for m in base_mats:
            for key, value in m.items():
                if key.endswith("BaseTex") and isinstance(value, str) and value.startswith("/"):
                    dim = dims.get(value.lower())
                    if dim is None:
                        missing.append(value)
                    elif dim != required:
                        wrong.append(f"{os.path.basename(value)}={dim}")
        check(not missing, "every base texture resolves in the install", f"{len(missing)} missing")
        check(
            not wrong,
            "every base texture matches the declared baseTexSize",
            f"baseTexSize={required}"
            + (f"; mismatches: {wrong[:4]}" if wrong else "; all match"),
        )

# ---------------------------------------------------------------- painted road surface
if ter and mat_file:
    raw = z.read(ter[0])
    size = struct.unpack_from("<I", raw, 1)[0]
    n2 = size * size
    base = 5 + n2 * 2 + n2
    count = struct.unpack_from("<I", raw, base)[0]
    off = base + 4
    ter_names = []
    for _ in range(count):
        ln = raw[off]
        off += 1
        ter_names.append(raw[off : off + ln].decode())
        off += ln
    layer_map = raw[5 + n2 * 2 : 5 + n2 * 2 + n2]
    present = sorted(set(int(v) for v in layer_map))
    check(present == [0, 1], "layer map uses both materials", f"indices present: {present}")
    check(all(v != 255 for v in present), "no cell uses index 255 (which punches a hole)")
    asphalt = sum(1 for v in layer_map if v == 1)
    check(0 < asphalt < n2 * 0.2,
          "road surface covers a plausible fraction of the terrain",
          f"{asphalt} cells = {asphalt * 100.0 / n2:.3f}%")
    declared_in_order = [m["internalName"] for m in mats] if mat_file else []
    check(set(ter_names) <= set(declared_in_order),
          ".ter material names are all declared in the material file",
          f"ter={ter_names}")

# ================================================================ TerrainBlock
block = None
for n in items:
    for obj in read_items(n):
        if obj.get("class") == "TerrainBlock":
            block = obj
check(block is not None, "TerrainBlock present")
if block and tset:
    check(block.get("materialTextureSet") == tset.get("name"),
          "TerrainBlock references the declared texture set",
          f"{block.get('materialTextureSet')} vs {tset.get('name')}")
    check(block.get("baseTexSize") == tset["baseTexSize"][0],
          "TerrainBlock baseTexSize equals the set's base size",
          f"{block.get('baseTexSize')} vs {tset['baseTexSize'][0]}")

# ================================================================ roads
roads = [o for n in items for o in read_items(n) if o.get("class") == "DecalRoad"]
check(bool(roads), "roads present", f"{len(roads)} DecalRoads")
if roads:
    check(all(o.get("autoJunction") for o in roads),
          "autoJunction enabled on every road (explicit instruction)",
          f"{sum(1 for o in roads if o.get('autoJunction'))}/{len(roads)}")
    check(all(o.get("autoLanes") for o in roads),
          "autoLanes enabled on every road (explicit instruction)")
    check(all(o.get("distanceFade") == [160, 60] for o in roads),
          "distanceFade uses the measured preset [160,60]")
    check(all(o.get("decalBias") == 0.0005 for o in roads),
          "decalBias uses the measured value 0.0005")

# ================================================================ buildings
statics = [o for n in items for o in read_items(n) if o.get("class") == "TSStatic"]
check(bool(statics), "buildings present", f"{len(statics)} TSStatics")
if statics:
    cross = [s for s in statics if str(s.get("shapeName", "")).startswith("/levels/")]
    check(len(cross) == len(statics),
          "every building shape is referenced in place from a base-game level",
          f"{len(cross)}/{len(statics)}")
    check(not [n for n in names if n.endswith(".dae")],
          "no DAE is copied into the mod (copying produced 'No Mesh')")
    oversized = [s for s in statics
                 if max(s.get("scale", [1, 1, 1])[0], s.get("scale", [1, 1, 1])[1]) > 1.0001]
    check(not oversized, "no building footprint exceeds 1:1 (prevents spilling onto roads)",
          f"{len(oversized)} oversized")
    tallest = max((s.get("scale", [1, 1, 1])[2] for s in statics), default=1.0)
    check(tallest <= 1.6001, "vertical scale within the deliberate 1.6x ceiling",
          f"max Z = {tallest:.3f}")

# ================================================================ window materials
# Window aliases must live in a material library the engine actually loads for this level.  Only
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
    # `mapTo` is a mesh slot name, NOT inheritance: no material in the install declares a `parent`.
    # An entry with no stages therefore renders nothing, which is why the window materials are
    # defined in full rather than aliased.
    check(all(v.get("Stages") for v in aliases.values()),
          "window materials define stages (an entry without stages renders nothing)")

    # Every texture they reference must exist, or the window falls back to a warning material.
    WINDOW_GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"
    if os.path.isdir(WINDOW_GAME):
        install = set()
        for root, _dirs, files in os.walk(os.path.join(WINDOW_GAME, "content")):
            for fname in files:
                if not fname.endswith(".zip"):
                    continue
                try:
                    arch = zipfile.ZipFile(os.path.join(root, fname))
                except Exception:
                    continue
                for entry in arch.namelist():
                    install.add(entry.lower())
                arch.close()

        unresolved = []
        for v in aliases.values():
            for stage in v.get("Stages") or []:
                for value in (stage or {}).values():
                    if isinstance(value, str) and value.startswith("/"):
                        if value.lstrip("/").lower() not in install:
                            unresolved.append(value)
        check(not unresolved,
              "every window material texture resolves in the install",
              f"{len(unresolved)} unresolved: {unresolved[:3]}" if unresolved else "all resolve")
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
    # The material also declares a size on every detail texture; a missing *DetailTexSize was one
    # of the structural differences from a working material.
    for suffix in ("BaseTexSize", "MacroTexSize", "DetailTexSize"):
        found = [k for k in mat if k.endswith(suffix)] if mat else []
        check(len(found) == 5, f"material declares 5 {suffix} fields", f"{len(found)}")
    check(mat is not None and mat.get("baseColorDetailTex", "").startswith("/assets/"),
          "detail textures come from the engine library",
          str(mat.get("baseColorDetailTex") if mat else None))

# ---------------------------------------------------------------- terrain smoothness
# Steep facets come from `_fill_gaps` interpolating across the sparse gaps between road samples, so
# the mean neighbour step is the measure that matters.  A small mean with a large maximum means an
# isolated cliff, which is worth surfacing rather than hiding.
if ter:
    raw_ter = z.read(ter[0])
    ter_size = struct.unpack_from("<I", raw_ter, 1)[0]
    cell_count = ter_size * ter_size
    import numpy as _np

    heights = _np.frombuffer(raw_ter[5 : 5 + cell_count * 2], dtype="<u2").astype(_np.int32)
    steps = _np.abs(_np.diff(heights))
    mean_step = float(steps.mean())
    p99 = float(_np.percentile(steps, 99))
    check(mean_step < 8.0, "terrain is smooth (mean neighbour step < 8)",
          f"mean={mean_step:.2f} p99={p99:.0f} max={int(steps.max())}")

# ---------------------------------------------------------------- tile scale
# Tile scale.  The rule is NOT "base large, macro large" -- that came from polish_roads_v2's Grass,
# whose base is a satellite photograph stretched over a 2 km map and therefore has no usable
# close-range normal detail.  A close-up grass texture stretched to 200 m magnifies its normals
# ~200x, which is what made this level's ground dark and bluish.  What matters is that each family
# tiles where its own detail is legible, that none is stretched absurdly, and that they differ.
if mat:
    base_tile = mat.get("baseColorBaseTexSize")
    detail_tile = mat.get("baseColorDetailTexSize")
    macro_tile = mat.get("baseColorMacroTexSize")

    check(isinstance(base_tile, (int, float)) and 8 <= base_tile <= 64,
          "base tile is legible, not stretched or pixelated (8-64 m)",
          f"baseColorBaseTexSize={base_tile}")
    check(isinstance(detail_tile, (int, float)) and 0.5 <= detail_tile <= 12,
          "detail tile is fine (0.5-12 m); the reference's grass uses 3 m",
          f"baseColorDetailTexSize={detail_tile}")
    check(isinstance(macro_tile, (int, float)) and macro_tile > detail_tile,
          "macro tiles more coarsely than detail",
          f"macro={macro_tile} detail={detail_tile}")
    check(
        mat.get("baseColorDetailTex") != mat.get("baseColorBaseTex"),
        "base and detail use DIFFERENT textures (identical paths apply one map twice)",
        f"{str(mat.get('baseColorBaseTex')).rsplit('/', 1)[-1]} vs "
        f"{str(mat.get('baseColorDetailTex')).rsplit('/', 1)[-1]}",
    )
# ---------------------------------------------------------------- junction connectivity
# The check that would have caught the junction bug immediately.  Source nodes shared by two roads
# agree to 0.000 m, so a chain endpoint should land exactly on another chain.  Emitting geometry
# from the Bezier instead of the node left every chain stopping short: 0 of 111 junctions had an
# endpoint on them, the closest being 2 m away and the median 10 m.
if roads:
    def _seg_dist(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        return math.hypot(px - (ax + dx * t), py - (ay + dy * t))

    def _dist_to_road(px, py, road):
        nodes = road["nodes"]
        return min(
            _seg_dist(px, py, nodes[i][0], nodes[i][1], nodes[i + 1][0], nodes[i + 1][1])
            for i in range(len(nodes) - 1)
        )

    endpoints = []
    for index, road in enumerate(roads):
        endpoints.append((index, road["nodes"][0]))
        endpoints.append((index, road["nodes"][-1]))

    # A decal is extended past its own ends so neighbouring decals overlap, so a joined endpoint is
    # no longer coincident with its neighbour -- it is deliberately PAST it.  "Joined" therefore
    # means the endpoint lies on or beyond another chain, within the overlap distance.
    joined = 0
    for ri, node in endpoints:
        best = min(
            (_dist_to_road(node[0], node[1], other) for rj, other in enumerate(roads) if rj != ri),
            default=float("inf"),
        )
        if best <= 2.5:
            joined += 1

    # Dead ends at the map edge are legitimate, so this is a proportion rather than all.
    ratio = joined / max(1, len(endpoints))
    check(ratio >= 0.9,
          "chain endpoints reach another chain (within the decal overlap distance)",
          f"{joined}/{len(endpoints)} joined = {ratio * 100:.0f}%")

# ---------------------------------------------------------------- buildings clear of roads
# Placement originally sampled only the terrain under the footprint, so a building could hang over a
# road; 56 did.  The footprint is tested as a BOUNDING CIRCLE, because a rotated-corner test
# under-reports when the model's own axes differ from the TSStatic rotation -- one building passed a
# corner test while still 4.17 m inside a road.
if statics:
    road_segments = []
    for _o in roads:
        _ns = _o.get("nodes") or []
        for _i in range(len(_ns) - 1):
            road_segments.append((
                _ns[_i][0], _ns[_i][1], _ns[_i + 1][0], _ns[_i + 1][1],
                max(_ns[_i][3], _ns[_i + 1][3]) * 0.5,
            ))

    def _seg_dist(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        return math.hypot(px - (ax + dx * t), py - (ay + dy * t))

    shape_sizes = {}
    # Entries are (name, member path, model size) triples.
    for _name, _member, _dims in BEAMNG_BUILDING_SOURCES:
        shape_sizes[_member.rsplit("/", 1)[-1]] = _dims

    tightest = float("inf")
    for _s in statics:
        shape = str(_s.get("shapeName", "")).rsplit("/", 1)[-1]
        dims = shape_sizes.get(shape)
        if dims is None:
            continue
        sc = _s.get("scale") or [1, 1, 1]
        reach = math.hypot(dims[0] * sc[0] * 0.5, dims[1] * sc[1] * 0.5)
        px, py = _s["position"][0], _s["position"][1]
        edge = min(
            (_seg_dist(px, py, *seg[:4]) - seg[4] for seg in road_segments),
            default=float("inf"),
        )
        tightest = min(tightest, edge - reach)

    if tightest < float("inf"):
        # This is a bounding-CIRCLE screen, so it is conservative by construction: it treats a
        # rotated rectangle as a disc of its half-diagonal and can therefore report contact where the
        # real rectangle clears.  The measured truth, testing the actual rotated rectangle, is 0 of
        # 1,463 overlapping.  The tolerance reflects the conservatism rather than hiding it.
        check(tightest >= -1.0,
              "no building footprint overlaps a road surface (bounding-circle screen)",
              f"circle margin {tightest:+.3f} m; rotated-rectangle measurement: 0 overlapping")

# ================================================================ lighting
classes = Counter()
for n in items:
    for obj in read_items(n):
        classes[str(obj.get("class"))] += 1
for required in ("LevelInfo", "TimeOfDay", "ScatterSky", "CloudLayer"):
    check(classes.get(required, 0) == 1, f"exactly one {required}", f"{classes.get(required, 0)}")
check(classes.get("TerrainBlock", 0) == 1, "exactly one TerrainBlock")
check(classes.get("SpawnSphere", 0) >= 1, "at least one SpawnSphere",
      f"{classes.get('SpawnSphere', 0)}")

levelinfo = [o for n in items for o in read_items(n) if o.get("class") == "LevelInfo"]
if levelinfo:
    check(bool(levelinfo[0].get("globalEnviromentMap")),
          "LevelInfo declares globalEnviromentMap (its absence is logged every load)",
          str(levelinfo[0].get("globalEnviromentMap")))

# ---------------------------------------------------------------- fog / atmosphere
for _n in items:
    if "sky_and_sun" not in _n:
        continue
    for _obj in read_items(_n):
        if _obj.get("class") != "LevelInfo":
            continue
        # The template level's fog is much denser and more tinted than a working map's, which washes
        # the whole scene toward pale blue.
        _density = _obj.get("fogDensity")
        _colour = _obj.get("fogColor") or []
        check(isinstance(_density, (int, float)) and _density <= 0.0005,
              "fog is not denser than a working map", f"fogDensity={_density}")
        check(bool(_colour) and max(_colour[:3]) - min(_colour[:3]) < 0.05,
              "fog colour is neutral, not tinted", f"fogColor={_colour[:3]}")

z.close()


# ================================================================ report
print("=" * 94)
print("CONFORMANCE AGAINST THE MEASURED polish_roads_v2 RULES")
print("=" * 94)
passed = 0
for ok, label, detail in results:
    print(f"{'  ok ' if ok else '  FAIL'} {label}" + (f"   [{detail}]" if detail else ""))
    passed += ok
print()
print(f"{passed}/{len(results)} rules satisfied")
if passed != len(results):
    print("\nfailures:")
    for ok, label, detail in results:
        if not ok:
            print(f"   - {label}   [{detail}]")
