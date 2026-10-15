"""Rebuild the emission layer. Run from the repo root."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")

src = io.open(TARGET, encoding="utf-8").read()
lines = src.split("\n")

# Keep the module docstring, imports, core value types and core helpers: lines 1..1246.
keep = "\n".join(lines[:1246])

NEW = r'''
# ==========================================================================================
#  Terrain material -- taken from an ENGINE level, with no material authored and no texture copied
# ==========================================================================================
#
# There is no global terrain material library in BeamNG; a terrain material is always declared per
# level, in `levels/<level>/art/terrains/main.materials.json`.  Fifteen shipped levels provide one,
# and three of them -- east_coast_usa, west_coast_usa and Utah -- already use the arrangement that
# matters here: five base textures inside the level and ten from the engine's own library.
#
# One of those materials is reproduced below unchanged.  Its five local texture references are
# rewritten to the SAME engine level they came from, so every one of the fifteen slots resolves to
# built-in content:
#
#     base    /levels/east_coast_usa/art/terrains/...      (engine level, referenced in place)
#     detail  /assets/materials/terrain/...                (engine library)
#     macro   /assets/materials/terrain/...                (engine library)
#
# Referencing another level's textures by absolute path is proven to work: polish_roads_v2
# references ten textures inside east_coast_usa and its ground renders.
#
# Nothing is copied and nothing is authored.  The material's `internalName` is left exactly as the
# engine declares it.
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
        r"D:\\SteamLibrary\\steamapps\\common\\BeamNG.drive",
        r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\BeamNG.drive",
        r"C:\\Program Files\\Steam\\steamapps\\common\\BeamNG.drive",
        r"E:\\SteamLibrary\\steamapps\\common\\BeamNG.drive",
        r"D:\\Steam\\steamapps\\common\\BeamNG.drive",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "BeamNG.drive.exe")):
            return candidate
    return None


# ==========================================================================================
#  Buildings -- base-game shapes referenced in place
# ==========================================================================================
#
# A shape is referenced, never copied.  A copied DAE keeps <instance_material> targets that belong
# to the SOURCE level's material library, which this mod does not ship, and the engine then renders
# every instance as its "No Mesh" placeholder.  Referencing in place is also what a working map
# does: polish_roads_v2 uses 208 shapes from Industrial, 15 from italy and 8 from derby that way.
#
# Footprint and height are measured in metres, read from each DAE's POSITION accessor.
BEAMNG_BUILDING_SOURCES = [
    ("ind_bld_8x8.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae", (8.20, 8.20, 5.73)),
    ("ind_bld_12x10.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x10.dae", (10.10, 12.10, 7.90)),
    ("ind_bld_12x15.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae", (15.20, 12.20, 12.55)),
    ("ind_bld_12x20.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x20.dae", (20.34, 12.75, 11.50)),
    ("ind_bld_12x24.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x24.dae", (24.08, 13.01, 18.72)),
    ("ind_bld_12x30.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae", (30.10, 12.11, 10.92)),
    ("ind_bld_24x60.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae", (60.27, 31.07, 17.14)),
    ("city_west2.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/city_west2.dae", (133.01, 91.59, 37.37)),
    ("city_west5.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/city_west5.dae", (134.74, 94.73, 66.48)),
    ("city_block3.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/city_block3.dae", (99.34, 87.42, 66.75)),
    ("condo_cylindrical.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae", (56.19, 56.63, 87.24)),
]

BEAMNG_BUILDING_MODELS = [
    (member, size) for _name, _level, member, size in BEAMNG_BUILDING_SOURCES
]

# instanceColor palette, used to vary the appearance of repeated base-game shapes WITHOUT creating
# a material per variant.  polish_roads_v2 varies 8607 instances this way.
BUILDING_INSTANCE_COLORS = {
    "Residential": [0.78, 0.76, 0.72, 1.0],
    "Commercial": [0.66, 0.72, 0.80, 1.0],
    "Industrial": [0.62, 0.60, 0.56, 1.0],
    "Office": [0.56, 0.64, 0.74, 1.0],
    "Beautification": [0.84, 0.82, 0.76, 1.0],
    "Electricity": [0.54, 0.54, 0.52, 1.0],
    "default": [0.74, 0.72, 0.68, 1.0],
}


def choose_beamng_model(width: float, depth: float, height: float, service: str):
    """
    Pick the base-game shape closest to this building and return (shapeName, model size, scale).

    The scale is UNIFORM in X/Y so the mesh keeps its proportions; scaling the axes independently
    to force a bounding box onto a footprint produced values like [2.64, 0.53, 1.00] and visibly
    deformed every building.  Z follows the same factor with a ceiling, because CS1 heights are
    genuine but stretching a model 2.6x vertically is as disfiguring as squashing it sideways.

    Models are never scaled ABOVE 1:1, so an instance can only occupy less than its own footprint --
    never more, which is what let oversized props spill across roads in an earlier attempt.
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


