"""
make_zippy_map.py  -  builds a rough Nav2 occupancy map of the flat from Aayush's sketch.

Output: home.pgm + home.yaml           navigation map (walls + furniture)
        home_walls.pgm + home_walls.yaml  walls only, for linorobot2's world_creator
        home_furniture.txt                door sills + furniture boxes to paste into home.sdf
        home_preview.png                  labelled picture in Gazebo/RViz coordinates

Frame (looking at the sketch with the text readable):
  X  -> along the long side of the flat (left = Bedroom A / B end, right = Bedroom C / D end)
  Y  -> up (bottom = Main Door side, top = Sofa / Swing side)
All numbers are in METRES. Edit them and re-run:  python3 make_zippy_map.py
"""
import numpy as np

RES = 0.05            # metres per pixel (Nav2 default)
MARGIN = 0.5          # unknown border around the flat
OUTER_T = 0.25        # outer wall thickness
INNER_T = 0.15        # inner wall thickness
DOOR = 0.76           # "about 2.5 ft" (measured 5 Oct 2026)
MAIN_DOOR = 1.00

FREE, OCC, UNKNOWN = 254, 0, 205

# ---------------------------------------------------------------- floor (free space)
FLOOR = [
    (0.0, 20.4, 1.1, 9.5),    # main rectangle of the flat
    (7.4, 11.2, 0.0, 1.1),    # entrance bump (Main Door side)
]

# ---------------------------------------------------------------- walls: (x0, x1, y0, y1, thickness)
# horizontal wall: y0 == y1, vertical wall: x0 == x1
WALLS = [
    # outer
    (0.0, 7.4, 1.1, 1.1, OUTER_T), (11.2, 20.4, 1.1, 1.1, OUTER_T),
    (7.4, 11.2, 0.0, 0.0, OUTER_T),
    (7.4, 7.4, 0.0, 1.1, OUTER_T),
    (0.0, 20.4, 9.5, 9.5, OUTER_T),
    (0.0, 0.0, 1.1, 9.5, OUTER_T), (20.4, 20.4, 1.1, 9.5, OUTER_T),
    # Bedroom A + Guest Room
    (0.0, 7.4, 4.5, 4.5, INNER_T),     # A, Guest | top toilets, lobby, hall
    (3.9, 3.9, 1.1, 4.5, INNER_T),     # Bedroom A | Guest Room  (v2)
    (7.4, 7.4, 1.1, 4.5, INNER_T),     # Guest Room | entrance
    # top toilet block (cupboard strip + 2 toilets, stacked)  (v2)
    (2.3, 2.3, 4.5, 6.5, INNER_T),
    (0.0, 2.3, 5.47, 5.47, INNER_T),
    (0.0, 2.3, 5.95, 5.95, INNER_T),
    (0.0, 4.1, 6.5, 6.5, INNER_T),     # toilets/lobby | B
    (4.1, 4.1, 6.5, 9.5, INNER_T),     # B | hall  (v3: lobby side is open space)
    # TV wall in the hall  (v2)
    (7.4, 10.6, 5.475, 5.475, 0.45),
    # kitchen
    (11.2, 11.2, 0.0, 4.5, INNER_T),
    (11.2, 14.6, 4.5, 4.5, INNER_T),
    (14.6, 14.6, 1.1, 4.5, INNER_T),
    # mandir now runs the full depth up to the lobby  (v2)
    (14.6, 16.4, 4.6, 4.6, INNER_T),
    # bottom lobby top: solid, no door into D from here  (v2)
    (14.6, 16.4, 5.75, 5.75, 0.5),
    # Bedroom C / passage / bottom toilet block  (v2)
    (16.4, 16.4, 1.1, 4.6, INNER_T),   # mandir | C  (v3: lobby -> passage is open space)
    (16.4, 16.4, 5.5, 9.5, INNER_T),   # wall block | passage + Bedroom D
    (16.4, 20.4, 4.45, 4.45, INNER_T), # C | passage + toilets
    (17.3, 17.3, 4.45, 6.75, INNER_T), # passage | toilet block
    (17.3, 20.4, 5.3, 5.3, INNER_T),
    (17.3, 20.4, 6.15, 6.15, INNER_T),
    (17.3, 20.4, 6.75, 6.75, INNER_T),
    # Bedroom D
    (14.6, 14.6, 6.0, 9.5, INNER_T),   # D | dining
]

