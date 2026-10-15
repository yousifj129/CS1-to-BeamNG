"""Wire the building-derived road strategy into the builder and CLI."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- tidy the redundant expression ---------------------------------------------------------
src = src.replace("start = Vec3(ax, my * 0.0 + ay, 0.0)", "start = Vec3(ax, ay, 0.0)", 1)

# ---- builder option ------------------------------------------------------------------------
OLD = """        with_terrain: bool = True,
        heightmap_size: int = 2048,
        max_sagitta: float = 0.5,
    ) -> None:"""
NEW = """        with_terrain: bool = True,
        heightmap_size: int = 2048,
        max_sagitta: float = 0.5,
        roads_from_buildings: bool = False,
    ) -> None:"""
if OLD not in src:
    raise SystemExit("__init__ signature anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """        self.heightmap_size = heightmap_size
        self.max_sagitta = max_sagitta"""
NEW = """        self.heightmap_size = heightmap_size
        self.max_sagitta = max_sagitta
        # When set, the CS1 road geometry is discarded and streets are derived from the buildings
        # instead.  See `derive_roads_from_buildings`.
        self.roads_from_buildings = roads_from_buildings"""
if OLD not in src:
    raise SystemExit("__init__ body anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- use the strategy when emitting ----------------------------------------------------------
OLD = """        for entry in chain_roads(self.roads, self.max_sagitta):"""
NEW = """        if self.roads_from_buildings:
            # Derived from building positions rather than the CS1 road graph.
            entries = derive_roads_from_buildings(self.buildings)
            self.report["roadSource"] = "derived-from-buildings"
        else:
            entries = chain_roads(self.roads, self.max_sagitta)
            self.report["roadSource"] = "cs1-road-graph"

        for entry in entries:"""
if OLD not in src:
    raise SystemExit("emit_roads loop anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- CLI -----------------------------------------------------------------------------------
OLD = """    parser.add_argument(
        "--no-terrain","""
NEW = """    parser.add_argument(
        "--roads-from-buildings",
        action="store_true",
        help="discard the CS1 road geometry and derive streets from building positions instead",
    )
    parser.add_argument(
        "--no-terrain","""
if OLD not in src:
    raise SystemExit("CLI anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- pass it through -------------------------------------------------------------------------
import re

m = re.search(r"builder = BeamNGLevelBuilder\((.*?)\)\n", src, re.S)
if not m:
    raise SystemExit("builder construction not found")
call = m.group(0)
if "roads_from_buildings" not in call:
    new_call = call.replace(
        "with_terrain=", "roads_from_buildings=args.roads_from_buildings,\n            with_terrain=", 1
    )
    if new_call == call:
        # No with_terrain kwarg; append before the closing paren.
        new_call = call.rstrip()[:-1] + "        roads_from_buildings=args.roads_from_buildings,\n    )\n"
    src = src.replace(call, new_call, 1)
    print("wired the CLI flag into the builder")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("builder option :", "roads_from_buildings: bool = False" in src)
print("strategy used  :", "derive_roads_from_buildings(self.buildings)" in src)
print("CLI flag       :", '"--roads-from-buildings"' in src)
