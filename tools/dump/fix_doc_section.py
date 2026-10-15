"""Replace the duplicated road section (lines 495-534) with a single clean one."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

lines = io.open(PATH, encoding="utf-8").read().split("\n")

# Sanity-check the region before touching it.
print("line 495:", lines[494][:70])
print("line 511:", lines[510][:70])
print("line 513:", lines[512][:70])
print("line 534:", lines[533][:70])

NEW = [
    "### 5.2 The `autoJunction` question",
    "",
    "Measured: of **6,740** DecalRoads, `autoJunction` is present on **6** -- and in all six cases its",
    "value is **`false`**. `autoLanes` is present on **none**.",
    "",
    "This was once read as \"autoJunction is wrong and should be removed\", which was a mistake. This",
    "map **hand-authors its junctions**: dedicated groups such as `Dworzec_traffic` (38 roads) and",
    "`road_inv` (701 roads) exist specifically to build junction and invisible-road geometry by hand,",
    "and a further 4,946 decals sit under `DecalRoad_Meshroady/`. A converted CS1 city has none of",
    "those hand-built pieces, so automatic joining is the appropriate behaviour there even though this",
    "map does not need it.",
    "",
    "`autoJunction` and `autoLanes` are therefore **kept enabled** in our converter, by explicit",
    "instruction, as a deliberate divergence from this map.",
    "",
    "Worth recording alongside it: this map's node-count distribution shows **2,840 two-node roads",
    "(42.1%)**. A working map is built from many short decals, so short decals are not in themselves",
    "the cause of gaps.",
    "",
    "### 5.3 DecalRoad property frequencies",
    "",
    "The complete inventory is in section 5.1b above, measured from all 6,740 objects. Two further",
    "observations are worth stating separately:",
    "",
    "* `improvedSpline`, `oneWay`, `gatedRoad` and `overObjects` are **only ever written as `true`**.",
    "  The key is either present-and-true or absent; `false` never appears.",
    "* `distanceFade` uses only **23 distinct values** across 5,878 objects, heavily clustered on",
    "  presets rather than edited per road.",
    "",
    "Our converter previously emitted `distanceFade [3000,500]` and `decalBias 0.002`, each roughly",
    "an order of magnitude away from anything this map uses.",
]

# Replace lines 495..534 inclusive (0-based 494..533).
lines = lines[:494] + NEW + lines[534:]

io.open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("\nreplaced", 534 - 494 + 1, "lines with", len(NEW))
