"""
Paint the road surface from the geometry that is ACTUALLY emitted.

The first version painted the layer map inside `build_terrain`, from `self.roads` -- the CS1 road
list.  That runs before the road strategy is applied, so with `--roads-from-buildings` the terrain
was painted with CS1 roads while 1,695 different decals were emitted on top.  The proof: both builds
reported exactly 195,967 asphalt cells despite having 173 and 1,695 roads, and the derived roads
would have covered far more.

Painted geometry must be the emitted geometry.  The painting now happens in `emit_roads`, from the
same chain list that produces the DecalRoads, and the `.ter` is written afterwards.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. build_terrain no longer paints ------------------------------------------------------
OLD = """
        # Paint the road footprint into the terrain's material layer map.  This is what gives roads
        # their own surface: a DecalRoad is only a decal and carries no grip, so without this the
        # whole map drives as one surface and roads feel like the ground they are drawn on.
        painted = apply_road_surface(self.terrain, self.roads)
        self.report["roadSurfaceCells"] = painted"""
if OLD not in src:
    raise SystemExit("build_terrain painting anchor not found")
src = src.replace(OLD, "\n        # The road surface is painted later, in emit_roads, from the geometry actually emitted.", 1)

# ---- 2. make apply_road_surface accept explicit centrelines ---------------------------------
OLD_FN = src[src.index("def rasterise_road_surface("):src.index("def choose_terrain_size(")]
NEW_FN = '''def rasterise_road_surface(
    roads: Sequence["Road"],
    terrain: "Terrain",
    extra_width: float = 1.0,
    max_sagitta: float = 1.5,
    centrelines: Optional[Sequence[Dict[str, Any]]] = None,
) -> Any:
    """
    Mark every terrain cell covered by a road, returning a boolean mask.

    Accepts either the CS1 `roads` list or a list of already-chained `centrelines` (the records
    `chain_roads` / `derive_roads_from_buildings` produce).  Pass `centrelines` whenever the emitted
    geometry may differ from the CS1 road list -- painting one geometry and emitting another leaves
    the road surface in the wrong place, which is exactly what happened when this was called from
    `build_terrain`.

    Each segment is walked in small steps and the cells within `width/2 + extra_width` of each step
    are set.  The buffer is applied to both sides and around each round dot, so segments meeting at
    a junction overlap there instead of leaving a thin grass seam exactly where tyres cross most.
    """
    if np is None:
        raise RuntimeError("numpy is required for terrain rasterising")

    res = terrain.size
    mask = np.zeros((res, res), dtype=bool)
    if res < 2:
        return mask

    span = terrain.world_size
    if span <= 0:
        return mask
    to_cell = (res - 1) / span

    def stamp(ax: float, ay: float, bx: float, by: float, radius: float) -> None:
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        step = max(0.5, min(radius, 2.0))
        steps = max(1, int(math.ceil(length / step)))
        cell_radius = radius * to_cell + 1.0

        for s in range(steps + 1):
            t = s / steps
            cx = (ax + dx * t - terrain.position_x) * to_cell
            cy = (ay + dy * t - terrain.position_y) * to_cell

            x0 = max(0, int(math.floor(cx - cell_radius)))
            x1 = min(res - 1, int(math.ceil(cx + cell_radius)))
            y0 = max(0, int(math.floor(cy - cell_radius)))
            y1 = min(res - 1, int(math.ceil(cy + cell_radius)))
            if x1 < x0 or y1 < y0:
                continue

            ys, xs = np.ogrid[y0 : y1 + 1, x0 : x1 + 1]
            inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= cell_radius * cell_radius
            mask[y0 : y1 + 1, x0 : x1 + 1] |= inside

    if centrelines is not None:
        for entry in centrelines:
            radius = max(float(entry.get("width") or 0.0), 1.0) * 0.5 + max(0.0, extra_width)
            pts = entry.get("points") or []
            for index in range(len(pts) - 1):
                ax, ay, _ = pts[index].beamng()
                bx, by, _ = pts[index + 1].beamng()
                stamp(ax, ay, bx, by, radius)
        return mask

    for road in roads:
        width = max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0)
        radius = width * 0.5 + max(0.0, extra_width)
        pts = road.surface_polyline(max_sagitta=max_sagitta)
        for index in range(len(pts) - 1):
            ax, ay, _ = pts[index].beamng()
            bx, by, _ = pts[index + 1].beamng()
            stamp(ax, ay, bx, by, radius)

    return mask


def paint_road_surface(
    terrain: "Terrain",
    centrelines: Sequence[Dict[str, Any]],
    extra_width: float = 1.0,
) -> int:
    """
    Paint the emitted centrelines into `terrain.layers`, returning the number of asphalt cells.

    Cells become `TERRAIN_LAYER_ASPHALT`, everything else `TERRAIN_LAYER_GRASS`.  255 is never
    written -- it punches a hole through the terrain rather than selecting a material.
    """
    mask = rasterise_road_surface(
        [], terrain, extra_width=extra_width, centrelines=centrelines
    )
    if not mask.any():
        return 0
    terrain.layers = np.where(mask, TERRAIN_LAYER_ASPHALT, TERRAIN_LAYER_GRASS).astype(np.uint8)
    return int(np.count_nonzero(mask))


'''
src = src.replace(OLD_FN, NEW_FN, 1)

# ---- 3. paint in emit_roads, and write the .ter afterwards -----------------------------------
OLD_LOOP = """        for entry in entries:
            width = max(entry["width"], self.max_width)"""
NEW_LOOP = """        # Paint the terrain surface from these SAME centrelines, so what grips matches what is
        # drawn.  Done before the objects are built so the layer map is final before the .ter is
        # written; `build()` orders emit_roads ahead of emit_terrain_files for that reason.
        if self.terrain is not None:
            self.report["roadSurfaceCells"] = paint_road_surface(self.terrain, entries)

        for entry in entries:
            width = max(entry["width"], self.max_width)"""
if OLD_LOOP not in src:
    raise SystemExit("emit_roads loop anchor not found")
src = src.replace(OLD_LOOP, NEW_LOOP, 1)

# ---- 4. reorder build(): roads before the .ter ----------------------------------------------
OLD_ORDER = """        self.emit_terrain_materials()
        self.emit_terrain_block()
        self.emit_terrain_files()
        self.emit_roads()"""
NEW_ORDER = """        self.emit_terrain_materials()
        self.emit_terrain_block()
        # Roads run BEFORE the terrain files: emitting them paints the road surface into the layer
        # map, and the .ter has to be written after that is final.  Writing it first would persist
        # an unpainted layer map and roads would carry no grip.
        self.emit_roads()
        self.emit_terrain_files()"""
if OLD_ORDER not in src:
    raise SystemExit("build order anchor not found")
src = src.replace(OLD_ORDER, NEW_ORDER, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("paints emitted geometry:", "paint_road_surface(self.terrain, entries)" in src)
print("roads before .ter     :", "self.emit_roads()\n        self.emit_terrain_files()" in src)
