"""Trace the clearance cap for the buildings that still overlap a road."""

import json
import math
import os
import sys
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, os.path.join(REPO, "tools"))
import beamng_convert as B

layout, _p, _w = B.load_city_layout(os.path.join(REPO, "exports", "Cannes_city_layout.json"))
roads = [r for r in layout.roads if B.is_drivable(r)]
segments = B.road_segments(roads)

by_id = {b.building_id: b for b in layout.buildings}
z = zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip"))
buildings = [
    json.loads(l)
    for l in z.read("levels/Cannes/main/MissionGroup/Buildings/items.level.json").decode().split("\n")
    if l.strip()
]
z.close()

target = None
for b in buildings:
    if b.get("name") == "b_806":
        target = b
        break

print("=== b_806 as emitted ===")
for k in ("name", "shapeName", "position", "scale", "cs1Prefab"):
    print(f"   {k:<12} {target.get(k)}")
print()

bx, by = target["position"][0], target["position"][1]
print(f"position (beamng x,y) = ({bx:.2f}, {by:.2f})")

centre_clearance = B.road_clearance(bx, by, segments)
print(f"clearance at the CENTRE to a road edge : {centre_clearance:+.3f} m")
print()

size = None
for member, dims in B.BEAMNG_BUILDING_MODELS:
    if member.endswith(target["shapeName"].rsplit("/", 1)[-1]):
        size = dims
print(f"model size {size}")
half_diag = 0.5 * math.hypot(size[0], size[1])
print(f"model half-diagonal (unscaled)         : {half_diag:.3f} m")
print(f"at the emitted scale {target['scale'][0]:.5f} -> {half_diag * target['scale'][0]:.3f} m")
print()
print("So the footprint reaches:" )
print(f"   centre clearance {centre_clearance:+.3f} minus half-diagonal {half_diag * target['scale'][0]:.3f}")
print(f"   = {centre_clearance - half_diag * target['scale'][0]:+.3f} m")
print()

# Was the cap even reached? Reproduce choose_beamng_model for this building.
source = None
for b in layout.buildings:
    bx2, by2, _ = b.position.beamng()
    if abs(bx2 - bx) < 0.01 and abs(by2 - by) < 0.01:
        source = b
        break
if source is None:
    print("could not find the source building")
else:
    print(f"source building: {source.prefab_name} {source.width:.1f} x {source.length:.1f}")
    model, msize, scale = B.choose_beamng_model(source.width, source.length, max(source.height, 3.0))
    print(f"choose_beamng_model -> {model} scale {scale}")
    mhalf = 0.5 * math.hypot(msize[0], msize[1])
    allowed = centre_clearance / mhalf if mhalf else 1.0
    print(f"   half-diagonal of the chosen model {mhalf:.3f} m")
    print(f"   allowed scale = clearance/half_diag = {allowed:.4f}")
    print(f"   emitted scale {target['scale'][0]:.5f}  -> cap {'BOUND' if allowed < target['scale'][0] else 'did NOT bind'}")