# ---------------------------------------------------------------- doors cut into walls
# (name, x_or_y_of_wall, start, end, orientation)  'h' = gap along X in a horizontal wall
DOORS = [
    # ("Main door",   0.0, 8.8, 8.8 + MAIN_DOOR, "h"),   # kept CLOSED: Zippy should never leave the flat
    ("Bedroom A",   4.5, 2.5, 2.5 + DOOR, "h"),
    ("Guest Room",  4.5, 4.8, 4.8 + DOOR, "h"),
    ("Bedroom B",   6.5, 3.0, 3.0 + DOOR, "h"),
    ("Kitchen",     4.5, 12.4, 12.4 + DOOR, "h"),
    ("Bedroom C",   4.45, 16.45, 16.45 + DOOR, "h"),
    # Bedroom D: doorway across the top of the passage (open, full passage width)
    # toilet doors are left CLOSED on purpose - Zippy never needs to go in
]

# ---------------------------------------------------------------- furniture / keep-outs (filled)
FURNITURE = [
    ("Bed A",            0.65, 2.75, 1.2, 3.35),
    ("Cupboard A",       3.35, 3.82, 1.2, 4.4),
    ("Cupboard G",       3.98, 4.7, 1.2, 4.4),
    ("Sofa G",           6.6, 7.3, 1.2, 3.05),
    ("C.B.",             6.75, 7.3, 3.05, 4.4),
    ("Cupboard T",       0.05, 2.25, 6.0, 6.42),
    ("Bed B",            1.16, 2.99, 7.40, 9.375),   # head on top wall, ~1 m (3.4 ft) gap each side
    ("Table B",          3.05, 3.50, 8.95, 9.375),   # bedside table, right of the bed
    ("Swing",            4.4, 5.5, 6.6, 8.1),
    ("Sofa back",        7.1, 11.1, 8.85, 9.4),
    ("Sofa arm L",       7.1, 7.8, 7.8, 9.4),
    ("Sofa arm R",       10.4, 11.1, 6.8, 9.4),
    ("Coffee table",     8.4, 9.6, 6.6, 7.5),
    ("Entrance cupboard",7.5, 8.4, 1.2, 3.3),
    ("Bench",            10.3, 11.1, 1.4, 3.0),
    ("Counter",          11.25, 11.85, 1.15, 3.6),
    ("Fridge",           11.25, 11.95, 3.6, 4.45),
    ("Counter",          11.25, 14.55, 1.15, 1.75),
    ("Counter",          13.95, 14.55, 1.15, 4.45),
    ("Mandir",           14.6, 16.4, 1.1, 4.6),
    ("Dining table",     12.1, 13.8, 5.6, 8.9),
    ("Bed C",            17.15, 20.25, 1.25, 3.0),
    ("Wall block",       14.6, 16.4, 5.5, 9.5),
    ("Cupboard T",       17.35, 20.35, 6.2, 6.7),
    ("Bed D",            17.95, 20.25, 7.15, 8.5),
    ("Table D",          19.6, 20.25, 8.65, 9.4),
]

# rooms nobody (Zippy) enters: interior stays UNKNOWN, like a real LiDAR map
CLOSED_ROOMS = [
    (0.0, 2.3, 4.5, 5.47), (0.0, 2.3, 5.47, 5.95),    # top toilets
    (17.3, 20.4, 4.45, 5.3), (17.3, 20.4, 5.3, 6.15), # bottom toilets
]

ROOM_LABELS = [
    ("Bedroom A", 2.0, 3.9), ("Guest Room", 5.6, 2.6), ("Bedroom B", 2.1, 6.95),
    ("Lobby", 3.2, 5.6), ("HALL", 6.0, 6.0), ("TV wall", 9.0, 4.9), ("Entrance", 9.3, 2.5),
    ("Kitchen", 12.9, 3.9), ("Mandir", 15.5, 2.3), ("Lobby", 15.5, 5.1),
    ("Passage", 16.85, 5.6), ("Bedroom C", 18.7, 3.7), ("Bedroom D", 17.2, 9.0),
    ("Toilets", 1.15, 5.2), ("Toilets", 18.85, 5.2),
]

# ---------------------------------------------------------------- Gazebo extras
# (0, 0) of the map / Gazebo world = Zippy's dock, where the simulated robot spawns.
# Dock: Bedroom B, bottom-left corner, left of the bed (chosen 5 Oct 2026).
ORIGIN_AT = (0.40, 7.00)   # Zippy's dock: Bedroom B, bottom-left, back to the left wall, facing +x

