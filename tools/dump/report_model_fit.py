"""Report the model assignment quality: footprint distortion per building."""

import io
import json
import os
import sys

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, os.path.join(REPO, "tools"))

# Pull the chooser and the model table out of the converter without importing the whole module.
src = io.open(os.path.join(REPO, "tools", "beamng_convert.py"), encoding="utf-8").read()
ns = {"Optional": object, "Tuple": tuple, "List": list, "Dict": dict}
for block in ("BEAMNG_BUILDING_SOURCES = ", "def choose_beamng_model("):
    start = src.index(block)
    if block.startswith("BEAMNG"):
        end = src.index("\n\n\n", start)
    else:
        end = src.index("\n\n\n", start)
    exec(src[start:end], ns)

choose = ns["choose_beamng_model"]
models = ns["BEAMNG_BUILDING_MODELS"]
print(f"models available: {len(models)}")
for name, size in models:
    print(f"   {name:<26} {size[0]:>7.1f} x {size[1]:>7.1f} x {size[2]:>6.1f}")

layout = json.load(open(os.path.join(REPO, "exports", "Cannes_city_layout.json"), encoding="utf-8"))
buildings = [
    b for b in layout["buildings"]
    if not b.get("isCollapsed") and float(b.get("width") or 0) > 0.5 and float(b.get("length") or 0) > 0.5
]
print(f"\nbuildings: {len(buildings)}")

import collections

worst = []
use = collections.Counter()
for b in buildings:
    w, d = float(b["width"]), float(b["length"])
    h = max(float(b.get("height") or 0), 3.0)
    name, size, scale = choose(w, d, h, b.get("service") or "")
    use[name] += 1
    # Distortion: how far the two footprint axes deviate from the building.
    aw, ad = size[0] * scale[0], size[1] * scale[1]
    dist = abs(aw - w) + abs(ad - d)
    worst.append((dist, w, d, h, name, scale, size))

worst.sort(reverse=True)
print("\nmodel usage:")
for name, count in use.most_common():
    print(f"   {count:>5}x  {name}")

dists = sorted(x[0] for x in worst)
print(f"\nfootprint error (m, sum of both axes): median={dists[len(dists)//2]:.3f}  p90={dists[int(len(dists)*0.9)]:.3f}  max={dists[-1]:.3f}")
print("\nworst 8 assignments:")
for dist, w, d, h, name, scale, size in worst[:8]:
    print(f"   {w:.0f}x{d:.0f}x{h:.1f} -> {name:<24} model {size[0]:.1f}x{size[1]:.1f}  scale={['%.2f'%s for s in scale]}  err={dist:.1f}m")
