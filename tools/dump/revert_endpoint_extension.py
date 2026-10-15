"""
Revert the endpoint extension: it separated roads instead of joining them.

Measured on the built archive: **zero** endpoint locations are shared by two or more chains, and the
greatest distance between any coincident endpoints is 0.0000 m -- because there are none.

The cause is the extension itself.  It pushed each chain's end outward along that chain's own final
direction by up to 12 m.  At a junction the meeting chains approach from *different* directions, so
extending both moves their endpoints **apart** -- by up to 24 m at a right-angle junction.  Two
chains that previously met exactly at the junction node were pulled away from it.

The reasoning behind the extension was wrong: decals meeting at an angle need their ENDPOINTS to
coincide at the junction, not to overshoot past it.  Overshooting is only useful for two collinear
segments continuing in a straight line, which is not what a junction is.

So the extension is removed and chains end exactly at their junction node again.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """
        # Push both ends outward by one half-width so that chains meeting at a junction genuinely
        # overlap.  Chains are cut at junctions, so without this each decal merely touches its
        # neighbour -- and two decals that touch still show a seam once each has its own edge fade.
        reach = min(widest * 0.5, 12.0)
        chain = _extend_ends(chain, reach)"""

NEW = """
        # Chains end EXACTLY at their junction node, and that is deliberate.  An earlier version
        # pushed each end outward along the chain's own direction to force overlap; measured on the
        # built archive that left ZERO coincident endpoint locations, because at a junction the
        # meeting chains approach from different directions and extending both moves their ends
        # APART -- up to 24 m at a right angle.  Overshooting only helps two collinear segments,
        # which is not what a junction is."""

if OLD not in src:
    raise SystemExit("extension call anchor not found")
src = src.replace(OLD, NEW, 1)

# The helper is now unused; remove it so it cannot be reintroduced by accident.
start = src.index("def _extend_ends(")
end = src.index("def chain_roads(")
src = src[:start] + src[end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("extension call removed :", "_extend_ends(chain" not in src)
print("helper removed         :", "def _extend_ends(" not in src)