SILL_H = 0.01    # no sills in the flat; Zippy is designed to climb 0.5-1 cm, so test at 1 cm
INCLUDE_SILLS = True   # off for the sample robot (its casters snag); back on in Manual 0.4 for Zippy
SILLS = [        # (name, x0, x1, y0, y1)  doorway gap x wall thickness
    ("bedroom_a",  2.5, 3.26, 4.425, 4.575),
    ("guest_room", 4.8, 5.56, 4.425, 4.575),
    ("bedroom_b",  3.0, 3.76, 6.425, 6.575),
    ("kitchen",   12.4, 13.16, 4.425, 4.575),
    ("bedroom_c", 16.45, 17.21, 4.375, 4.525),
    ("bedroom_d", 16.45, 17.25, 5.975, 6.125),
]

# heights (m) of the furniture boxes in Gazebo. "wall" = built into the walls map.
def height_of(name):
    n = name.lower()
    if n.startswith("wall block"):
        return "wall"
    for key, h in [("bed", 0.50), ("cupboard", 2.0), ("c.b.", 2.0), ("sofa", 0.85),
                   ("swing", 0.60), ("coffee", 0.45), ("bench", 0.45), ("counter", 1.07),
                   ("fridge", 1.70), ("mandir", 2.0), ("dining", 0.75), ("table", 0.75)]:
        if key in n:
            return h
    return 1.0


# ================================================================ build grids
xmin, xmax = 0.0 - MARGIN, 20.4 + MARGIN
ymin, ymax = 0.0 - MARGIN, 9.5 + MARGIN
W = int(round((xmax - xmin) / RES))
H = int(round((ymax - ymin) / RES))


def px(x):
    return int(round((x - xmin) / RES))


def py(y):
    return int(round((y - ymin) / RES))


def make_grid(with_furniture):
    g = np.full((H, W), UNKNOWN, dtype=np.uint8)

    def fill(x0, x1, y0, y1, val):
        g[py(min(y0, y1)):py(max(y0, y1)), px(min(x0, x1)):px(max(x0, x1))] = val

    for f in FLOOR:
        fill(*f, FREE)
    if with_furniture:
        for r in CLOSED_ROOMS:
            fill(*r, UNKNOWN)
    for x0, x1, y0, y1, t in WALLS:
        h = t / 2
        if y0 == y1:
            fill(x0 - h, x1 + h, y0 - h, y0 + h, OCC)
        else:
            fill(x0 - h, x0 + h, y0 - h, y1 + h, OCC)
    for name, w, a, b, o in DOORS:
        h = OUTER_T / 2 + 0.01
        if o == "h":
            fill(a, b, w - h, w + h, FREE)
        else:
            fill(w - h, w + h, a, b, FREE)
    for name, x0, x1, y0, y1 in FURNITURE:
        if with_furniture or height_of(name) == "wall":
            fill(x0, x1, y0, y1, OCC)
    if not with_furniture:
        g[g == UNKNOWN] = FREE          # walls-only image: just black on white
    return np.flipud(g)                 # PGM row 0 must be the TOP of the map


def save(img, stem):
    with open(f"{stem}.pgm", "wb") as f:
        f.write(f"P5\n# Zippy flat map, {RES} m/px\n{W} {H}\n255\n".encode())
        f.write(img.tobytes())
    ox, oy = round(xmin - ORIGIN_AT[0], 3), round(ymin - ORIGIN_AT[1], 3)
    with open(f"{stem}.yaml", "w") as f:
        f.write(f"image: {stem}.pgm\nmode: trinary\nresolution: {RES}\n"
                f"origin: [{ox}, {oy}, 0.0]\nnegate: 0\n"
                "occupied_thresh: 0.65\nfree_thresh: 0.25\n")


img = make_grid(True)
save(img, "home")                       # navigation map (walls + furniture)
save(make_grid(False), "home_walls")    # world_creator input (walls only)

