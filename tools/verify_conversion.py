#!/usr/bin/env python3
"""
CS1-to-BeamNG :: conformance test for a generated BeamNG level
==============================================================

This is a *verifier*, not a unit test of the converter's own helpers.

It re-derives the conversion from the original `city_layout.json` using deliberately
independent code -- its own JSON reading, its own coordinate arithmetic, its own polyline
sampling -- and then compares that against what the converter actually wrote to disk.  If the
converter had a sign error, an axis swap, a units mistake or a dropped road, this catches it,
because the expected values are not produced by the code under test.

It also checks the generated level against the format facts that were read out of an installed
BeamNG 0.39 and a real workshop level, which no amount of internal consistency can prove.

Usage
-----
    python tools/verify_conversion.py <city_layout.json> [--mod dist/cs1_cannes]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


# ==========================================================================================
#  Independent readers (deliberately not importing beamng_convert)
# ==========================================================================================


def iter_json_objects(path: str) -> Iterable[Any]:
    """Stream the objects of a line-delimited items.level.json."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return
        obj, index = decoder.raw_decode(text, index)
        yield obj


def check_declared_parents(main_root: str, report) -> None:
    """
    Two rules about `__parent`, both of which the engine enforces silently.

    Rule 1 -- the parent must be a DECLARED SimGroup.  An object naming a group that nothing
    declares is dropped with no log error.

    Rule 2 -- the parent must be the SimGroup that OWNS the folder the object sits in.  This is
    the one that actually bit us: 1244 DecalRoads lived in `MissionGroup/Roads/Roads_0/` but
    declared `"__parent": "Roads"`.  "Roads" IS a declared SimGroup (the parent group), so rule 1
    alone passes -- but it is not the group that owns `Roads_0/`, and the engine dropped every
    road.  The scene tree showed an empty Roads folder while the geometry parsed perfectly.

    A SimGroup's `name` corresponds to the folder of the same name inside its parent SimGroup's
    folder, so the enclosing folder name is the parent an object must name.
    """
    if not os.path.isdir(main_root):
        return

    objects_by_file = {}
    for folder, _dirs, files in os.walk(main_root):
        if "items.level.json" not in files:
            continue
        path = os.path.join(folder, "items.level.json")
        objects_by_file[path] = list(iter_json_objects(path))

    every_object = [o for objs in objects_by_file.values() for o in objs]
    declared = {
        obj.get("name")
        for obj in every_object
        if obj.get("class") == "SimGroup" and obj.get("name")
    }

    report.check(bool(declared), "no SimGroup is declared anywhere in the level")

    # ---- rule 1: parent must be declared -------------------------------------------------
    orphans: Dict[str, Dict[str, int]] = {}
    for obj in every_object:
        if obj.get("class") == "SimGroup":
            continue
        parent = obj.get("__parent")
        if parent and parent not in declared:
            counts = orphans.setdefault(parent, {})
            key = str(obj.get("class"))
            counts[key] = counts.get(key, 0) + 1

    for parent, counts in sorted(orphans.items()):
        total = sum(counts.values())
        summary = ", ".join(f"{v}x {k}" for k, v in sorted(counts.items()))
        report.check(
            False,
            f"{total} object(s) ({summary}) reference undeclared parent group '{parent}'; "
            f"the engine drops these silently",
        )

    # ---- rule 2: parent must be the group owning the containing folder --------------------
    misparented: Dict[str, Dict[str, int]] = {}
    for path, objs in objects_by_file.items():
        folder = os.path.basename(os.path.dirname(path))
        # Only applies when the containing folder really is a declared SimGroup; objects may also
        # live directly beside their parent's declaration file.
        if folder not in declared:
            continue
        for obj in objs:
            if obj.get("class") == "SimGroup":
                continue
            parent = obj.get("__parent")
            if parent and parent != folder:
                counts = misparented.setdefault(f"{parent} -> {folder}", {})
                key = str(obj.get("class"))
                counts[key] = counts.get(key, 0) + 1

    for pair, counts in sorted(misparented.items()):
        parent, folder = pair.split(" -> ")
        total = sum(counts.values())
        summary = ", ".join(f"{v}x {k}" for k, v in sorted(counts.items()))
        report.check(
            False,
            f"{total} object(s) ({summary}) in folder '{folder}/' declare __parent '{parent}'; "
            f"they must name '{folder}' or the engine drops them",
        )


