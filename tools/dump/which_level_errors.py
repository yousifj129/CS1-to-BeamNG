"""
Which levels produce the "Missing Terrain texture" error?

Every earlier conclusion rested on the assumption that polish_roads_v2 renders its terrain and ours
does not.  That was never actually verified from a log -- the check was run once while our level was
loaded, and the count was attributed to us without confirming polish produced zero.

This segments the log by level load and reports the error count inside each segment.
"""

import os
import re

LOG = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "beamng.log")

LEVEL_RE = re.compile(r"Level loading: '/levels/([^/]+)/", re.I)
ERROR_RE = re.compile(r"Missing Terrain texture", re.I)
TEXCACHE_RE = re.compile(r"terrainMaterialCache/([0-9A-F]+)\.dds", re.I)
TEXSET_RE = re.compile(r"TerrainMaterialTextureSet", re.I)

segments = []
current = None

with open(LOG, encoding="utf-8", errors="replace") as handle:
    for n, line in enumerate(handle, 1):
        m = LEVEL_RE.search(line)
        if m:
            current = {"level": m.group(1), "start": n, "errors": 0, "cache": [], "texset": 0}
            segments.append(current)
            continue
        if current is None:
            continue
        if ERROR_RE.search(line):
            current["errors"] += 1
        c = TEXCACHE_RE.search(line)
        if c:
            current["cache"].append(c.group(1))
        if TEXSET_RE.search(line):
            current["texset"] += 1

print(f"log: {LOG}")
print(f"level-load segments found: {len(segments)}")
print()
print(f"{'level':<22}{'from line':>10}{'errors':>8}{'texset':>8}{'distinct caches':>17}")
print("-" * 70)
for s in segments:
    print(f"{s['level']:<22}{s['start']:>10}{s['errors']:>8}{s['texset']:>8}{len(set(s['cache'])):>17}")

print()
print("Per-level detail for any segment with errors:")
for s in segments:
    if s["errors"]:
        caches = {}
        for c in s["cache"]:
            caches[c] = caches.get(c, 0) + 1
        print(f"   {s['level']}: {s['errors']} errors, {len(caches)} distinct cache keys")
        for key, count in list(caches.items())[:4]:
            print(f"      {key}  x{count}")
    else:
        print(f"   {s['level']}: 0 errors")

print()
total_errors = sum(s["errors"] for s in segments)
print(f"total 'Missing Terrain texture' lines in this log: {total_errors}")
