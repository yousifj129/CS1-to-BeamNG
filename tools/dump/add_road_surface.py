"""
Paint the road network into the terrain's material layer map, and fix junction gaps.

WHY THIS MATTERS FOR PHYSICS
----------------------------
A `DecalRoad` is a decal: it changes how the ground looks, not what the tyres grip.  Until now the
whole terrain was one grass material, so road and off-road grip were identical -- which is exactly
why driving felt like gravel everywhere.

BeamNG resolves physics from `TerrainMaterial.groundmodelName` per *terrain cell*, through the
`.ter` layer map.  So the road footprint has to be written into that layer map and given an asphalt
material.  Then a road is physically a road, not a picture of one.

WHAT THIS ADDS
--------------
1. A second terrain material, `Asphalt`, declared alongside `Grass`.
2. A rasteriser that walks every road segment and marks the cells it covers as asphalt, buffered
   outwards so that roads meeting at a junction actually overlap there rather than leaving a gap.

The two `.ter` material names are stored in layer-map index order: index 0 = Grass, index 1 =
Asphalt.  That ordering is what makes the layer bytes mean anything.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ==============================================================================================
# 1. A rasteriser for the road footprint.
# ==============================================================================================
RASTERISER = '''

# ==========================================================================================
#  Road surface rasterising
# ==========================================================================================

# Layer-map index of each terrain material.  The `.ter` stores its material NAMES in this same
# order, and every layer byte is an index into that list, so these two must not drift apart.
TERRAIN_LAYER_GRASS = 0
TERRAIN_LAYER_ASPHALT = 1
TERRAIN_MATERIAL_ORDER = ["Grass", "Asphalt"]


def rasterise_road_surface(
    roads: Sequence["Road"],
    terrain: "Terrain",
    extra_width: float = 1.0,
    max_sagitta: float = 1.5,
) -> Any:
    """
    Mark every terrain cell covered by a road, returning a boolean mask.

    Each segment is walked in small steps and the cells within `width/2 + extra_width` of each
    step are set.  Two details matter:

    * The buffer is applied to BOTH sides and around each round dot, so segments meeting at a
      junction overlap there.  Without it the smooth road edges leave a thin grass seam exactly at
      the place the tyres cross most often.
    * `extra_width` adds a small margin beyond the drawn road, so the painted surface is always at
      least as wide as the decal sitting on top of it.  A painted surface narrower than its decal
      would put a grip discontinuity under the visible road edge.

    CS1 road nodes carry their own Y, but the mask is purely 2D: which cells are asphalt does not
    depend on elevation.
    """
    if np is None:
        raise RuntimeError("numpy is required for terrain rasterising")

    res = terrain.size
    mask = np.zeros((res, res), dtype=bool)
    if res < 2 or not roads:
        return mask

    span = terrain.world_size
    # Guard against a degenerate extent; without this the cell maths divides by zero.
    if span <= 0:
        return mask
    to_cell = (res - 1) / span

    for road in roads:
        width = max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0)
        radius = width * 0.5 + max(0.0, extra_width)
        # Step finely enough that consecutive stamps overlap even on the narrowest road.
        step = max(0.5, min(radius, 2.0))

        points = road.surface_polyline(max_sagitta=max_sagitta)
        for index in range(len(points) - 1):
            ax, ay, _ = points[index].beamng()
            bx, by, _ = points[index + 1].beamng()

            dx, dy = bx - ax, by - ay
            length = math.hypot(dx, dy)
            steps = max(1, int(math.ceil(length / step)))

            for s in range(steps + 1):
                t = s / steps
                px = ax + dx * t
                py = ay + dy * t

                cx = (px - terrain.position_x) * to_cell
                cy = (py - terrain.position_y) * to_cell
                cell_radius = radius * to_cell + 1.0

                x0 = max(0, int(math.floor(cx - cell_radius)))
                x1 = min(res - 1, int(math.ceil(cx + cell_radius)))
                y0 = max(0, int(math.floor(cy - cell_radius)))
                y1 = min(res - 1, int(math.ceil(cy + cell_radius)))
                if x1 < x0 or y1 < y0:
                    continue

                ys, xs = np.ogrid[y0 : y1 + 1, x0 : x1 + 1]
                inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= cell_radius * cell_radius
                mask[y0 : y1 + 1, x0 : x1 + 1] |= inside

    return mask


def apply_road_surface(terrain: "Terrain", roads: Sequence["Road"], extra_width: float = 1.0) -> int:
    """
    Paint the road footprint into `terrain.layers`, returning the number of cells changed.

    Cells become `TERRAIN_LAYER_ASPHALT`; everything else stays `TERRAIN_LAYER_GRASS`.  255 is never
    written -- that value punches a hole through the terrain instead of selecting a material.
    """
    mask = rasterise_road_surface(roads, terrain, extra_width=extra_width)
    if not mask.any():
        return 0

    before = np.count_nonzero(terrain.layers != TERRAIN_LAYER_ASPHALT)
    terrain.layers = np.where(mask, TERRAIN_LAYER_ASPHALT, TERRAIN_LAYER_GRASS).astype(np.uint8)
    after = np.count_nonzero(terrain.layers != TERRAIN_LAYER_ASPHALT)
    return int(before - after)

'''

anchor = "def choose_terrain_size("
if anchor not in src:
    raise SystemExit("choose_terrain_size anchor not found")
src = src.replace(anchor, RASTERISER.strip() + "\n\n\n" + anchor, 1)

# ==============================================================================================
# 2. Emit two terrain materials, in layer-index order.
# ==============================================================================================
OLD_METHOD = src[src.index("    def emit_terrain_materials(self) -> None:"):src.index("    def emit_terrain_block(self) -> None:")]

NEW_METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        Write the terrain materials, in layer-map index order.

        Two materials are declared: `Grass` for the ground and `Asphalt` for the painted road
        surface.  Index 0 is Grass and index 1 is Asphalt, matching `TERRAIN_MATERIAL_ORDER`, which
        is also the order their names are stored in the `.ter`.  Every layer byte is an index into
        that list, so the two must agree.

        Both materials are taken from working levels and only their texture paths are changed --
        all fifteen slots per material point at built-in engine content.  Nothing is authored and
        no texture is copied.
        """
        material_names = list(TERRAIN_MATERIAL_ORDER)

        definitions: Dict[str, Any] = {}
        texture_set = dict(CS1_TERRAIN_TEXTURE_SET)
        texture_set["name"] = self.texture_set_name
        texture_set["persistentId"] = new_id()
        definitions[f"{self.level_name}TerrainMaterialTextureSet"] = texture_set

        for name in material_names:
            template = CS1_TERRAIN_MATERIAL if name == "Grass" else CS1_ASPHALT_MATERIAL
            definition = dict(template)
            definition["name"] = f"{name}-{new_id()}"
            definition["persistentId"] = new_id()
            definitions[definition["name"]] = definition

        # Merge the building window aliases into this same file.  It is the one material library
        # the engine is known to load for this level, so a shape's window material is redirected
        # without relying on any other lookup path.
        definitions.update(getattr(self, "window_material_aliases", {}))

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)

        self.terrain_materials = material_names
        self.terrain_texture_base_size = int((texture_set.get("baseTexSize") or [2048])[0])
        self.report["terrainMaterial"] = {
            "internalNames": material_names,
            "groundmodelNames": [
                (CS1_TERRAIN_MATERIAL if n == "Grass" else CS1_ASPHALT_MATERIAL)["groundmodelName"]
                for n in material_names
            ],
            "textureSet": texture_set["name"],
            "baseTexSize": self.terrain_texture_base_size,
            "texturesCopied": 0,
        }

'''

src = src.replace(OLD_METHOD, NEW_METHOD, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("rasteriser added :", "def rasterise_road_surface(" in src)
print("apply_road_surface:", "def apply_road_surface(" in src)
print("two materials    :", "TERRAIN_MATERIAL_ORDER" in src)