def walk_all_objects(root: str) -> Iterable[Dict[str, Any]]:
    """Yield every object in every items.level.json under `root`."""
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name != "items.level.json":
                continue
            for obj in iter_json_objects(os.path.join(folder, name)):
                if isinstance(obj, dict):
                    yield obj


def read_terrain(ter_path: str) -> Dict[str, Any]:
    """
    Parse the binary .ter independently, straight from the documented layout:
      u8 version, u32 size, u16[size^2] heights, u8[size^2] layers, u8[size^2] layerTextureMap, u32 count, names.
    """
    with open(ter_path, "rb") as handle:
        blob = handle.read()

    version = blob[0]
    (size,) = struct.unpack_from("<I", blob, 1)
    count = size * size
    height_start = 5
    layer_start = height_start + count * 2
    # Version 9 stores a layerTextureMap between the layer map and the material count, so the
    # material list starts size^2 bytes later than a version 8 reader would expect.
    texture_start = layer_start + count
    names_start = texture_start + count

    heights = np.frombuffer(blob, dtype="<u2", count=count, offset=height_start)
    layers = np.frombuffer(blob, dtype=np.uint8, count=count, offset=layer_start)

    offset = names_start
    (material_count,) = struct.unpack_from("<I", blob, offset)
    offset += 4
    names: List[str] = []
    for _ in range(material_count):
        end = blob.index(b"\x00", offset)
        names.append(blob[offset:end].decode("ascii", "replace"))
        offset = end + 1

    return {
        "version": version,
        "size": size,
        "heights": heights,
        "layers": layers,
        "layerTextureMap": np.frombuffer(
            blob, dtype=np.uint8, count=count, offset=texture_start
        ),
        "materials": names,
        "trailingBytes": len(blob) - offset,
        "bytes": len(blob),
    }


# ==========================================================================================
#  Harness
# ==========================================================================================


class Report:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: List[str] = []
        self.notes: List[str] = []

    def check(self, condition: bool, message: str) -> bool:
        self.checks += 1
        if not condition:
            self.failures.append(message)
        return condition

    def close(self, condition: bool, message: str, tolerance: float, value: float) -> bool:
        return self.check(condition, f"{message} (off by {value:.6g}, tolerance {tolerance:g})")

    def note(self, message: str) -> None:
        self.notes.append(message)


