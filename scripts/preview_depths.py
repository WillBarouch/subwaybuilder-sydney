"""Render the depth-band polygons for a small area to a PNG, for checking contour quality.

    python scripts/preview_depths.py W S E N out.png [contours.json.gz]
"""
import gzip, json, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import PathPatch
from matplotlib.path import Path

W, S, E, N = map(float, sys.argv[1:5])
out = sys.argv[5]
src = sys.argv[6] if len(sys.argv) > 6 else 'build/SYD/ocean_depth_index_contours.json.gz'
depths = json.load(gzip.open(src, 'rt'))['depths']
fig, ax = plt.subplots(figsize=(10, 7), dpi=110)
cmap = plt.get_cmap('viridis')
n = 0
for e in depths:
    b = e['b']
    if b[2] < W or b[0] > E or b[3] < S or b[1] > N:
        continue
    verts, codes = [], []
    for ring in e['p']:
        verts += ring + [ring[0]]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(ring) - 1) + [Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=cmap(min(1, -e['d'] / 30)),
                           edgecolor='k', lw=0.3, alpha=0.55))
    n += 1
ax.set_xlim(W, E); ax.set_ylim(S, N)
ax.set_aspect(1 / np.cos(np.radians((S + N) / 2)))
ax.set_title(f'{n} depth polygons (semi-transparent: overlaps show darker)')
fig.savefig(out, bbox_inches='tight')
print(out, n)
