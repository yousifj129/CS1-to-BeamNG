"""
Extract just the sections of the BeamNG log that belong to OUR level.

The log accumulates several level loads in one session, so grepping globally attributes other
levels' errors (e.g. gridmap_v2's terrain material warnings) to ours.  This isolates the window
between our level's "Level loading" and the next level change.
"""

import os
import re

LOG = os.path.join(
    os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "beamng.log"
)
OUR_LEVEL = "cannes"

with open(LOG, encoding="utf-8", errors="replace") as handle:
    lines = handle.read().split("\n")

# Find every window where our level is loading.
starts = [i for i, l in enumerate(lines) if f"Level loading: '/levels/{OUR_LEVEL}/'" in l]
if not starts:
    # Fall back: any mention
    starts = [i for i, l in enumerate(lines) if OUR_LEVEL in l.lower()][:1]

print(f"log: {LOG}")
print(f"total lines: {len(lines)}")
print(f"load windows for '{OUR_LEVEL}': {len(starts)}")
print()

windows = []
for start in starts:
    # The window runs until the next level load of any level, or 2000 lines.
    end = len(lines)
    for j in range(start + 1, min(start + 4000, len(lines))):
        if "Level loading: '/levels/" in lines[j] and j > start:
            end = j
            break
    windows.append((start, end))

PATTERNS = re.compile(
    r"TerrainCellMaterial|WARNING_MATERIAL|TerrainMaterial|ground model|"
    r"Missing Terrain|Unable to deserialize|TSStatic|DecalRoad|"
    r"Level loaded|lighting|Lighting|ambient|Ambient|ScatterSky|TimeOfDay|"
    r"no datablock|unable to register|Missing|not found|Failed",
    re.I,
)

for index, (start, end) in enumerate(windows, 1):
    print("=" * 100)
    print(f"window {index}: lines {start + 1}..{end}")
    print("=" * 100)
    shown = 0
    for i in range(start, end):
        line = lines[i]
        if not line.strip():
            continue
        if PATTERNS.search(line):
            print("  " + line.strip()[:165])
            shown += 1
            if shown >= 45:
                print("  ... (truncated)")
                break
    print()

# Also: what does the level-select screen say about our level?
print("=" * 100)
print("level selector / preview references")
print("=" * 100)
for line in lines:
    if "cannes" in line.lower() and re.search(r"preview|selector|freeroamSelector|info\.json", line, re.I):
        print("  " + line.strip()[:165])