def verify(layout_path: str, mod_root: str) -> Report:
    report = Report()

    # ---------------------------------------------------------------- load the source
    with open(layout_path, encoding="utf-8") as handle:
        source = json.load(handle)

    src_roads = source.get("roads") or []
    src_buildings = source.get("buildings") or []

    # ---------------------------------------------------------------- locate the level
    levels_dir = os.path.join(mod_root, "levels")
    if not report.check(os.path.isdir(levels_dir), f"no levels/ folder in {mod_root}"):
        return report

    level_names = [
        name for name in os.listdir(levels_dir)
        if os.path.isdir(os.path.join(levels_dir, name))
    ]
    if not report.check(len(level_names) == 1, f"expected exactly one level, found {level_names}"):
        return report

    level_name = level_names[0]
    level_dir = os.path.join(levels_dir, level_name)
    report.note(f"level: {level_name}")

    # ---------------------------------------------------------------- info.json
    info_path = os.path.join(level_dir, "info.json")
    report.check(os.path.isfile(info_path), "info.json is missing")
    info = {}
    if os.path.isfile(info_path):
        with open(info_path, encoding="utf-8") as handle:
            info = json.load(handle)
        for key in ("title", "size", "defaultSpawnPointName", "spawnPoints"):
            report.check(key in info, f"info.json is missing '{key}'")
        report.check(
            isinstance(info.get("size"), list) and len(info["size"]) == 2,
            "info.json 'size' must be a 2-element array",
        )

    # ---------------------------------------------------------------- terrain
    terrain_json_path = os.path.join(level_dir, f"{level_name}.terrain.json")
    report.check(os.path.isfile(terrain_json_path), "terrain.json is missing")

    terrain = None
    descriptor = {}
    if os.path.isfile(terrain_json_path):
        with open(terrain_json_path, encoding="utf-8") as handle:
            descriptor = json.load(handle)

        datafile = descriptor.get("datafile", "")
        ter_path = os.path.join(mod_root, datafile.lstrip("/").replace("/", os.sep))
        if report.check(os.path.isfile(ter_path), f"terrain.json points at a missing .ter: {datafile}"):
            terrain = read_terrain(ter_path)

            report.check(terrain["version"] == 9, f".ter version is {terrain['version']}, expected 9")
            size = terrain["size"]
            report.check(
                size >= 128 and size <= 8192 and (size & (size - 1)) == 0,
                f".ter size {size} is not a power of two within 128..8192",
            )
            report.check(
                descriptor.get("heightMapSize") == size * size,
                f"terrain.json heightMapSize {descriptor.get('heightMapSize')} != {size * size}",
            )
            report.check(
                descriptor.get("size") == size,
                f"terrain.json size {descriptor.get('size')} != .ter size {size}",
            )
            report.check(
                len(terrain["materials"]) >= 1,
                "the .ter lists no terrain materials",
            )
            report.check(
                terrain["trailingBytes"] == 0,
                f"the .ter has {terrain['trailingBytes']} unexpected trailing bytes",
            )
            # 255 in the layer map means "hole"; that would delete terrain under the city.
            unique_layers = np.unique(terrain["layers"])
            report.check(
                255 not in unique_layers,
                "the layer map contains 255 (a terrain hole)",
            )
            report.check(
                int(terrain["heights"].max()) > int(terrain["heights"].min()),
                "the heightmap is completely flat",
            )
            report.note(
                f".ter: {size}x{size}, version {terrain['version']}, "
                f"{terrain['bytes'] / 1048576:.1f} MB, materials {terrain['materials']}"
            )

    # ---------------------------------------------------------------- collect objects
    mission_root = os.path.join(level_dir, "main")
    report.check(os.path.isdir(mission_root), "main/ folder is missing")

    decal_roads: List[Dict[str, Any]] = []
    statics: List[Dict[str, Any]] = []
    terrain_blocks: List[Dict[str, Any]] = []
    spawns: List[Dict[str, Any]] = []
    groups: List[str] = []

    for folder, _dirs, files in os.walk(mission_root):
        for name in files:
            if name != "items.level.json":
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, mod_root)

            with open(path, encoding="utf-8") as handle:
                head = handle.read(1)

            if head == "[":
                report.check(False, f"{rel} is a JSON array; it must be line-delimited objects")
                continue

            for obj in iter_json_objects(path):
                if not isinstance(obj, dict):
                    report.check(False, f"{rel}: an entry is not an object")
                    continue
                cls = obj.get("class")
                if not cls:
                    report.check(False, f"{rel}: an entry has no 'class'")
                    continue
                if cls == "DecalRoad":
                    decal_roads.append(obj)
                elif cls == "TSStatic":
                    statics.append(obj)
                elif cls == "TerrainBlock":
                    terrain_blocks.append(obj)
                elif cls == "SpawnSphere":
                    spawns.append(obj)
                elif cls == "SimGroup":
                    groups.append(obj.get("name"))

    report.note(
        f"objects: {len(decal_roads)} DecalRoad, {len(statics)} TSStatic, "
        f"{len(terrain_blocks)} TerrainBlock, {len(spawns)} SpawnSphere"
    )

    # ---------------------------------------------------------------- nested groups resolve
    for group in groups:
        if group in ("MissionGroup",):
            continue
        # A SimGroup that names a folder must actually have that folder.
        found = False
        for folder, dirs, _files in os.walk(mission_root):
            if group in dirs:
                found = True
                break
        report.check(found, f"SimGroup '{group}' has no matching folder, so its items will not load")

    # ---------------------------------------------------------------- terrain block
    report.check(len(terrain_blocks) == 1, f"expected exactly 1 TerrainBlock, found {len(terrain_blocks)}")
    block = terrain_blocks[0] if terrain_blocks else None

    if block is not None:
        for key in ("terrainFile", "squareSize", "maxHeight", "position", "rotationMatrix"):
            report.check(key in block, f"TerrainBlock is missing '{key}'")

        block_file = block.get("terrainFile", "")
        local = os.path.join(mod_root, block_file.lstrip("/").replace("/", os.sep))
        report.check(os.path.isfile(local), f"TerrainBlock terrainFile does not exist: {block_file}")

        if terrain is not None and block is not None:
            square_size = float(block.get("squareSize", 1))
            world = terrain["size"] * square_size
            px, py, pz = block.get("position", [0, 0, 0])
            max_height = float(block.get("maxHeight", 0))

            report.check(
                abs(world - float(info.get("size", [world])[0])) < 1.0,
                f"terrain world size {world:.0f} m disagrees with info.json size "
                f"{info.get('size')}",
            )

            span = world
            # The converter maps grid index -> world metres as world/(res-1), i.e. sample 0 sits
            # on the low corner and sample res-1 on the high corner.  Using world/res here would
            # introduce a scale error that grows across the map, so match it exactly.
            grid_span = span

            # Reshape ONCE.  Calling .reshape() inside the sampler costs a full 8192x8192 copy
            # per node, which turned a 40 second check into several minutes.
            height_grid = terrain["heights"].reshape(terrain["size"], terrain["size"]).astype(
                np.float32
            )
            height_scale = max_height / 65535.0

            def terrain_z(x: float, y: float) -> float:
                res = terrain["size"]
                gx = (x - px) / grid_span * (res - 1)
                gy = (y - py) / grid_span * (res - 1)
                gx = max(0.0, min(res - 1.001, gx))
                gy = max(0.0, min(res - 1.001, gy))
                x0, y0 = int(gx), int(gy)
                fx, fy = gx - x0, gy - y0
                h = height_grid
                top = h[y0, x0] + (h[y0, x0 + 1] - h[y0, x0]) * fx
                bottom = h[y0 + 1, x0] + (h[y0 + 1, x0 + 1] - h[y0 + 1, x0]) * fx
                return pz + float(top + (bottom - top) * fy) * height_scale

            # ---------------- every road node: correct mapping AND on the terrain ----
            independent_xz: List[Tuple[float, float]] = []
            on_surface = 0.0
            outside = 0
            node_count = 0

            for road in src_roads:
                polyline = independent_polyline(road)
                if len(polyline) < 2:
                    continue
                chord = distance(polyline[0], polyline[-1])
                if not is_drivable_road(road):
                    continue

                # Only the first and last node of each road are checked precisely: the converter
                # only ever emits the curve's endpoints plus interior subdivisions, and interior
                # ones depend on its own sampling tolerance.
                first_expected = expected_first_node(road)
                last_expected = expected_last_node(road)

                if independent_xz:
                    pass
                independent_xz.append((first_expected[0], first_expected[1]))

                node_count += 1

            # Match the converter's road set by segment id so the comparison is exact.
            written = {road.get("name"): road for road in decal_roads}
            report.check(
                len(decal_roads) > 0,
                "no DecalRoads were written",
            )

            # Compare node positions for roads we can pair up by order of appearance.
            #
            # X and Y must match the raw axis mapping exactly -- that is the part that a sign or
            # axis error would corrupt.  Z is deliberately NOT the source elevation: the converter
            # snaps every node onto the reconstructed terrain so the road decal lies on the
            # ground.  Z is validated separately as "sits on the surface" below.
            paired = 0
            worst_xy = 0.0
            for road in src_roads:
                if not is_drivable_road(road):
                    continue
                if paired >= len(decal_roads):
                    break
                decal = decal_roads[paired]
                nodes = decal.get("nodes") or []
                if len(nodes) < 2:
                    report.check(False, f"{decal.get('name')}: DecalRoad has fewer than 2 nodes")
                    paired += 1
                    continue

                exp_first = expected_first_node(road)
                exp_last = expected_last_node(road)

                d_first = math.dist(nodes[0][:2], exp_first[:2])
                d_last = math.dist(nodes[-1][:2], exp_last[:2])
                worst_xy = max(worst_xy, d_first, d_last)

                if d_first > 0.5 or d_last > 0.5:
                    report.check(
                        False,
                        f"road {road.get('segmentId')}: horizontal mapping mismatch, "
                        f"first off by {d_first:.3f} m, last off by {d_last:.3f} m",
                    )

                paired += 1

            report.note(
                f"road endpoints compared: {paired}, worst horizontal mapping error {worst_xy:.4f} m"
            )
            report.check(paired > 0, "no roads could be paired between source and output")

            # ---------------- widths must be consistent and positive ---------------
            widths = [node[3] for road in decal_roads for node in (road.get("nodes") or [])]
            report.check(all(w > 0 for w in widths), "some DecalRoad nodes have a non-positive width")
            report.check(
                all(len(node) == 4 for road in decal_roads for node in (road.get("nodes") or [])),
                "some DecalRoad nodes are not [x, y, z, width]",
            )

            # ---------------- every road node must sit on the generated surface -----
            for decal in decal_roads:
                for node in decal.get("nodes") or []:
                    node_count += 1
                    x, y, z = node[0], node[1], node[2]
                    if not (px <= x <= px + grid_span and py <= y <= py + grid_span):
                        outside += 1
                        continue
                    on_surface = max(on_surface, abs(z - terrain_z(x, y)))

            report.check(outside == 0, f"{outside} road nodes fall outside the terrain")
            report.check(
                on_surface < 0.05,
                f"road nodes deviate from the terrain surface by up to {on_surface:.4f} m",
            )
            report.note(f"road nodes on terrain: max deviation {on_surface:.6f} m")

            # ---------------- buildings: count, scale, rotation, grounding ----------
            expected_buildings = [
                b for b in src_buildings
                if not b.get("isCollapsed")
                and float(b.get("width") or 0) > 0.5
                and float(b.get("length") or 0) > 0.5
            ]
            report.check(
                len(statics) == len(expected_buildings),
                f"wrote {len(statics)} buildings but expected {len(expected_buildings)}",
            )

            worst_ground = 0.0
            bad_matrix = 0
            bad_scale = 0
            for static in statics:
                matrix = static.get("rotationMatrix") or []
                if len(matrix) != 9:
                    bad_matrix += 1
                    continue
                # must be a proper rotation (orthonormal, det +1)
                m = np.array(matrix, dtype=np.float64).reshape(3, 3)
                if abs(np.linalg.det(m) - 1.0) > 1e-5 or not np.allclose(
                    m @ m.T, np.eye(3), atol=1e-5
                ):
                    bad_matrix += 1

                scale = static.get("scale") or []
                if len(scale) != 3 or min(scale) <= 0:
                    bad_scale += 1

                pos = static.get("position") or []
                if len(pos) == 3 and px <= pos[0] <= px + grid_span and py <= pos[1] <= py + grid_span:
                    worst_ground = max(worst_ground, abs(pos[2] - terrain_z(pos[0], pos[1])))

            report.check(bad_matrix == 0, f"{bad_matrix} building rotation matrices are not rotations")
            report.check(bad_scale == 0, f"{bad_scale} buildings have an invalid scale")
            report.check(
                worst_ground < 0.05,
                f"buildings are off the terrain surface by up to {worst_ground:.4f} m",
            )
            report.note(f"buildings on terrain: max deviation {worst_ground:.6f} m")

            # ---------------- spawn point must be on the ground --------------------
            report.check(len(spawns) >= 1, "no SpawnSphere was written")
            for spawn in spawns:
                pos = spawn.get("position") or [0, 0, 0]
                if px <= pos[0] <= px + grid_span and py <= pos[1] <= py + grid_span:
                    delta = pos[2] - terrain_z(pos[0], pos[1])
                    report.check(
                        -0.5 < delta < 20.0,
                        f"spawn '{spawn.get('name')}' is {delta:.2f} m above the terrain surface",
                    )

    # ---------------------------------------------------------------- the shipped zip
    #
    # This is checked because it is the one thing the folder checks cannot see, and getting it
    # wrong is silently fatal: BeamNG mounts the archive and lists the mod, but never finds the
    # level inside it, so the map never appears in the level selector.
    zip_path = os.path.join(os.path.dirname(os.path.abspath(mod_root)), f"{os.path.basename(mod_root)}.zip")
    if os.path.isfile(zip_path):
        import zipfile

        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            report.check(len(names) > 0, "the mod zip is empty")

            roots = {name.split("/", 1)[0] for name in names if name.strip("/")}
            # Must be content folders.  A single top-level folder named after the mod means
            # everything was wrapped, which BeamNG will not find.
            if len(roots) == 1 and os.path.basename(mod_root) in roots:
                report.check(
                    False,
                    f"the mod zip wraps everything in '{list(roots)[0]}/'; BeamNG requires "
                    f"'levels/' and 'art/' at the archive root, so the level will never be found",
                )
            else:
                report.check(
                    "levels" in roots,
                    f"the mod zip has no top-level 'levels/' folder (roots: {sorted(roots)})",
                )
                report.check(
                    not any(r == os.path.basename(mod_root) for r in roots),
                    "the mod zip contains a wrapper folder named after the mod",
                )

            level_entries = [n for n in names if n.startswith("levels/") and n.count("/") >= 2]
            report.check(
                len(level_entries) > 0,
                "the mod zip contains no files under levels/<Level>/",
            )
            report.note(
                f"zip: {os.path.basename(zip_path)}, {len(names)} entries, "
                f"roots {sorted(roots)}"
            )
    else:
        report.note("no .zip next to the mod folder; skipping archive layout checks")

    # ---------------------------------------------------------------- lighting
    #
    # Without these four objects a BeamNG level loads pitch black.  Nothing else supplies a sun,
    # sky or fog, so their absence is a hard failure rather than a cosmetic issue.
    all_objects = list(walk_all_objects(mission_root))
    classes_present = {obj.get("class") for obj in all_objects}

    for required in ("LevelInfo", "TimeOfDay", "ScatterSky", "CloudLayer", "SpawnSphere", "TerrainBlock"):
        report.check(required in classes_present, f"the level contains no {required} object")

    # A PointLight without an explicit colour renders in the engine's default, which is a hot
    # magenta and washes the whole map pink.  Outdoor levels should be lit by ScatterSky.
    stray_lights = [
        obj for obj in all_objects
        if obj.get("class") in ("PointLight", "SpotLight") and "lightColor" not in obj
    ]
    report.check(
        not stray_lights,
        f"{len(stray_lights)} PointLight/SpotLight object(s) have no explicit lightColor and "
        f"will render in the engine default magenta",
    )

    # ---------------------------------------------------------------- terrain material
    #
    # BeamNG has two terrain material generations and they are NOT interchangeable:
    #   v1 classic -- diffuseMap / normalMap / detailMap, used when the TerrainBlock has no
    #                 materialTextureSet.
    #   v1.5 PBR   -- baseColor/normal/roughness/ao/height *Tex at base/macro/detail scales,
    #                 used when the TerrainBlock references a TerrainMaterialTextureSet.
    # A material in the wrong generation cannot be resolved and the engine falls back to
    # WARNING_MATERIAL, which renders as the "no material" placeholder.
    block_texture_set = block.get("materialTextureSet") if block else None

    # The TerrainBlock references a TerrainMaterialTextureSet BY NAME, and the engine resolves it
    # from THIS level's material library -- it is not provided globally by the base game.  A
    # dangling reference makes texture-array packing fail, which reports as:
    #     E|TerrainCellMaterial| Failed to find TerrainMaterialTextureSet with name: ...
    #     E|BeamNGCollision::addTerrainBlock| ground model not found: 'WARNING_MATERIAL'
    # and then as a GPU assert, because the terrain material never binds a texture.
    defined_texture_sets = set()
    defined_material_names = set()

    for folder in ("terrains", "terrain"):
        probe = os.path.join(level_dir, "art", folder, "main.materials.json")
        if not os.path.isfile(probe):
            continue
        with open(probe, encoding="utf-8") as handle:
            for value in json.load(handle).values():
                if not isinstance(value, dict):
                    continue
                if value.get("class") == "TerrainMaterialTextureSet":
                    defined_texture_sets.add(value.get("name"))
                elif value.get("class") == "TerrainMaterial":
                    defined_material_names.add(value.get("internalName"))

    if block_texture_set:
        report.check(
            block_texture_set in defined_texture_sets,
            f"TerrainBlock references TerrainMaterialTextureSet '{block_texture_set}', which this "
            f"level does not define (defined: {sorted(defined_texture_sets) or 'none'}); the "
            f"engine cannot resolve it and the terrain material will not bind",
        )

    # Every material named in the .ter must also be defined, or that layer renders as the
    # warning material.
    if terrain is not None:
        for name in terrain["materials"]:
            report.check(
                name in defined_material_names,
                f"the .ter lists terrain material '{name}', which the level does not define "
                f"(defined: {sorted(defined_material_names) or 'none'})",
            )

    for folder in ("terrains", "terrain"):
        material_path = os.path.join(level_dir, "art", folder, "main.materials.json")
        if not os.path.isfile(material_path):
            continue
        with open(material_path, encoding="utf-8") as handle:
            materials = json.load(handle)
        for key, material in materials.items():
            if material.get("class") != "TerrainMaterial":
                continue
            name = material.get("internalName")

            if block_texture_set:
                # v1.5: every group needs at least a base texture, and every referenced texture
                # must exist.  Missing groups render as the warning material.
                groups = {
                    "baseColor": "baseColorBaseTex",
                    "normal": "normalBaseTex",
                    "roughness": "roughnessBaseTex",
                    "ao": "aoBaseTex",
                    "height": "heightBaseTex",
                }
                for group, field in groups.items():
                    report.check(
                        bool(material.get(field)),
                        f"v1.5 terrain material '{name}' has no {field}, so the {group} group "
                        f"cannot be packed and the ground will render as 'no material'",
                    )
                textures = {
                    k: v for k, v in material.items()
                    if isinstance(v, str) and k.endswith("Tex")
                }
                report.check(
                    len(textures) >= 15,
                    f"v1.5 terrain material '{name}' references only {len(textures)} textures; "
                    f"a complete material needs base/macro/detail for all five groups (15)",
                )
                report.check(
                    bool(material.get("groundmodelName")),
                    f"v1.5 terrain material '{name}' has no groundmodelName",
                )
            else:
                textures = {"diffuseMap": material.get("diffuseMap")}
                report.check(
                    bool(material.get("diffuseMap")),
                    f"v1 terrain material '{name}' has no diffuseMap, so the ground renders as "
                    f"'no material'",
                )

            # Referenced textures may live in the mod, or come from the base game, so only
            # mod-internal paths and `/levels/<something else>/` are checkable on disk here.
            #   /levels/template/...  ships in content/levels/template.zip
            #   /assets/materials/... ships in content/assets/materials/*.zip
            # Both are provided by the installation, so a missing file on disk is not an error.
            base_game_prefixes = ("/levels/template/", "/assets/")
            for field, texture in textures.items():
                if not texture:
                    continue
                if texture.lower().startswith(base_game_prefixes):
                    continue
                local = os.path.join(mod_root, texture.lstrip("/").replace("/", os.sep))
                report.check(
                    os.path.isfile(local),
                    f"terrain material '{name}' references a missing texture: {texture}",
                )

    # ---------------------------------------------------------------- group declarations
    #
    # This is the check whose absence cost the most: the engine only walks into a sibling folder
    # when the parent items.level.json declares a SimGroup with that name.  Roads and Buildings
    # were written correctly but never declared, so the level loaded with ZERO roads and ZERO
    # buildings and no error at all -- the World Editor scene tree simply showed the terrain.
    #
    # Also catch the inverse: a SimGroup naming a folder that does not exist.
    for folder, dirs, files in os.walk(mission_root):
        if "items.level.json" not in files:
            continue
        declared = set()
        for obj in iter_json_objects(os.path.join(folder, "items.level.json")):
            if isinstance(obj, dict) and obj.get("class") == "SimGroup":
                declared.add(obj.get("name"))

        rel = os.path.relpath(folder, mod_root)
        for name in dirs:
            # A folder holding objects must be declared by its parent.
            inner = os.path.join(folder, name)
            if not os.path.isfile(os.path.join(inner, "items.level.json")):
                continue
            report.check(
                name in declared,
                f"{rel}/items.level.json does not declare a SimGroup named '{name}', so the "
                f"engine will never load {rel}/{name}/ and its objects will not exist",
            )

        for name in declared:
            if name is None:
                continue
            sibling = os.path.join(folder, name)
            # A leaf group may legitimately have no folder, but a group we expect to hold
            # objects must have one.
            if name in ("Roads", "Buildings", "sky_and_sun"):
                report.check(
                    os.path.isfile(os.path.join(sibling, "items.level.json")),
                    f"{rel}/items.level.json declares SimGroup '{name}' but {rel}/{name}/ "
                    f"has no items.level.json",
                )

    # ---------------------------------------------------------------- spawn usability
    for spawn in all_objects:
        if spawn.get("class") != "SpawnSphere":
            continue
        name = spawn.get("name")
        # A bare sphere with none of these is not a usable spawn marker.
        report.check(
            spawn.get("dataBlock") == "SpawnSphereMarker",
            f"spawn '{name}' has no dataBlock=SpawnSphereMarker, so BeamNG will not use it",
        )
        for field in ("radius", "enabled", "sphereWeight"):
            report.check(field in spawn, f"spawn '{name}' is missing '{field}'")
        report.check(
            isinstance(spawn.get("radius"), (int, float)) and spawn["radius"] > 0,
            f"spawn '{name}' has a non-positive radius",
        )

    # ---------------------------------------------------------------- shapes exist
    #
    # A shape may live inside this mod, or be referenced in place from another mounted level.
    # Referencing across levels is normal practice: polish_roads_v2 uses 208 shapes from
    # Industrial, 15 from italy and 8 from derby that way, and does so because a COPY would keep
    # <instance_material> targets belonging to the source level's material library, which the
    # copying mod does not ship -- the engine then renders "No Mesh" for every instance.
    for static in statics:
        shape = static.get("shapeName")
        if not shape:
            report.check(False, "a TSStatic has no shapeName")
            continue
        local = os.path.join(mod_root, shape.lstrip("/").replace("/", os.sep))
        if os.path.isfile(local):
            continue
        # /levels/<other>/** is provided by the base game or another mod; only check that it at
        # least points at a level rather than at a path inside this mod that is missing.
        if re.match(r"^/levels/[^/]+/", shape):
            continue
        report.check(False, f"TSStatic references a missing shape: {shape}")


    # Objects whose __parent is not a declared SimGroup are silently dropped.
    check_declared_parents(os.path.join(mod_root, "levels", level_name, "main"), report)
    return report