# ---------------------------------------------------------------- SDF boxes
def box(name, x0, x1, y0, y1, hgt, rgb):
    cx, cy = (x0 + x1) / 2 - ORIGIN_AT[0], (y0 + y1) / 2 - ORIGIN_AT[1]
    sx, sy = abs(x1 - x0), abs(y1 - y0)
    size = f"{sx:.3f} {sy:.3f} {hgt:.3f}"
    return (f'    <model name="zippy_{name}">\n'
            f'      <static>true</static>\n'
            f'      <pose>{cx:.3f} {cy:.3f} {hgt / 2:.4f} 0 0 0</pose>\n'
            f'      <link name="link">\n'
            f'        <collision name="collision"><geometry><box><size>{size}</size></box></geometry></collision>\n'
            f'        <visual name="visual"><geometry><box><size>{size}</size></box></geometry>\n'
            f'          <material><ambient>{rgb} 1</ambient><diffuse>{rgb} 1</diffuse></material></visual>\n'
            f'      </link>\n'
            f'    </model>\n')


blocks, used = [], {}
for name, x0, x1, y0, y1 in (SILLS if INCLUDE_SILLS else []):
    blocks.append(box(f"sill_{name}", x0, x1, y0, y1, SILL_H, "0.8 0.6 0.2"))
for name, x0, x1, y0, y1 in FURNITURE:
    h = height_of(name)
    if h == "wall":
        continue
    slug = name.lower().replace(".", "").replace(" ", "_")
    used[slug] = used.get(slug, 0) + 1
    if used[slug] > 1:
        slug += f"_{used[slug]}"
    rgb = "0.9 0.9 0.85" if "counter" in slug else "0.55 0.4 0.3"
    blocks.append(box(slug, x0, x1, y0, y1, h, rgb))

with open("home_furniture.txt", "w") as f:
    f.write("    <!-- Zippy: furniture at real heights (from make_zippy_map.py) -->\n")
    f.write("".join(blocks))

free_area = (img == FREE).sum() * RES * RES
print(f"map {W}x{H} px = {W*RES:.1f} x {H*RES:.1f} m, free floor {free_area:.1f} m2, "
      f"{len(blocks)} boxes in home_furniture.txt")

# ================================================================ preview (Gazebo / RViz coordinates)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OX, OY = ORIGIN_AT
    fig, ax = plt.subplots(figsize=(16, 8.5))
    ax.imshow(img, cmap="gray", vmin=0, vmax=255,
              extent=[xmin - OX, xmax - OX, ymin - OY, ymax - OY])
    for name, w, a, b, o in DOORS:
        if o == "h":
            ax.plot([a - OX, b - OX], [w - OY, w - OY], color="tab:green", lw=4)
            ax.text((a + b) / 2 - OX, w + 0.18 - OY, name, color="tab:green", ha="center", fontsize=7)
        else:
            ax.plot([w - OX, w - OX], [a - OY, b - OY], color="tab:green", lw=4)
            ax.text(w + 0.15 - OX, (a + b) / 2 - OY, name, color="tab:green", fontsize=7, va="center")
    for name, x0, x1, y0, y1 in FURNITURE:
        ax.text((x0 + x1) / 2 - OX, (y0 + y1) / 2 - OY, name, color="tab:orange", ha="center",
                va="center", fontsize=6.5, rotation=90 if (y1 - y0) > 1.8 * (x1 - x0) else 0)
    for name, x, y in ROOM_LABELS:
        ax.text(x - OX, y - OY, name, color="tab:blue", ha="center", va="center", fontsize=11,
                weight="bold", bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1))
    ax.plot([8.8 - OX, 9.8 - OX], [-OY, -OY], color="tab:red", lw=4)
    ax.text(9.3 - OX, 0.2 - OY, "Main door (closed)", color="tab:red", ha="center", fontsize=7)
    ax.plot(0, 0, marker="*", color="tab:red", ms=16)
    ax.text(0, -0.35, "(0, 0) dock", color="tab:red", ha="center", fontsize=8)
    ax.set_xticks(np.arange(np.ceil(xmin - OX), xmax - OX, 1))
    ax.set_yticks(np.arange(np.ceil(ymin - OY), ymax - OY, 1))
    ax.grid(color="tab:blue", alpha=0.15)
    ax.set_xlabel("x (m) in Gazebo / RViz")
    ax.set_ylabel("y (m)")
    ax.set_title(f"Zippy flat map v4 - green = doors, orange = furniture, grey = unknown, "
                 f"{free_area:.0f} m² free floor")
    fig.tight_layout()
    fig.savefig("home_preview.png", dpi=110)
except ImportError:
    print("matplotlib not installed - skipped preview")
