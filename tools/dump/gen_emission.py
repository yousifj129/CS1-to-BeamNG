"""Emit the full replacement emission layer to build/new_emission.py."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
OUT = os.path.join(REPO, "build", "new_emission.py")

PART1 = r'''
# ==========================================================================================
#  Terrain material -- taken from an ENGINE level; no material authored, no texture copied
# ==========================================================================================
#
# There is no global terrain material library in BeamNG: a terrain material is always declared per
# level, in `levels/<level>/art/terrains/main.materials.json`.  Fifteen shipped levels provide one,
# and three of them -- east_coast_usa, west_coast_usa and Utah -- already use the arrangement that
# matters: five base textures inside the level and ten from the engine's own library.
#
# One such material is reproduced below.  Its five local texture references are rewritten to the
# same engine level they came from, so all fifteen slots resolve to built-in content:
#
#     base    /levels/east_coast_usa/art/terrains/...   (engine level, referenced in place)
#     detail  /assets/materials/terrain/...             (engine library)
#     macro   /assets/materials/terrain/...             (engine library)
#
# Cross-level texture references are proven to work: polish_roads_v2 references ten textures inside
# east_coast_usa and its ground renders.
# ==========================================================================================

CS1_TERRAIN_SOURCE_LEVEL = "east_coast_usa"

CS1_TERRAIN_MATERIAL = {
    "class": "TerrainMaterial",
    "internalName": "Dirt",
    "groundmodelName": "DIRT",
    "annotation": "DIRT",
    "macroDistances": [0, 10, 100, 3000],
    "detailDistances": [0, 0, 30, 60],
    "baseColorBaseTex": "/levels/east_coast_usa/art/terrains/t_terrain_base_b.png",
    "baseColorBaseTexSize": 2048,
    "normalBaseTex": "/levels/east_coast_usa/art/terrains/t_terrain_base_nm.png",
    "normalBaseTexSize": 2048,
    "roughnessBaseTex": "/levels/east_coast_usa/art/terrains/t_terrain_base_r.png",
    "roughnessBaseTexSize": 2048,
    "aoBaseTex": "/levels/east_coast_usa/art/terrains/t_terrain_base_ao.png",
    "aoBaseTexSize": 2048,
    "heightBaseTex": "/levels/east_coast_usa/art/terrains/t_terrain_base_h.png",
    "heightBaseTexSize": 2048,
    "baseColorDetailTex": "/assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_b.png",
    "baseColorDetailTexSize": 4,
    "baseColorDetailStrength": [0.5, 0.5],
    "normalDetailTex": "/assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_nm.png",
    "normalDetailTexSize": 4,
    "roughnessDetailTex": "/assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_r.png",
    "roughnessDetailTexSize": 4,
    "aoDetailTex": "/assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_ao.png",
    "aoDetailTexSize": 4,
    "heightDetailTex": "/assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_h.png",
    "heightDetailTexSize": 4,
    "baseColorMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_b.png",
    "baseColorMacroTexSize": 80,
    "baseColorMacroStrength": [0.5, 0.5],
    "normalMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_nm.png",
    "normalMacroTexSize": 80,
    "normalMacroStrength": [0.5, 0.5],
    "roughnessMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_r.png",
    "roughnessMacroTexSize": 80,
    "roughnessMacroStrength": [0.5, 0.5],
    "aoMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_ao.png",
    "aoMacroTexSize": 80,
    "heightMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_h.png",
    "heightMacroTexSize": 80,
}

CS1_TERRAIN_TEXTURE_SET = {
    "class": "TerrainMaterialTextureSet",
    "baseTexSize": [2048, 2048],
    "detailTexSize": [1024, 1024],
    "macroTexSize": [1024, 1024],
}


def find_beamng_install() -> Optional[str]:
    """Locate the BeamNG install, for base-game shapes and terrain resources."""
    candidates = [
        os.environ.get("BEAMNG_PATH"),
        r"D:\SteamLibrary\steamapps\common\BeamNG.drive",
        r"C:\Program Files (x86)\Steam\steamapps\common\BeamNG.drive",
        r"C:\Program Files\Steam\steamapps\common\BeamNG.drive",
        r"E:\SteamLibrary\steamapps\common\BeamNG.drive",
        r"D:\Steam\steamapps\common\BeamNG.drive",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "BeamNG.drive.exe")):
            return candidate
    return None


# ==========================================================================================
#  Buildings -- base-game shapes referenced in place
# ==========================================================================================
#
# A shape is referenced, never copied.  A copied DAE keeps <instance_material> targets belonging to
# the SOURCE level's material library, which this mod does not ship, and the engine renders every
# instance as its "No Mesh" placeholder.  Referencing in place is what working maps do:
# polish_roads_v2 uses 208 shapes from Industrial, 15 from italy and 8 from derby that way.
BEAMNG_BUILDING_SOURCES = [
    ("ind_bld_8x8.dae", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae", (8.20, 8.20, 5.73)),
    ("ind_bld_12x10.dae", "levels/italy/art/shapes/buildings/ind_bld_12x10.dae", (10.10, 12.10, 7.90)),
    ("ind_bld_12x15.dae", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae", (15.20, 12.20, 12.55)),
    ("ind_bld_12x20.dae", "levels/italy/art/shapes/buildings/ind_bld_12x20.dae", (20.34, 12.75, 11.50)),
    ("ind_bld_12x24.dae", "levels/italy/art/shapes/buildings/ind_bld_12x24.dae", (24.08, 13.01, 18.72)),
    ("ind_bld_12x30.dae", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae", (30.10, 12.11, 10.92)),
    ("ind_bld_24x60.dae", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae", (60.27, 31.07, 17.14)),
    ("city_west2.dae", "levels/west_coast_usa/art/shapes/buildings/city_west2.dae", (133.01, 91.59, 37.37)),
    ("city_west5.dae", "levels/west_coast_usa/art/shapes/buildings/city_west5.dae", (134.74, 94.73, 66.48)),
    ("city_block3.dae", "levels/west_coast_usa/art/shapes/buildings/city_block3.dae", (99.34, 87.42, 66.75)),
    ("condo_cylindrical.dae", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae", (56.19, 56.63, 87.24)),
]

BEAMNG_BUILDING_MODELS = [(member, size) for _n, member, size in BEAMNG_BUILDING_SOURCES]

# instanceColor tints repeated base-game shapes WITHOUT creating a material per variant.  Working
# maps vary thousands of instances this way.
BUILDING_INSTANCE_COLORS = {
    "Residential": [0.78, 0.76, 0.72, 1.0],
    "Commercial": [0.66, 0.72, 0.80, 1.0],
    "Industrial": [0.62, 0.60, 0.56, 1.0],
    "Office": [0.56, 0.64, 0.74, 1.0],
    "Beautification": [0.84, 0.82, 0.76, 1.0],
    "Electricity": [0.54, 0.54, 0.52, 1.0],
    "default": [0.74, 0.72, 0.68, 1.0],
}


def choose_beamng_model(width: float, depth: float, height: float):
    """
    Pick the base-game shape closest to this building; return (shapeName, model size, scale).

    The X/Y scale is UNIFORM so the mesh keeps its proportions.  Scaling axes independently to
    force a bounding box onto a footprint produced values like [2.64, 0.53, 1.00] and visibly
    deformed every building.  Models are never scaled above 1:1, so an instance can only occupy
    less than its own footprint -- never more, which is what let oversized props spill onto roads.
    """
    best = None
    for member, (mw, md, mh) in BEAMNG_BUILDING_MODELS:
        for swap in (False, True):
            model_w, model_d = (md, mw) if swap else (mw, md)
            aspect_error = abs((model_w / model_d) - (width / depth))
            size_error = abs(model_w - width) + abs(model_d - depth)
            cost = aspect_error * 8.0 + size_error
            if best is None or cost < best[0]:
                best = (cost, member, (mw, md, mh), swap)

    _cost, member, (mw, md, mh), swap = best
    model_w, model_d = (md, mw) if swap else (mw, md)

    fit = min(1.0, min(width / model_w, depth / model_d))
    vertical = max(height, 1.0) / mh
    return f"/{member}", (mw, md, mh), (fit, fit, max(fit, min(vertical, fit * 1.6)))
'''

PART2 = r'''

# ==========================================================================================
#  Roads
# ==========================================================================================

def chain_roads(roads: Sequence["Road"], max_sagitta: float = 0.5) -> List[Dict[str, Any]]:
    """
    Join road segments that share a node into continuous centre-lines.

    The export holds one segment per CS1 road piece and CS1 splits the network finely -- 780 of
    1244 segments are bare two-node stubs.  One DecalRoad each therefore leaves a gap at every
    boundary, because each decal fades in and out at its own ends.

    A node touched by three or more segments is a junction and chains are cut there, so each
    incoming road ends cleanly instead of several overlapping and stacking their fades.  Every
    segment is consumed exactly once, so no stretch is drawn twice.
    """
    if not roads:
        return []

    incident: Dict[int, List[Tuple[int, str]]] = {}
    for index, road in enumerate(roads):
        incident.setdefault(road.start_node_id, []).append((index, "start"))
        incident.setdefault(road.end_node_id, []).append((index, "end"))

    junction_nodes = {node for node, uses in incident.items() if len(uses) >= 3}
    used = [False] * len(roads)

    def polyline_of(road: "Road") -> List[Vec3]:
        return list(road.surface_polyline(max_sagitta))

    chains: List[Dict[str, Any]] = []
    order = sorted(
        range(len(roads)),
        key=lambda i: (
            0 if (roads[i].start_node_id in junction_nodes
                  or roads[i].end_node_id in junction_nodes) else 1,
            i,
        ),
    )

    for seed in order:
        if used[seed]:
            continue
        seed_road = roads[seed]
        used[seed] = True
        members = [seed]
        chain = polyline_of(seed_road)

        for direction in ("end", "start"):
            node_id = seed_road.end_node_id if direction == "end" else seed_road.start_node_id
            while node_id not in junction_nodes:
                candidates = [(i, e) for i, e in incident.get(node_id, []) if not used[i]]
                if len(candidates) != 1:
                    break
                idx, entered_by = candidates[0]
                nxt = roads[idx]
                used[idx] = True
                members.append(idx)

                pts = polyline_of(nxt)
                if entered_by == "start":
                    oriented = pts
                    node_id = nxt.end_node_id
                else:
                    oriented = list(reversed(pts))
                    node_id = nxt.start_node_id

                if direction == "end":
                    if chain and oriented and oriented[0].distance_to(chain[-1]) < 0.05:
                        oriented = oriented[1:]
                    chain.extend(oriented)
                else:
                    if chain and oriented and oriented[-1].distance_to(chain[0]) < 0.05:
                        oriented = oriented[:-1]
                    chain = oriented + chain

        if len(chain) < 2:
            continue

        widest = max(roads[i].measured_width for i in members)
        representative = roads[max(members, key=lambda i: roads[i].measured_width)]
        chains.append({
            "points": chain,
            "width": widest,
            "material": material_for(representative),
            "road": representative,
            "segments": len(members),
        })

    return chains


# ==========================================================================================
#  Level builder
# ==========================================================================================

class BeamNGLevelBuilder:
    def __init__(
        self,
        layout: CityLayout,
        output_root: str,
        level_name: str,
        mod_name: str,
        max_width: float = 6.0,
        include_non_drivable: bool = False,
        with_terrain: bool = True,
        heightmap_size: int = 2048,
        max_sagitta: float = 0.5,
    ) -> None:
        self.layout = layout
        self.output_root = output_root
        self.level_name = level_name
        self.mod_name = mod_name
        self.max_width = max_width
        self.include_non_drivable = include_non_drivable
        self.with_terrain = with_terrain
        self.heightmap_size = heightmap_size
        self.max_sagitta = max_sagitta

        self.mod_root = os.path.join(output_root, mod_name)
        self.level_root = os.path.join(self.mod_root, "levels", level_name)
        self.main_root = os.path.join(self.level_root, "main")

        self.roads: List[Road] = []
        self.buildings: List[Building] = []
        self.terrain: Optional[Terrain] = None
        self.terrain_block: Optional[Dict[str, Any]] = None
        self.sky_objects: List[Dict[str, Any]] = []

        # The engine's own material name is kept; nothing is renamed or authored.
        self.terrain_materials: List[str] = [CS1_TERRAIN_MATERIAL["internalName"]]
        self.texture_set_name = f"{level_name}TerrainMaterialTextureSet"
        self.terrain_texture_base_size = int(CS1_TERRAIN_TEXTURE_SET["baseTexSize"][0])

        self.report: Dict[str, Any] = {
            "levelName": level_name,
            "modName": mod_name,
            "roadsConverted": 0,
            "roadsSkipped": 0,
            "roadsSkippedByClass": {},
            "buildingsConverted": 0,
            "decalRoadNodes": 0,
            "materials": {},
            "files": [],
            "warnings": [],
        }

    # ---------------------------------------------------------------- primitives
    def write_json(self, path: str, payload: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def write_lines(self, path: str, objects: Iterable[Dict[str, Any]]) -> None:
        """
        Write a line-delimited items.level.json -- one COMPLETE object per physical line.

        Not cosmetic: the engine parses these one line at a time, and an object that wraps makes it
        reject the entire file with `Unable to deserialize file ...` while reporting nothing else.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            for obj in objects:
                handle.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
                handle.write("\n")
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def _emit_grouped(self, objects, group: str, container: str) -> List[str]:
        """
        Write objects into <container>/<group>/items.level.json.

        Objects go DIRECTLY in the folder named after their group, parented to that same name.
        Measured on polish_roads_v2: `Dworzec_traffic/items.level.json` holds 38 DecalRoads all
        parented to `Dworzec_traffic`; `DynamicLights` holds 1201 lights parented to
        `DynamicLights`.

        An object whose `__parent` does not name the group owning its folder is dropped silently --
        no log line at all.  That is what left the Roads folder empty while the geometry parsed
        cleanly.
        """
        written: List[str] = []
        if not objects:
            return written

        group_root = os.path.join(self.main_root, container, group)
        os.makedirs(group_root, exist_ok=True)

        for obj in objects:
            obj["__parent"] = group

        path = os.path.join(group_root, "items.level.json")
        self.write_lines(path, objects)
        written.append(os.path.relpath(path, self.mod_root))

        for name in os.listdir(group_root):
            candidate = os.path.join(group_root, name)
            if os.path.isdir(candidate):
                shutil.rmtree(candidate, ignore_errors=True)

        return written

    # ---------------------------------------------------------------- content
    def select_content(self) -> None:
        self.roads = [r for r in self.layout.roads if is_drivable(r)]
        skipped = [r for r in self.layout.roads if not is_drivable(r)]
        self.buildings = list(self.layout.buildings)

        by_class: Counter = Counter()
        for road in skipped:
            by_class[road.road_class or "unknown"] += 1
        self.report["roadsSkipped"] = len(skipped)
        self.report["roadsSkippedByClass"] = dict(by_class.most_common())

    def build_terrain(self) -> None:
        self.terrain = build_terrain(
            self.roads,
            self.buildings,
            resolution=self.heightmap_size,
            max_sagitta=self.max_sagitta,
        )

    def ground_height(self, x: float, y: float) -> float:
        if self.terrain is None:
            return 0.0
        t = self.terrain
        span = t.size * t.square_size
        origin = -span * 0.5
        gx = (x - origin) / span * (t.size - 1)
        gy = (y - origin) / span * (t.size - 1)
        gx = max(0.0, min(t.size - 1.001, gx))
        gy = max(0.0, min(t.size - 1.001, gy))
        x0, y0 = int(gx), int(gy)
        fx, fy = gx - x0, gy - y0
        h = t.heights
        top = h[y0, x0] * (1 - fx) + h[y0, x0 + 1] * fx
        bottom = h[y0 + 1, x0] * (1 - fx) + h[y0 + 1, x0 + 1] * fx
        value = top * (1 - fy) + bottom * fy
        return t.height_min + float(value) / 65535.0 * (t.max_height - t.height_min)

    # ---------------------------------------------------------------- terrain
    def emit_terrain_materials(self) -> None:
        """
        Write ONE terrain material, taken from an engine level.

        Every field is written as declared, apart from `name` and `persistentId` which the engine
        expects to be unique per level.  All fifteen texture references point at built-in content:
        five at the source engine level's art/terrains directory, ten at /assets/materials/terrain.
        No texture is copied and no material is authored.
        """
        material_name = self.terrain_materials[0]

        definition: Dict[str, Any] = dict(CS1_TERRAIN_MATERIAL)
        definition["name"] = material_name
        definition["persistentId"] = new_id()

        texture_set = dict(CS1_TERRAIN_TEXTURE_SET)
        texture_set["name"] = self.texture_set_name
        texture_set["persistentId"] = new_id()

        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{material_name}-{new_id()}": definition,
        }

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)

        self.terrain_texture_base_size = int((texture_set.get("baseTexSize") or [2048])[0])
        self.report["terrainMaterial"] = {
            "internalName": material_name,
            "groundmodelName": definition.get("groundmodelName"),
            "textureSet": texture_set["name"],
            "baseTexSize": self.terrain_texture_base_size,
            "detailTexSize": definition.get("baseColorDetailTexSize"),
            "texturesCopied": 0,
        }

    def emit_terrain_block(self) -> None:
        """
        The TerrainBlock, carrying the fields a working level carries.

        `baseTexSize` must equal the texture set's base size -- measured equal in every working
        map.  `materialTextureSet` must name a set THIS level declares.

        `squareSize` is omitted when it is 1 (polish_roads_v2 omits it); when the map needs a
        coarser grid it is written, because the shader uses it to turn world position into texture
        coordinates and omitting it would make the engine assume 1 m.
        """
        if self.terrain is None:
            return

        t = self.terrain
        span = t.size * t.square_size

        block: Dict[str, Any] = {
            "class": "TerrainBlock",
            "name": "theTerrain",
            "persistentId": new_id(),
            "__parent": "MissionGroup",
            "terrainFile": f"/levels/{self.level_name.lower()}/{self.level_name}.ter",
            "materialTextureSet": self.texture_set_name,
            "baseTexSize": self.terrain_texture_base_size,
            "maxHeight": round(t.max_height, 4),
            "lightMapSize": 1024,
            "screenError": 64,
            "castShadows": True,
            "position": [round(-span * 0.5, 3), round(-span * 0.5, 3), round(t.height_min, 3)],
            "rotationMatrix": list(IDENTITY_ROTATION),
        }
        if abs(t.square_size - 1.0) > 1e-9:
            block["squareSize"] = t.square_size

        self.terrain_block = block

    def emit_terrain_files(self) -> None:
        """Write the .ter, its descriptive .terrain.json, and the heightmap image."""
        if self.terrain is None:
            return

        ter_path = os.path.join(self.level_root, f"{self.level_name}.ter")
        write_ter_file(ter_path, self.terrain, self.terrain_materials)
        self.report["files"].append(os.path.relpath(ter_path, self.mod_root))

        heightmap_path = os.path.join(self.level_root, f"{self.level_name}.terrainheightmap.png")
        write_png_gray8(heightmap_path, self.terrain.heightmap_png)
        self.report["files"].append(os.path.relpath(heightmap_path, self.mod_root))

        t = self.terrain
        n = t.size * t.size
        self.write_json(
            os.path.join(self.level_root, f"{self.level_name}.terrain.json"),
            {
                "version": TERRAIN_FILE_VERSION,
                "size": t.size,
                "binaryFormat": (
                    "version(char), size(unsigned int), "
                    "heightMap(heightMapSize * heightMapItemSize), "
                    "layerMap(layerMapSize * layerMapItemSize), "
                    "layerTextureMap(layerMapSize * layerMapItemSize), materialNames"
                ),
                "datafile": f"/levels/{self.level_name.lower()}/{self.level_name}.ter",
                "heightmapImage": (
                    f"/levels/{self.level_name.lower()}/{self.level_name}.terrainheightmap.png"
                ),
                "heightMapSize": n,
                "heightMapItemSize": 2,
                "layerMapSize": n,
                "layerMapItemSize": 1,
                "materials": list(self.terrain_materials),
            },
        )

    # ---------------------------------------------------------------- roads
    def emit_roads(self) -> None:
        """
        One DecalRoad per chained centre-line.

        `autoJunction` and `autoLanes` are ENABLED by explicit instruction.  They ask the engine to
        weld road geometry where decals meet, so intersections connect themselves.  Measured on
        polish_roads_v2 these appear on only 6 of 6740 roads -- but that map hand-authors its
        junction pieces in dedicated groups; a converted city has none, so automatic joining is the
        correct behaviour here.

        The decal values below are the ones that map actually uses in bulk:
        `distanceFade [160,60]`, `decalBias 0.0005`, `detail 0.5`.
        """
        objects: List[Dict[str, Any]] = []
        material_usage: Counter = Counter()

        for entry in chain_roads(self.roads, self.max_sagitta):
            width = max(entry["width"], self.max_width)
            material = entry["material"]
            road = entry["road"]
            material_usage[material] += 1

            nodes: List[List[float]] = []
            for point in entry["points"]:
                bx, by, _ = point.beamng()
                bz = self.ground_height(bx, by) if self.terrain is not None else point.beamng()[2]
                nodes.append([round(bx, 4), round(by, 4), round(bz, 4), round(width, 4)])

            deduped: List[List[float]] = []
            for node in nodes:
                if deduped:
                    dx = node[0] - deduped[-1][0]
                    dy = node[1] - deduped[-1][1]
                    if dx * dx + dy * dy < 0.0004:
                        continue
                deduped.append(node)
            if len(deduped) < 2:
                continue

            objects.append({
                "class": "DecalRoad",
                "persistentId": new_id(),
                "__parent": "Roads",
                "position": deduped[0][:3],
                "material": material,
                "textureLength": 12.0,
                "renderPriority": 9,
                "drivability": 1.0,
                "oneWay": road.is_one_way,
                "improvedSpline": True,
                "autoJunction": True,
                "autoLanes": True,
                "detail": 0.5,
                "decalBias": 0.0005,
                "distanceFade": [160, 60],
                "startEndFade": [0.0, 0.0],
                "overObjects": not self.with_terrain,
                "nodes": deduped,
            })
            self.report["decalRoadNodes"] += len(deduped)

        self.report["roadsConverted"] = len(objects)
        self.report["materials"] = dict(material_usage.most_common())
        self.report["roadGroupFiles"] = self._emit_grouped(
            objects, group="Roads", container="MissionGroup"
        )

    # ---------------------------------------------------------------- buildings
    def emit_buildings(self) -> None:
        """
        Base-game shapes referenced IN PLACE, grounded on the HIGHEST surface under the footprint.

        The high point is used deliberately: sitting on the lowest point and then sinking drove
        buildings into the terrain.  A small gap over a dip is far less objectionable than an
        intersecting building.

        Appearance is varied with `instanceColor` rather than by creating a material per variant.
        """
        objects: List[Dict[str, Any]] = []

        for building in self.buildings:
            half_w = building.width * 0.5
            half_l = building.length * 0.5
            height = max(building.height, 3.0)

            bx, by, _ = building.position.beamng()
            yaw = yaw_to_beamng(building.angle_radians)

            ground = self.ground_height(bx, by)
            if self.terrain is not None:
                cos_a, sin_a = math.cos(yaw), math.sin(yaw)
                probes = [ground]
                for ox, oy in (
                    (-half_w, -half_l), (half_w, -half_l), (-half_w, half_l), (half_w, half_l),
                    (-half_w, 0.0), (half_w, 0.0), (0.0, -half_l), (0.0, half_l),
                ):
                    rx = ox * cos_a - oy * sin_a
                    ry = ox * sin_a + oy * cos_a
                    probes.append(self.ground_height(bx + rx, by + ry))
                ground = max(probes)

            model, _model_size, scale = choose_beamng_model(
                building.width, building.length, height
            )

            objects.append({
                "class": "TSStatic",
                "name": f"b_{building.building_id}",
                "persistentId": new_id(),
                "__parent": "Buildings",
                "shapeName": model,
                "position": [round(bx, 4), round(by, 4), round(ground, 4)],
                "rotationMatrix": [round(v, 8) for v in rotation_matrix_z(yaw)],
                "scale": [round(v, 5) for v in scale],
                "collisionType": "Collision Mesh",
                "decalType": "Collision Mesh",
                # Tints the base-game shape without creating a material.
                "instanceColor": BUILDING_INSTANCE_COLORS.get(
                    building.service, BUILDING_INSTANCE_COLORS["default"]
                ),
                "cs1Prefab": building.prefab_name,
                "cs1Service": building.service,
            })

        self.report["buildingsConverted"] = len(objects)
        self.report["buildingGroupFiles"] = self._emit_grouped(
            objects, group="Buildings", container="MissionGroup"
        )