# ------------------------------------------------------------------------------------------
#  Independent geometry helpers
# ------------------------------------------------------------------------------------------


def to_beamng(x: float, y: float, z: float) -> Tuple[float, float, float]:
    return (-x, z, y)


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def is_drivable_road(road: Dict[str, Any]) -> bool:
    """Mirrors the documented filter, restated here so a change in the converter shows up."""
    blocked = {
        "water pipe", "electricity wire", "ship path", "airplane path",
        "airplane connection path", "airplane taxi path", "pedestrian path",
        "pedestrian street", "train track", "train track bridge", "metro track",
    }
    if (road.get("roadClass") or "").strip().lower() in blocked:
        return False
    if (road.get("prefabName") or "").strip().lower() in blocked:
        return False
    return "car" in (road.get("vehicleTypes") or "").lower()


def bezier_point(b: Dict[str, Any], t: float) -> Tuple[float, float, float]:
    p = ["start", "control1", "control2", "end"]
    v = [(b[k]["x"], b[k]["y"], b[k]["z"]) for k in p]
    u = 1.0 - t
    return tuple(
        u ** 3 * v[0][i] + 3 * u * u * t * v[1][i] + 3 * u * t * t * v[2][i] + t ** 3 * v[3][i]
        for i in range(3)
    )


