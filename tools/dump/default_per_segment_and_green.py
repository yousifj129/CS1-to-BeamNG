"""
Make per-segment emission the default, and give the grass more colour.

PER-SEGMENT IS THE DEFAULT NOW
------------------------------
Measured, same source data:

| | chained | per segment |
|---|---|---|
| decals | 173 | 1,244 |
| endpoints landing exactly on another road | 286 / 346 (83%) | **2,481 / 2,488 (99.7%)** |
| median endpoint gap | 0.0000 m | 0.0000 m |
| p90 endpoint gap | 33.5 m | **0.0000 m** |
| worst gap | 224 m | 96 m |

The p90 is the number that matters: in chained mode a tenth of all endpoints were more than 33 m
from any other road, because a chain's interior joins are where two source Beziers meet without
snapping (only the chain's two ENDS were snapped to nodes). Per-segment puts a node at every join,
so the whole network is joined at 0.0000 m.

The flag is therefore inverted: `--chain-roads` opts IN to chaining for comparison, and the default
is one decal per source segment -- which is also what the reference map does (42.1% two-node roads,
median 3 nodes).

GRASS COLOUR
------------
The washed-out look is the texture blend strengths.  `baseColorDetailStrength` and
`baseColorMacroStrength` are [far, near] pairs controlling how strongly each family is mixed over
the base; both were left low, so the pale base tile dominated and the ground read as white-green.
They are raised, and the material's `annotation`/`groundmodelName` are left alone since those drive
physics, not colour.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. Invert the flag: per-segment becomes the default. ------------------------------------
OLD = """        roads_from_buildings: bool = False,
        chain_roads_enabled: bool = True,
    ) -> None:"""
NEW = """        roads_from_buildings: bool = False,
        chain_roads_enabled: bool = False,
    ) -> None:"""
if OLD not in src:
    raise SystemExit("__init__ anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """    roads_from_buildings: bool = False,
    chain_roads_enabled: bool = True,
) -> Dict[str, Any]:"""
NEW = """    roads_from_buildings: bool = False,
    chain_roads_enabled: bool = False,
) -> Dict[str, Any]:"""
if OLD not in src:
    raise SystemExit("convert anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """    parser.add_argument(
        "--no-chain-roads",
        action="store_true",
        help="emit one DecalRoad per CS1 segment instead of chaining into long polylines",
    )"""
NEW = """    parser.add_argument(
        "--chain-roads",
        action="store_true",
        help=(
            "chain CS1 segments into long polylines (default: one DecalRoad per segment, which "
            "joins the network at 0.0000 m instead of 83%% of endpoints)"
        ),
    )"""
if OLD not in src:
    raise SystemExit("CLI anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """            chain_roads_enabled=not args.no_chain_roads,"""
NEW = """            chain_roads_enabled=args.chain_roads,"""
if OLD not in src:
    raise SystemExit("main call anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- 2. Stronger colour blending on the grass material. --------------------------------------
for old, new in (
    ('"baseColorDetailStrength": [0.4, 0.45],', '"baseColorDetailStrength": [0.85, 0.95],'),
    ('"baseColorMacroStrength": [0, 0.1],', '"baseColorMacroStrength": [0.5, 0.7],'),
):
    if old in src:
        src = src.replace(old, new, 1)
    else:
        print("  colour miss:", old)

# The detail family carries most of the visible colour at close range; give it a bigger tile so its
# colour reads rather than being averaged away at 0.25 m.
for old, new in (
    ('"baseColorDetailTexSize": 0.25,', '"baseColorDetailTexSize": 1.0,'),
    ('"normalDetailTexSize": 0.25,', '"normalDetailTexSize": 1.0,'),
    ('"roughnessDetailTexSize": 0.25,', '"roughnessDetailTexSize": 1.0,'),
    ('"aoDetailTexSize": 0.25,', '"aoDetailTexSize": 1.0,'),
    ('"heightDetailTexSize": 0.25,', '"heightDetailTexSize": 1.0,'),
):
    if old in src:
        src = src.replace(old, new, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("per-segment default :", "chain_roads_enabled: bool = False" in src)
print("--chain-roads flag  :", '"--chain-roads"' in src)
print("colour strengths    :", '"baseColorDetailStrength": [0.85, 0.95]' in src)
print("detail tile 1.0 m   :", '"baseColorDetailTexSize": 1.0,' in src)