# ==========================================================================================
#  Roads -- chain segments, then emit one DecalRoad per chain
# ==========================================================================================

def chain_roads(roads: Sequence["Road"], max_sagitta: float = 0.5) -> List[Dict[str, Any]]:
    """
    Join road segments that share a node into long continuous centre-lines.

    The export holds one segment per CS1 road piece and CS1 splits the network finely -- 780 of
    1244 segments are bare two-node stubs.  Emitting one DecalRoad each leaves a gap at every
    boundary, because each decal fades in and out at its own ends.

    Junctions: a node touched by three or more segments is a junction and chains are cut there, so
    each incoming road ends cleanly rather than several overlapping and stacking their fades.

    Every segment is consumed exactly once, so no stretch of road is drawn twice.
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
                candidates = [
                    (idx, end) for idx, end in incident.get(node_id, []) if not used[idx]
                ]
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
        chains.append(
            {
                "points": chain,
                "width": widest,
                "material": material_for(representative),
                "road": representative,
                "segments": len(members),
            }
        )

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

        # The material keeps the engine's own internal name; nothing is renamed or authored.
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
            "problems": [],
        }

    # ---------------------------------------------------------------- primitives
    def write_json(self, path: str, payload: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def write_lines(self, path: str, objects: Iterable[Dict[str, Any]]) -> None:
        """
        Write a line-delimited items.level.json.

        One COMPLETE JSON object per physical line.  This is not cosmetic: the engine parses these
        files one line at a time, and an object that wraps makes it reject the whole file with
        `Unable to deserialize file ...` while reporting nothing else.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            for obj in objects:
                handle.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
                handle.write("\n")
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def _emit_grouped(
        self, objects: List[Dict[str, Any]], group: str, container: str
    ) -> List[str]:
        """
        Write objects into <container>/<group>/items.level.json.

        Objects go DIRECTLY in the folder named after their group, with `__parent` set to that same
        name.  Measured on polish_roads_v2: `Dworzec_traffic/items.level.json` holds 38 DecalRoads
        all parented to `Dworzec_traffic`, and `DynamicLights` holds 1201 lights parented to
        `DynamicLights`.

        An object whose `__parent` does not name the group owning its folder is dropped by the
        engine with no log output at all -- that is what left the Roads folder empty while the
        geometry parsed cleanly.
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

        # Remove stale chunk folders from any earlier layout so they cannot linger.
        for name in os.listdir(group_root):
            candidate = os.path.join(group_root, name)
            if os.path.isdir(candidate):
                shutil.rmtree(candidate, ignore_errors=True)

        return written

    # ---------------------------------------------------------------- content
    def select_content(self) -> None:
        keep = [r for r in self.layout.roads if is_drivable(r)]
        skipped = [r for r in self.layout.roads if not is_drivable(r)]
        self.roads = keep
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
        gx = (x - (-span * 0.5)) / span * (t.size - 1)
        gy = (y - (-span * 0.5)) / span * (t.size - 1)
        gx = max(0.0, min(t.size - 1.001, gx))
        gy = max(0.0, min(t.size - 1.001, gy))
        x0, y0 = int(gx), int(gy)
        fx, fy = gx - x0, gy - y0
        h = t.heights
        top = h[y0, x0] * (1 - fx) + h[y0, x0 + 1] * fx
        bottom = h[y0 + 1, x0] * (1 - fx) + h[y0 + 1, x0 + 1] * fx
        value = top * (1 - fy) + bottom * fy
        return t.height_min + float(value) / 65535.0 * (t.max_height - t.height_min)

    def emit_terrain_materials(self) -> None:
        """
        Write ONE terrain material, taken from an engine level.

        Every field is written as declared apart from `name` and `persistentId`, which the engine
        expects to be unique per level.  The fifteen texture references all point at built-in
        content: five at the source engine level's `art/terrains/` directory and ten at
        `/assets/materials/terrain/`.  No texture is copied and no material is authored.
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
        The TerrainBlock, with the fields a working level carries.

        `baseTexSize` must equal the texture set's base size -- measured equal in every working
        map.  `materialTextureSet` must name a set THIS level declares.

        `squareSize` is omitted when it is 1, matching polish_roads_v2; when the map is too large
        for a 1 m grid it is written, because the shader uses it to map world position to texture
        coordinates and omitting it would make the engine assume 1.
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
            "position": [
                round(-span * 0.5, 3),
                round(-span * 0.5, 3),
                round(t.height_min, 3),
            ],
            "rotationMatrix": list(IDENTITY_ROTATION),
        }
        if abs(t.square_size - 1.0) > 1e-9:
            block["squareSize"] = t.square_size

        self.terrain_block = block
'''