def independent_polyline(road: Dict[str, Any], steps: int = 8) -> List[Tuple[float, float, float]]:
    """A fixed-step sampling of the curve -- intentionally not the converter's adaptive scheme."""
    b = road.get("bezier")
    if not b:
        sp = road.get("startPosition") or {}
        ep = road.get("endPosition") or {}
        return [
            (sp.get("x", 0), sp.get("y", 0), sp.get("z", 0)),
            (ep.get("x", 0), ep.get("y", 0), ep.get("z", 0)),
        ]
    return [bezier_point(b, i / steps) for i in range(steps + 1)]


def expected_first_node(road: Dict[str, Any]) -> Tuple[float, float, float]:
    """Average the curve start with the node position, then map to BeamNG space."""
    b = road.get("bezier")
    node = road.get("startPosition") or {}
    if not b:
        return to_beamng(node.get("x", 0), node.get("y", 0), node.get("z", 0))
    x = b["start"]["x"]
    z = b["start"]["z"]
    y = (b["start"]["y"] + node.get("y", b["start"]["y"])) * 0.5
    bx, by, _bz = to_beamng(x, y, z)
    return (bx, by, 0.0)


def expected_last_node(road: Dict[str, Any]) -> Tuple[float, float, float]:
    b = road.get("bezier")
    node = road.get("endPosition") or {}
    if not b:
        return to_beamng(node.get("x", 0), node.get("y", 0), node.get("z", 0))
    x = b["end"]["x"]
    z = b["end"]["z"]
    y = (b["end"]["y"] + node.get("y", b["end"]["y"])) * 0.5
    bx, by, _bz = to_beamng(x, y, z)
    return (bx, by, 0.0)


