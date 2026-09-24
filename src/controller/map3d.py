"""Lightweight isometric path view using Tkinter's standard Canvas widget."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from ardrone.state import DroneState


@dataclass(frozen=True, slots=True)
class MapPoint:
    x_m: float
    y_m: float
    z_m: float
    yaw_deg: float


class FlightPath:
    """Estimate local XY position by integrating fresh NavData velocities."""

    def __init__(self, maximum_points: int = 400) -> None:
        if maximum_points < 2:
            raise ValueError("maximum_points must be at least 2")
        self.points: deque[MapPoint] = deque(maxlen=maximum_points)
        self._last_sequence: int | None = None
        self._last_received_at: float | None = None
        self._x_m = 0.0
        self._y_m = 0.0

    def update(self, sequence: int, received_at: float, state: DroneState) -> bool:
        """Record a fresh sample; return False when this sequence was already used."""
        if sequence == self._last_sequence:
            return False
        if self._last_received_at is not None:
            dt = received_at - self._last_received_at
            if 0.0 < dt <= 0.5:
                self._x_m += state.vx_m_s * dt
                self._y_m += state.vy_m_s * dt
        self._last_sequence = sequence
        self._last_received_at = received_at
        self.points.append(MapPoint(self._x_m, self._y_m, state.altitude_m, state.yaw_deg))
        return True


class IsometricMap:
    """A small Tk window that draws a 3D-like local grid, path and drone marker."""

    def __init__(self, title: str = "AR.Drone 2.0 — Mapa local 3D") -> None:
        try:
            import tkinter as tk
        except ImportError as exc:
            raise RuntimeError("Tkinter is not installed") from exc

        self._tk = tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            raise RuntimeError("Tk could not open a desktop window") from exc
        self.root.title(title)
        self.root.geometry("760x560")
        self.root.minsize(520, 400)
        self.canvas = tk.Canvas(self.root, background="#101923", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.closed = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.root.destroy()
        except self._tk.TclError:
            pass

    def update(self, path: FlightPath, state: DroneState | None, age: float) -> None:
        if self.closed:
            return
        try:
            self.root.update_idletasks()
            width = max(self.canvas.winfo_width(), 520)
            height = max(self.canvas.winfo_height(), 360)
            self.canvas.delete("all")
            self._draw(width, height, path, state, age)
            self.root.update()
        except self._tk.TclError:
            self.closed = True

    def _draw(
        self,
        width: int,
        height: int,
        path: FlightPath,
        state: DroneState | None,
        age: float,
    ) -> None:
        canvas = self.canvas
        points = list(path.points)
        x_values = [point.x_m for point in points] or [0.0]
        y_values = [point.y_m for point in points] or [0.0]
        z_values = [point.z_m for point in points] or [0.0]
        x_min, x_max = min(x_values) - 1.0, max(x_values) + 1.0
        y_min, y_max = min(y_values) - 1.0, max(y_values) + 1.0
        z_max = max(2.0, max(z_values) + 0.75)
        x_mid = (x_min + x_max) / 2.0
        y_mid = (y_min + y_max) / 2.0
        span_xy = max((x_max - x_min + y_max - y_min) * 0.866, 4.0)
        span_z = max(z_max + (x_max - x_min + y_max - y_min) * 0.5, 3.0)
        scale = min((width - 120) / span_xy, (height - 150) / span_z, 65.0)
        scale = max(scale, 4.0)
        center_x = width / 2.0
        floor_y = height - 62.0
        half = math.sqrt(3.0) / 2.0

        def project(x: float, y: float, z: float) -> tuple[float, float]:
            local_x, local_y = x - x_mid, y - y_mid
            return (
                center_x + (local_x - local_y) * half * scale,
                floor_y - z * scale - (local_x + local_y) * 0.5 * scale,
            )

        canvas.create_text(
            18,
            16,
            anchor="nw",
            fill="#e5edf5",
            font=("Segoe UI", 12, "bold"),
            text="TRAYECTORIA LOCAL ESTIMADA  ·  X/Y integrados desde VX/VY  ·  Z = altitud",
        )
        grid_start_x = math.floor(x_min)
        grid_end_x = math.ceil(x_max)
        grid_start_y = math.floor(y_min)
        grid_end_y = math.ceil(y_max)
        for x in range(grid_start_x, grid_end_x + 1):
            a, b = project(x, y_min, 0.0), project(x, y_max, 0.0)
            canvas.create_line(*a, *b, fill="#263746", width=1)
        for y in range(grid_start_y, grid_end_y + 1):
            a, b = project(x_min, y, 0.0), project(x_max, y, 0.0)
            canvas.create_line(*a, *b, fill="#263746", width=1)

        origin = project(x_mid, y_mid, 0.0)
        x_end = project(x_mid + 1.5, y_mid, 0.0)
        y_end = project(x_mid, y_mid + 1.5, 0.0)
        z_end = project(x_mid, y_mid, z_max)
        canvas.create_line(*origin, *x_end, fill="#ef6c63", width=2, arrow="last")
        canvas.create_line(*origin, *y_end, fill="#59c27b", width=2, arrow="last")
        canvas.create_line(*origin, *z_end, fill="#5ba8ff", width=2, arrow="last")
        canvas.create_text(x_end[0] + 10, x_end[1], fill="#ef8a83", text="X")
        canvas.create_text(y_end[0] + 10, y_end[1], fill="#78d391", text="Y")
        canvas.create_text(z_end[0], z_end[1] - 12, fill="#78b8ff", text="Z (m)")

        if len(points) > 1:
            projected = [project(point.x_m, point.y_m, point.z_m) for point in points]
            flattened = [coordinate for point in projected for coordinate in point]
            canvas.create_line(*flattened, fill="#ffd166", width=3, smooth=True)
        if points:
            current = points[-1]
            px, py = project(current.x_m, current.y_m, current.z_m)
            heading = math.radians(current.yaw_deg)
            tip = project(
                current.x_m + math.cos(heading) * 0.45,
                current.y_m + math.sin(heading) * 0.45,
                current.z_m,
            )
            canvas.create_line(px, py, *tip, fill="#ffffff", width=3, arrow="last")
            canvas.create_oval(px - 6, py - 6, px + 6, py + 6, fill="#ff8c42", outline="")

        status = state.flight_state.value if state is not None else "WAITING"
        nav_status = f"NavData {'OK' if age <= 0.5 else 'STALE'} · {age:.2f} s"
        position = (
            f"X {points[-1].x_m:+.1f} m   Y {points[-1].y_m:+.1f} m   "
            f"Z {points[-1].z_m:.1f} m"
            if points
            else "X 0.0 m   Y 0.0 m   Z 0.0 m"
        )
        canvas.create_text(
            18,
            height - 24,
            anchor="sw",
            fill="#b7c7d6",
            font=("Segoe UI", 10),
            text=f"{status}    {nav_status}    {position}    puntos: {len(points)}",
        )