'''

PART3 = r'''

    # ---------------------------------------------------------------- lighting
    def emit_sky_and_sun(self) -> None:
        """
        Lighting, copied verbatim from BeamNG's own `levels/template`.

        The engine ships that level as the starting point for new maps, so its sky block is
        guaranteed loadable by this build.  A hand-written block was rejected wholesale earlier
        with `Unable to deserialize file .../sky_and_sun/items.level.json`, which leaves the level
        unlit and completely black.

        `CloudLayer` in particular requires a `texture` field; without it the whole group fails.
        """
        objects: List[Dict[str, Any]] = []
        template = None

        game = find_beamng_install()
        if game:
            archive = os.path.join(game, "content", "levels", "template.zip")
            if os.path.isfile(archive):
                template = archive

        if template:
            with zipfile.ZipFile(template) as source:
                for entry in source.infolist():
                    if not entry.filename.lower().endswith("items.level.json"):
                        continue
                    try:
                        text = source.read(entry).decode("utf-8", "replace")
                    except Exception:
                        continue
                    decoder = json.JSONDecoder()
                    index = 0
                    while index < len(text):
                        while index < len(text) and text[index].isspace():
                            index += 1
                        if index >= len(text):
                            break
                        try:
                            obj, index = decoder.raw_decode(text, index)
                        except json.JSONDecodeError:
                            break
                        if not isinstance(obj, dict):
                            continue
                        if obj.get("class") in (
                            "LevelInfo", "TimeOfDay", "ScatterSky", "CloudLayer",
                            "Precipitation", "ForestWindEmitter",
                        ):
                            clone = dict(obj)
                            clone["persistentId"] = new_id()
                            clone["__parent"] = "sky_and_sun"
                            clone.pop("name", None)
                            clone["name"] = clone.get("name", obj.get("class"))
                            objects.append(clone)

        if not objects:
            self.report["warnings"].append(
                "no lighting objects could be read from levels/template; the map will be dark"
            )

        self.write_lines(
            os.path.join(self.main_root, "MissionGroup", "sky_and_sun", "items.level.json"),
            objects,
        )
        self.sky_objects = objects

    # ---------------------------------------------------------------- spawn
    def choose_spawn_point(self) -> Tuple[float, float, float]:
        """
        A spawn on a flat, road-adjacent piece of ground.

        A car placed on a slope or a cliff edge simply falls, so candidates are scored on the relief
        of a 12 m disc around them, their distance from the terrain edge, and proximity to a road.
        """
        best = None
        for chain in chain_roads(self.roads, self.max_sagitta):
            for point in chain["points"][:: max(1, len(chain["points"]) // 4)]:
                bx, by, _ = point.beamng()
                ground = self.ground_height(bx, by)

                if self.terrain is None:
                    return bx, by, ground

                t = self.terrain
                span = t.size * t.square_size
                half = span * 0.5
                edge = min(bx + half, half - bx, by + half, half - by)
                if edge < 200.0:
                    continue

                relief = 0.0
                for dx, dy in ((12, 0), (-12, 0), (0, 12), (0, -12)):
                    relief = max(relief, abs(self.ground_height(bx + dx, by + dy) - ground))
                if relief > 2.5:
                    continue

                score = relief * 10.0 - edge * 0.01
                if best is None or score < best[0]:
                    best = (score, bx, by, ground)

        if best is None:
            for road in self.roads:
                bx, by, _ = road.start_position.beamng()
                return bx, by, self.ground_height(bx, by)
            return 0.0, 0.0, 0.0

        _score, bx, by, ground = best
        return bx, by, ground

    def emit_spawns_and_mission(self) -> None:
        """
        The MissionGroup tree.

        `main/items.level.json` declares ONLY the top-level MissionGroup.  Its own folder holds the
        objects, the TerrainBlock, and one SimGroup per sub-folder -- a folder is only descended
        into when the sibling file declares a SimGroup whose name equals the folder name.
        """
        bx, by, ground = self.choose_spawn_point()
        spawn_z = ground + 1.0

        objects: List[Dict[str, Any]] = [
            {
                "class": "SpawnSphere",
                "name": "cs1_spawn",
                "persistentId": new_id(),
                "__parent": "MissionGroup",
                "position": [round(bx, 4), round(by, 4), round(spawn_z, 4)],
                "rotationMatrix": list(IDENTITY_ROTATION),
                "autoplaceOnSpawn": "0",
                "dataBlock": "SpawnSphereMarker",
                "enabled": "1",
                "homingCount": "0",
                "indoorWeight": "1",
                "isAIControlled": "0",
                "lockCount": "0",
                "outdoorWeight": "1",
                "radius": 5,
                "sphereWeight": "1",
            }
        ]

        if self.terrain_block is not None:
            objects.append(self.terrain_block)

        for group in ("sky_and_sun", "Roads", "Buildings"):
            if group == "Roads" and not self.roads:
                continue
            if group == "Buildings" and not self.buildings:
                continue
            objects.append({
                "class": "SimGroup",
                "name": group,
                "persistentId": new_id(),
                "__parent": "MissionGroup",
            })

        self.write_lines(
            os.path.join(self.main_root, "MissionGroup", "items.level.json"), objects
        )
        self.write_lines(
            os.path.join(self.main_root, "items.level.json"),
            [{"class": "SimGroup", "name": "MissionGroup", "persistentId": new_id(), "enabled": "1"}],
        )

    # ---------------------------------------------------------------- preview and info
    def emit_preview_image(self) -> None:
        """Write `_preview.png`, which the level selector requests for its tile."""
        if self.terrain is None:
            return

        size = 256
        grid = _resample(self.terrain.heights.astype(np.float32), size)
        gy, gx = np.gradient(grid)
        shade = np.clip(0.5 + (gx * 2.0 + gy * 2.0), 0.0, 1.0)
        shade = 0.45 + shade * 0.55
        base = np.array([0.42, 0.52, 0.30], dtype=np.float32)
        rgb = np.clip(base[None, None, :] * shade[:, :, None], 0.0, 1.0)
        pixels = (rgb * 255.0 + 0.5).astype(np.uint8)

        path = os.path.join(self.level_root, "_preview.png")
        write_png_rgb(path, pixels)
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def emit_info_json(self) -> None:
        if self.terrain is None:
            return
        t = self.terrain
        span = t.size * t.square_size
        bx, by, ground = self.choose_spawn_point()

        self.write_json(
            os.path.join(self.level_root, "info.json"),
            {
                "title": self.level_name,
                "description": (
                    f"Converted from a Cities: Skylines save by CS1-to-BeamNG. "
                    f"{self.report['roadsConverted']} roads, "
                    f"{self.report['buildingsConverted']} buildings."
                ),
                "authors": "CS1-to-BeamNG",
                "size": [int(span), int(span)],
                "defaultSpawnPointName": "cs1_spawn",
                "spawnPoints": [
                    {
                        "name": "cs1_spawn",
                        "position": [round(bx, 3), round(by, 3), round(ground + 1.0, 3)],
                        "rotation": [0, 0, 0],
                    }
                ],
            },
        )

    # ---------------------------------------------------------------- driver
    def build(self) -> None:
        """
        Order matters.

        `emit_terrain_materials()` runs BEFORE `emit_terrain_block()`: it sets
        `terrain_texture_base_size`, which the block writes as `baseTexSize`.  Running it afterwards
        left the block declaring 1024 against a texture set of [4096,4096].
        """
        self.select_content()
        self.build_terrain()
        self.emit_terrain_materials()
        self.emit_terrain_block()
        self.emit_terrain_files()
        self.emit_roads()
        self.emit_buildings()
        self.emit_sky_and_sun()
        self.emit_spawns_and_mission()
        self.emit_preview_image()
        self.emit_info_json()


# ==========================================================================================
#  Packaging and verification
# ==========================================================================================

def remove_stale_unpacked_level(level_name: str) -> Optional[str]:
    """
    Delete an unpacked level folder that would shadow this mod, and return its path.

    BeamNG resolves `current/levels/<name>/` BEFORE the same level inside a mod, so any folder there
    silently replaces everything the mod contains.  The World Editor creates one whenever a level is
    opened -- it writes `main.decals.json` even for a level it does not otherwise touch.

    A folder holding only that 281-byte file was enough to shadow a 13 MB archive for several
    rounds.  Any directory for this level is removed, matched case-insensitively.
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None

    levels_dir = os.path.join(local, "BeamNG", "BeamNG.drive", "current", "levels")
    if not os.path.isdir(levels_dir):
        return None

    for entry in os.listdir(levels_dir):
        if entry.lower() != level_name.lower():
            continue
        candidate = os.path.join(levels_dir, entry)
        if os.path.isdir(candidate):
            try:
                shutil.rmtree(candidate)
                return candidate
            except OSError:
                return None
    return None


def zip_mod(mod_root: str, zip_path: str) -> str:
    """
    Package the mod.  Entries go at the ARCHIVE ROOT (`levels/`, `art/`) -- wrapping them in a
    folder makes the engine report "Invalid ZIP file".
    """
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder, _dirs, files in os.walk(mod_root):
            for name in sorted(files):
                full = os.path.join(folder, name)
                archive.write(full, os.path.relpath(full, mod_root).replace(os.sep, "/"))
    return zip_path


def find_beamng_user_mods() -> Optional[str]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    target = os.path.join(local, "BeamNG", "BeamNG.drive", "current", "mods")
    return target if os.path.isdir(target) else None
'''

with io.open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(PART1)
    handle.write(PART2)
    handle.write(PART3)

print("wrote", OUT, len(PART1) + len(PART2) + len(PART3), "bytes")
import ast as _ast
_ast.parse(PART1 + PART2)
print("PARTS 1+2 SYNTAX OK")
_ast.parse(PART2 + PART3)
print("PARTS 2+3 SYNTAX OK")