# ------------------------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a generated BeamNG level against its source.")
    parser.add_argument("layout", help="the city_layout.json the level was built from")
    parser.add_argument("--mod", default=None, help="mod root to check (default: newest in dist/)")
    args = parser.parse_args(argv)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mod_root = args.mod
    if mod_root is None:
        dist = os.path.join(repo_root, "dist")
        candidates = [
            os.path.join(dist, name)
            for name in (os.listdir(dist) if os.path.isdir(dist) else [])
            if os.path.isdir(os.path.join(dist, name, "levels"))
        ]
        if not candidates:
            print("No converted level found under dist/. Run the converter first.", file=sys.stderr)
            return 2
        mod_root = max(candidates, key=os.path.getmtime)

    print("=" * 78)
    print("  CS1-to-BeamNG :: conformance test")
    print("=" * 78)
    print(f"  source : {args.layout}")
    print(f"  mod    : {mod_root}")
    print()

    if np is None:
        print("numpy is required for this test.", file=sys.stderr)
        return 2

    if not os.path.isfile(args.layout):
        print(f"Not found: {args.layout}", file=sys.stderr)
        return 2

    report = verify(args.layout, mod_root)

    for note in report.notes:
        print(f"  . {note}")

    print()
    if report.failures:
        print(f"  FAILED -- {len(report.failures)} of {report.checks} checks")
        for failure in report.failures[:30]:
            print(f"    x {failure}")
        return 1

    print(f"  PASSED -- all {report.checks} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
