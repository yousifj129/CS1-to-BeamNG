"""
Emit one DecalRoad per source segment, instead of chaining segments into long polylines.

WHY THIS SHOULD FIX THE REMAINING GAPS
--------------------------------------
The user's observation was the clue: the painted road surface outlines every road perfectly, while
the decal drawn on top of it is unreliable.  Both come from the same source list, and measurement
shows chaining consumes 100% of the segments, so nothing is dropped.

What chaining DOES change is the geometry.  A chain's interior points come from each segment's
Bezier, while its endpoints are now snapped to the CS1 nodes.  Adjacent source segments share a
node, but their Beziers need not meet at that node -- CS1 offsets them.  So inside a long chain
(median 176 m, maximum 26.4 km) consecutive segments can meet at a slight kink or a small step that
snapping only fixes at the chain's two ends.  Where the step is large enough, the decal visibly
breaks.  That matches the report exactly: gaps in the middle of roads, not only at intersections.

Emitting one decal per source segment puts a NODE at every join, because both neighbours' decals
then terminate on the same shared coordinate.  It is also what the reference map does: of
polish_roads_v2's 6,740 DecalRoads, 42.1% are two-node roads and the median node count is 3 --
short decals, not long chained polylines.

Cost: 1,244 decal objects instead of 173, all in one file, which is well within what the reference
ships (4,946 decals in a single file there).
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

GENERATOR = '''

def roads_as_segments(roads: Sequence["Road"], max_sagitta: float = 0.5) -> List[Dict[str, Any]]:
    """
    One record per source segment, in the same shape `chain_roads` produces.

    Neighbouring segments share a node, and `surface_polyline` snaps each segment's first and last
    point to that node, so adjacent decals terminate on exactly the same coordinate.  Joins are
    therefore exact at every segment boundary rather than only at the ends of a chain.

    A segment's own width is used, so a wide road and a narrow one meeting at a node keep their
    distinct widths instead of both taking the widest value in the chain.
    """
    entries: List[Dict[str, Any]] = []
    for road in roads:
        points = road.surface_polyline(max_sagitta)
        if len(points) < 2:
            continue
        entries.append({
            "points": points,
            "width": max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0),
            "material": material_for(road),
            "source": road,
            "segments": 1,
        })
    return entries

'''

anchor = "def chain_roads("
if anchor not in src:
    raise SystemExit("chain_roads anchor not found")
src = src.replace(anchor, GENERATOR.strip() + "\n\n\n" + anchor, 1)

# ---- builder option --------------------------------------------------------------------------
OLD = """        roads_from_buildings: bool = False,
    ) -> None:"""
NEW = """        roads_from_buildings: bool = False,
        chain_roads_enabled: bool = True,
    ) -> None:"""
if OLD not in src:
    raise SystemExit("__init__ anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """        self.roads_from_buildings = roads_from_buildings"""
NEW = """        self.roads_from_buildings = roads_from_buildings
        # When False, one decal is emitted per source segment instead of chaining segments into
        # long polylines.  See `roads_as_segments`.
        self.chain_roads_enabled = chain_roads_enabled"""
if OLD not in src:
    raise SystemExit("__init__ body anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- strategy selection ----------------------------------------------------------------------
OLD = """        else:
            entries = chain_roads(self.roads, self.max_sagitta)
            self.report["roadSource"] = "cs1-road-graph\""""
NEW = """        elif self.chain_roads_enabled:
            entries = chain_roads(self.roads, self.max_sagitta)
            self.report["roadSource"] = "cs1-road-graph-chained"
        else:
            entries = roads_as_segments(self.roads, self.max_sagitta)
            self.report["roadSource"] = "cs1-road-graph-per-segment\""""
if OLD not in src:
    raise SystemExit("strategy anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- CLI -------------------------------------------------------------------------------------
OLD = """    parser.add_argument(
        "--roads-from-buildings","""
NEW = """    parser.add_argument(
        "--no-chain-roads",
        action="store_true",
        help="emit one DecalRoad per CS1 segment instead of chaining into long polylines",
    )
    parser.add_argument(
        "--roads-from-buildings","""
if OLD not in src:
    raise SystemExit("CLI anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- pass through convert() -------------------------------------------------------------------
OLD = """    roads_from_buildings: bool = False,
) -> Dict[str, Any]:"""
NEW = """    roads_from_buildings: bool = False,
    chain_roads_enabled: bool = True,
) -> Dict[str, Any]:"""
if OLD not in src:
    raise SystemExit("convert signature anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """        roads_from_buildings=roads_from_buildings,
        with_terrain=with_terrain,"""
NEW = """        roads_from_buildings=roads_from_buildings,
        chain_roads_enabled=chain_roads_enabled,
        with_terrain=with_terrain,"""
if OLD not in src:
    raise SystemExit("builder call anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """            roads_from_buildings=args.roads_from_buildings,
        )"""
NEW = """            roads_from_buildings=args.roads_from_buildings,
            chain_roads_enabled=not args.no_chain_roads,
        )"""
if OLD not in src:
    raise SystemExit("main call anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("roads_as_segments :", "def roads_as_segments(" in src)
print("option            :", "chain_roads_enabled: bool = True" in src)
print("CLI flag          :", '"--no-chain-roads"' in src)
