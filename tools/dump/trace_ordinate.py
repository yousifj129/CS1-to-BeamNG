"""Trace exactly where the north ordinate is lost in the derived roads."""

import sys

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, REPO + r"\tools")
import beamng_convert as B

layout, problems, _w = B.load_city_layout(REPO + r"\exports\Cannes_city_layout.json")

print("buildings:", len(layout.buildings))
print()
print("building.position as loaded (CS1 slots) and as beamng():")
for b in layout.buildings[:4]:
    p = b.position
    print("   Vec3(%.2f, %.2f, %.2f)  -> beamng %s" % (p.x, p.y, p.z, tuple(round(v, 2) for v in p.beamng())))
print()

xs = [b.position.beamng()[0] for b in layout.buildings]
ys = [b.position.beamng()[1] for b in layout.buildings]
print("beamng X range: %.1f .. %.1f" % (min(xs), max(xs)))
print("beamng Y range: %.1f .. %.1f   <- ground-plane north ordinate" % (min(ys), max(ys)))
print()

chains = B.derive_roads_from_buildings(layout.buildings)
print("chains:", len(chains))
c = chains[0]
print("first chain points:")
for p in c["points"][:5]:
    print("   Vec3(%.2f, %.2f, %.2f) -> beamng %s" % (p.x, p.y, p.z, tuple(round(v, 2) for v in p.beamng())))
print()
cxs = [p.beamng()[0] for ch in chains for p in ch["points"]]
cys = [p.beamng()[1] for ch in chains for p in ch["points"]]
print("chain point beamng X range: %.1f .. %.1f" % (min(cxs), max(cxs)))
print("chain point beamng Y range: %.1f .. %.1f" % (min(cys), max(cys)))
