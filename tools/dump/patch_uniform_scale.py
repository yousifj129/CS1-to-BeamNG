"""
Fix building scaling: use a UNIFORM scale instead of stretching each axis.

The previous version scaled X and Y independently to force the model's bounding box onto the
building's footprint, e.g. scale=[2.64, 0.53, 1.00] for a 12x30 m model on a 32x32 m building.
That squashes the mesh badly -- a 2.64x stretch on one axis and a 0.53x squash on the other is why
the buildings looked so wrong.

Instead the model is scaled uniformly to FIT within the building footprint, preserving its
proportions, and centred on it.  Slight under-coverage on the longer axis is far less objectionable
than severe distortion.

Aspect-aware selection is kept so the chosen model's proportions are reasonably close to the
building's, which minimises how much empty footprint is left.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("def choose_beamng_model(")
end = src.index("\n\n\n", start)

NEW = '''def choose_beamng_model(width: float, depth: float, height: float, service: str):
    """
    Pick the BeamNG building model closest to this building and return (path, size, scale).

    The scale is UNIFORM, so the mesh keeps its proportions.  Scaling X and Y independently to
    force the model's bounding box onto the footprint produced values like [2.64, 0.53, 1.00] --
    a 2.6x stretch on one axis against a 0.5x squash on the other -- which visibly deformed every
    building.  Fitting instead leaves a little uncovered footprint on the longer axis, which is
    far less noticeable than distorted geometry.

    Selection compares ASPECT RATIO rather than absolute size, so a 32x32 m building prefers a
    roughly square model over a long thin one even when the long one is numerically closer.
    """
    best = None
    for name, level, member, (mw, md, mh) in BEAMNG_BUILDING_MODELS:
        for swap in (False, True):
            model_w, model_d = (md, mw) if swap else (mw, md)
            # Aspect ratio similarity, plus a mild penalty for being far off in absolute size so
            # the model is not scaled up or down absurdly.
            aspect_error = abs((model_w / model_d) - (width / depth))
            size_error = abs(model_w - width) + abs(model_d - depth)
            cost = aspect_error * 8.0 + size_error
            if best is None or cost < best[0]:
                best = (cost, name, level, member, (mw, md, mh), swap)

    _cost, name, level, member, (mw, md, mh), swap = best
    model_w, model_d = (md, mw) if swap else (mw, md)

    # One uniform factor that fits the footprint: the smaller of the two axis ratios.
    fit = min(width / model_w, depth / model_d)
    # Keep the model's own height proportion, scaled by the same factor, but never let a building
    # become vanishingly thin.  CS1 heights are the real heights, so honour them where possible.
    target_h = max(height, 1.0)
    vertical = target_h / mh
    uniform = fit

    return (
        f"/{member}",
        (mw, md, mh),
        # Uniform in X and Y; Z follows the same factor so the model is not squashed vertically,
        # except that very tall CS1 buildings are allowed to stretch modestly.
        (uniform, uniform, max(uniform, min(vertical, uniform * 2.5))),
    )'''

src = src[:start] + NEW + src[end:]
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("uniform scale chooser written:", "One uniform factor that fits the footprint" in src)
