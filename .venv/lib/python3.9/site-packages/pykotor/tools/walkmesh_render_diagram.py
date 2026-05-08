"""Produce qualitative text validation diagrams for a BWM (no matplotlib).

Used by the CLI when --render-png is requested but matplotlib is not installed,
and by MCP for agent context. Format: perimeter outline with line-drawing (- | +),
transition IDs in small rectangles, optional ANSI color. Focus on borders and
numbered transitions. Distinct from the BWM ASCII file format (.wok.ascii).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykotor.resource.formats.bwm.bwm_data import BWM, BWMEdge, BWMFace

# Format version for detection; first line of file must match this.
BWM_VALIDATION_DIAGRAM_MAGIC = "# BWM validation diagram 1.0"

# Grid size for outline + transition boxes
DEFAULT_WIDTH = 78
DEFAULT_HEIGHT = 38
# Max grid size; for 1000+ faces we scale up for an accurate boundary
MAX_WIDTH = 400
MAX_HEIGHT = 240

# ANSI (16-color) by role
ANSI_RESET = "\033[0m"
ANSI_PERIMETER = "\033[36m"  # cyan
ANSI_TRANSITION_BOX = "\033[91m"  # red
ANSI_TRANSITION_ID = "\033[93m"  # yellow
ANSI_ARROW_STEM = "\033[32m"  # green
ANSI_ARROW_HEAD = "\033[1;31m"  # bold red
ANSI_ERROR_MARKER = "\033[1;35m"  # bold magenta for "X marks the spot"
# Legacy aliases
ANSI_WALKABLE = "\033[34m"
ANSI_UNWALKABLE = "\033[90m"
ANSI_BORDER = ANSI_PERIMETER
ANSI_BOX = ANSI_TRANSITION_BOX
ANSI_ID = ANSI_TRANSITION_ID


def _signed_area_xy(loop: list[tuple[float, float]]) -> float:
    """Shoelace formula: signed area of a closed polygon in the XY plane. Positive = CCW (outer)."""
    if len(loop) < 3:
        return 0.0
    area = 0.0
    for i in range(len(loop)):
        j = (i + 1) % len(loop)
        area += loop[i][0] * loop[j][1] - loop[j][0] * loop[i][1]
    return area * 0.5


def _bresenham(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> list[tuple[int, int, str]]:
    """Rasterize line from (x0,y0) to (x1,y1). Returns list of (c, r, char): '-' horizontal, '|' vertical, '+' corner."""
    out: list[tuple[int, int, str]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    prev_x, prev_y = x0, y0
    while True:
        if prev_x != x and prev_y != y:
            ch = "+"
        elif prev_x != x:
            ch = "-"
        else:
            ch = "|"
        out.append((x, y, ch))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            prev_x, prev_y = x, y
            x += sx
        if e2 < dx:
            err += dx
            prev_x, prev_y = x, y
            y += sy
    return out


def render_bwm_validation_diagram_lines(
    bwm: BWM,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    use_color: bool = True,
    error_positions: list[tuple[float, float]] | None = None,
) -> list[str]:
    """Produce text validation diagram: outer perimeter, transition boxes, optional error markers.

    Draws the walkmesh outer perimeter (and any hole boundaries) as closed polygons
    using - | +, places each transition in a small rectangle with its number, and
    draws "X" at any error_positions (world XY) so the user can locate issues.
    Distinct from the BWM ASCII file format (.wok.ascii).

    Args:
    ----
        bwm: Rebuilt BWM in memory.
        width: Character width of the drawing area (inside frame).
        height: Character height of the drawing area.
        use_color: If True, embed ANSI color codes.
        error_positions: Optional list of (x, y) world positions to mark with "X" (e.g. validation failures).

    Returns:
    -------
        List of lines (one string per line).
    """
    bbmin, bbmax = bwm.box()
    span_x = bbmax.x - bbmin.x
    span_y = bbmax.y - bbmin.y
    if span_x < 1e-9:
        span_x = 1.0
    if span_y < 1e-9:
        span_y = 1.0

    n_verts: int = len(bwm.vertices())
    walkable: list[BWMFace] = bwm.walkable_faces()
    unwalkable: list[BWMFace] = bwm.unwalkable_faces()
    n_walk: int = len(walkable)
    n_unwalk: int = len(unwalkable)
    edges: list[BWMEdge] = bwm.edges()
    n_perim = len(edges)
    trans_edges = [(i, e) for i, e in enumerate(edges) if e.transition >= 0]
    n_trans = len(trans_edges)

    # Use higher resolution for large walkmeshes so the perimeter boundary is drawn accurately
    if n_walk >= 1000 or n_perim >= 400:
        scale = min(2.0, 1.0 + (n_perim / 400) * 0.5)
        width = min(MAX_WIDTH, max(width, int(width * scale)))
        height = min(MAX_HEIGHT, max(height, int(height * scale)))

    def to_col(x: float) -> int:
        c = int(round((x - bbmin.x) / span_x * (width - 1)))
        return max(0, min(width - 1, c))

    def to_row(y: float) -> int:
        # Y up in game -> row 0 at top
        r = int(round((bbmax.y - y) / span_y * (height - 1)))
        return max(0, min(height - 1, r))

    # One closed polygon per loop (final=True marks end of each loop)
    loops: list[list[tuple[float, float]]] = []
    current_loop: list[tuple[float, float]] = []
    for edge in edges:
        a, b = bwm._edge_endpoints(edge.face, edge.index)
        current_loop.append((a.x, a.y))
        if edge.final:
            current_loop.append((b.x, b.y))
            loops.append(current_loop)
            current_loop = []
    if current_loop:
        _, b = bwm._edge_endpoints(edges[-1].face, edges[-1].index)
        current_loop.append((b.x, b.y))
        loops.append(current_loop)

    # Outer = loop with largest absolute area (CCW = positive); rest are holes. Sort so outer is first.
    loops_with_area: list[tuple[list[tuple[float, float]], float]] = [
        (loop, _signed_area_xy(loop)) for loop in loops
    ]
    loops_with_area.sort(key=lambda la: -abs(la[1]))
    loops = [loop for loop, _ in loops_with_area]
    outer_loop = loops[0] if loops else []
    n_outer_verts = len(outer_loop)
    n_outer_edges = n_outer_verts  # closed polygon: one edge per vertex
    n_hole_loops = max(0, len(loops) - 1)
    n_hole_edges = sum(len(loop) for loop in loops[1:]) if len(loops) > 1 else 0

    # Grid and color role (for ANSI)
    grid: list[list[str]] = [[" "] * width for _ in range(height)]
    color_role: list[list[str | None]] = [[None] * width for _ in range(height)]

    # Rasterize each loop only (no segment from one loop to the next); outer first, then holes
    for loop in loops:
        n_pts = len(loop)
        for i in range(n_pts):
            x0, y0 = loop[i][0], loop[i][1]
            x1, y1 = loop[(i + 1) % n_pts][0], loop[(i + 1) % n_pts][1]
            c0, r0 = to_col(x0), to_row(y0)
            c1, r1 = to_col(x1), to_row(y1)
            for c, r, ch in _bresenham(c0, r0, c1, r1):
                if 0 <= r < height and 0 <= c < width:
                    if grid[r][c] == " " or ch == "+":
                        grid[r][c] = ch
                        color_role[r][c] = "perimeter"

    # Transition boxes: 5 wide x 3 tall, ID centered; set color roles
    def draw_box(center_c: int, center_r: int, tid: int) -> None:
        tid_str = str(tid)
        if len(tid_str) > 2:
            tid_str = tid_str[:2]
        r0 = center_r - 1
        c0 = center_c - 2
        if r0 < 0 or r0 + 3 > height or c0 < 0 or c0 + 5 > width:
            return
        grid[r0][c0 : c0 + 5] = ["+", "-", "-", "-", "+"]
        for j in range(5):
            color_role[r0][c0 + j] = "transition_box"
        grid[r0 + 1][c0] = "|"
        color_role[r0 + 1][c0] = "transition_box"
        id_line = tid_str.center(3)[:3]
        for j, ch in enumerate(id_line):
            grid[r0 + 1][c0 + 1 + j] = ch
            color_role[r0 + 1][c0 + 1 + j] = (
                "transition_id" if ch in "0123456789" else "transition_box"
            )
        grid[r0 + 1][c0 + 4] = "|"
        color_role[r0 + 1][c0 + 4] = "transition_box"
        grid[r0 + 2][c0 : c0 + 5] = ["+", "-", "-", "-", "+"]
        for j in range(5):
            color_role[r0 + 2][c0 + j] = "transition_box"

    for trans_num, (_, edge) in enumerate(trans_edges, start=1):
        mid, _ = type(bwm).edge_inward_direction_xy(edge.face, edge.index)
        cc, rr = to_col(mid.x), to_row(mid.y)
        draw_box(cc, rr, trans_num)

    # Arrows at each transition: stem + head, offset one cell inward
    for _, edge in trans_edges:
        mid, direction = type(bwm).edge_inward_direction_xy(edge.face, edge.index)
        dx, dy = direction.x, direction.y
        cc = to_col(mid.x)
        rr = to_row(mid.y)
        # One cell inward so arrow is visible inside boundary
        if abs(dx) >= abs(dy):
            cc += 1 if dx > 0 else -1 if dx < 0 else 0
        else:
            rr += -1 if dy > 0 else 1 if dy < 0 else 0
        # Clamp for grid
        cc = max(0, min(width - 1, cc))
        rr = max(0, min(height - 1, rr))
        # Choose direction: left <, right >, up ^, down v
        if abs(dx) >= abs(dy):
            if dx > 0:  # inward right: stem left, head right
                stem_c, head_c = cc - 1, cc
                if 0 <= stem_c < width and 0 <= rr < height:
                    grid[rr][stem_c] = "-"
                    color_role[rr][stem_c] = "arrow_stem"
                if 0 <= head_c < width:
                    grid[rr][head_c] = ">"
                    color_role[rr][head_c] = "arrow_head"
            else:  # inward left: stem right, head left
                head_c, stem_c = cc, cc + 1
                if 0 <= head_c < width and 0 <= rr < height:
                    grid[rr][head_c] = "<"
                    color_role[rr][head_c] = "arrow_head"
                if 0 <= stem_c < width and 0 <= rr < height:
                    grid[rr][stem_c] = "-"
                    color_role[rr][stem_c] = "arrow_stem"
        elif dy > 0:  # inward up (smaller row): head above stem
            head_r, stem_r = rr, rr + 1
            if 0 <= head_r < height and 0 <= cc < width:
                grid[head_r][cc] = "^"
                color_role[head_r][cc] = "arrow_head"
            if 0 <= stem_r < height and 0 <= cc < width:
                grid[stem_r][cc] = "|"
                color_role[stem_r][cc] = "arrow_stem"
        else:  # inward down: stem above head
            stem_r, head_r = rr - 1, rr
            if 0 <= stem_r < height and 0 <= cc < width:
                grid[stem_r][cc] = "|"
                color_role[stem_r][cc] = "arrow_stem"
            if 0 <= head_r < height and 0 <= cc < width:
                grid[head_r][cc] = "v"
                color_role[head_r][cc] = "arrow_head"

    # "X marks the spot": draw error markers at world positions (e.g. validation failures)
    for x, y in error_positions or []:
        c, r = to_col(x), to_row(y)
        if 0 <= r < height and 0 <= c < width:
            grid[r][c] = "X"
            color_role[r][c] = "error_marker"

    def ansi_for_role(role: str | None) -> str:
        if role == "perimeter":
            return ANSI_PERIMETER
        if role == "transition_box":
            return ANSI_TRANSITION_BOX
        if role == "transition_id":
            return ANSI_TRANSITION_ID
        if role == "arrow_stem":
            return ANSI_ARROW_STEM
        if role == "arrow_head":
            return ANSI_ARROW_HEAD
        if role == "error_marker":
            return ANSI_ERROR_MARKER
        return ""

    def row_str(r: int) -> str:
        if not use_color:
            return "".join(grid[r])
        out: list[str] = []
        prev_role: str | None = None
        for c_idx in range(width):
            ch: str = grid[r][c_idx]
            role: str | None = color_role[r][c_idx]
            code: str | None = ansi_for_role(role)
            if code and role != prev_role:
                out.append(code)
                prev_role = role
            elif not code and prev_role is not None:
                out.append(ANSI_RESET)
                prev_role = None
            out.append(ch)
        if prev_role is not None:
            out.append(ANSI_RESET)
        return "".join(out)

    lines: list[str] = []
    lines.append(BWM_VALIDATION_DIAGRAM_MAGIC)
    lines.append("")
    lines.append("--- Summary ---")
    lines.append(
        f"  Bbox (world units):  X [{bbmin.x:.1f}, {bbmax.x:.1f}]  Y [{bbmin.y:.1f}, {bbmax.y:.1f}]  Z [{bbmin.z:.1f}, {bbmax.z:.1f}]"
    )
    lines.append(f"  Vertices: {n_verts}  |  Faces: {n_walk} walkable, {n_unwalk} unwalkable")
    lines.append(
        f"  Perimeter edges: {n_perim} (boundary of walkable area)  |  Transitions: {n_trans} (door/area links)"
    )
    if loops:
        outer_line = f"  Outer perimeter: {n_outer_verts} vertices, {n_outer_edges} edges (1 loop)"
        if n_hole_loops:
            outer_line += f"; holes: {n_hole_edges} edges ({n_hole_loops} loop(s))"
        outer_line += "."
        lines.append(outer_line)
    lines.append("")
    lines.append("--- Map (top-down XY; interior is walkable) ---")
    # Legend: one line per element, with colored sample when use_color
    if use_color:
        lines.append("  Legend:")
        lines.append(
            f"    {ANSI_PERIMETER}-|+{ANSI_RESET}  Perimeter — outer walkable boundary (and hole boundaries)"
        )
        lines.append(
            f"    {ANSI_TRANSITION_BOX}+---+{ANSI_RESET}  Transition box — door/area link at this edge"
        )
        lines.append(
            f"    {ANSI_TRANSITION_BOX}|{ANSI_RESET}{ANSI_TRANSITION_ID} N {ANSI_RESET}{ANSI_TRANSITION_BOX}|{ANSI_RESET}  Number = transition ID (matches LYT door index)"
        )
        lines.append(
            f"    {ANSI_ARROW_STEM}-{ANSI_RESET}{ANSI_ARROW_HEAD}>{ANSI_RESET}  Arrow: stem then head; points inward (into walkable area)"
        )
        if error_positions:
            lines.append(f"    {ANSI_ERROR_MARKER}X{ANSI_RESET}  Error location (X marks the spot)")
        lines.append("")
    else:
        leg = "  Legend: -|+ perimeter  +---+ transition box  |N| transition ID  -> arrow inward"
        if error_positions:
            leg += "  X = error location"
        lines.append(leg)
        lines.append("")
    lines.append("  +" + "-" * width + "+")
    for r in range(height):
        lines.append("  |" + row_str(r) + "|")
    lines.append("  +" + "-" * width + "+")
    lines.append("")
    lines.append("--- Transitions (door/area links) ---")
    if trans_edges:
        lines.append("  ID   Position (X, Y)     Inward direction (into walkable area)")
        for trans_num, (_, edge) in enumerate(trans_edges, start=1):
            mid, direction = type(bwm).edge_inward_direction_xy(edge.face, edge.index)
            dx, dy = direction.x, direction.y
            ch = (
                "^"
                if (abs(dy) >= abs(dx) and dy > 0)
                else "v"
                if (abs(dy) >= abs(dx))
                else ">"
                if dx > 0
                else "<"
            )
            lines.append(f"  [{trans_num:2}]  ({mid.x:6.1f}, {mid.y:6.1f})   {ch}")
        lines.append("  All on perimeter; arrows point inward.")
    else:
        lines.append("  None (no door/area links on this walkmesh).")
    lines.append("")
    return lines
