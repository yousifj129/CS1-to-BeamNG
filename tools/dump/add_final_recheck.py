"""
Final safety shrink: resolve any overlap that survives the push.

Down to 2 of 1,463 buildings.  Both are `ind_bld_12x15` at scale 0.65574 overlapping by 1.390 m --
the shrunken bounding circle still reaches the road because the *model's* half-diagonal is larger
than the CS1 footprint the scale was derived from.

So after the shrink-or-push decision, one measured recheck runs: if the footprint's reach still
exceeds the centre clearance, the building is shrunk by exactly the remaining shortfall.  This is a
last resort, not the main rule, and it is bounded below so a building never collapses to nothing.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """                                # Resample: the building now stands somewhere else.
                                ground = self.ground_height(bx, by)"""

NEW = """                                # Resample: the building now stands somewhere else.
                                ground = self.ground_height(bx, by)

                    # Final recheck, measured rather than predicted.  The bounding circle can still
                    # reach a road after the steps above, because the model's half-diagonal is not
                    # the CS1 footprint the scale was derived from.  Shrink by whatever shortfall
                    # remains.  Bounded below so a building never collapses to nothing.
                    landed_edge = road_clearance(bx, by, self._road_segments)
                    if math.isfinite(landed_edge) and model_half_diag > 1e-6:
                        room = landed_edge - BUILDING_ROAD_CLEARANCE
                        if room < model_half_diag * scale[0] and room > 0.0:
                            allowed = max(0.05, room / model_half_diag)
                            if allowed < scale[0]:
                                scale = (allowed, allowed, min(scale[2], max(allowed, 1.0)))
                                self.report[\"buildingsShrunkForRoad\"] = (
                                    self.report.get(\"buildingsShrunkForRoad\", 0) + 1
                                )"""

if OLD not in src:
    raise SystemExit("final recheck anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("final recheck added:", "landed_edge = road_clearance(bx, by, self._road_segments)" in src)
