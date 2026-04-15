# event_voxel_visualization.py
# ------------------------------------------------------------
# Voxel-grid creation + 3D plotting utilities for event cameras
# (x, y, t, p) -> voxel -> scatter plot in (x, time_bin, y)
# ------------------------------------------------------------

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D


class EventVoxelVisualization:
    """
    This class matches your GUI callback signature:
        plot_func(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None)

    It:
      1) filters events inside [t_start, t_start + t_duration]
      2) builds a voxel grid (2, B, H, W) (neg,pos) by default
      3) plots:
         - positive only
         - negative only
         - total (no differentiation)
         - both (differentiated)
    """

    # --------------------------
    # Configuration (edit these)
    # --------------------------
    DEFAULT_BINS = 20                 # number of time bins in voxel
    DEFAULT_TIME_INTERP = True        # linear interpolation over time bins
    DEFAULT_THRESHOLD = 0.0           # plot only voxels > threshold
    DEFAULT_MARKER_SIZE = 1           # scatter marker size
    P_POS_VALUE = 1                   # your convention: p=1 positive, p=0 negative

    @staticmethod
    def _infer_hw(x_values: np.ndarray, y_values: np.ndarray) -> tuple[int, int]:
        """
        Infer sensor width/height from data.
        If your app has fixed sensor size, replace this with constants.
        """
        if x_values.size == 0 or y_values.size == 0:
            return 0, 0
        W = int(np.max(x_values)) + 1
        H = int(np.max(y_values)) + 1
        return H, W

    # ==========================================================
    # Voxelization
    # ==========================================================
    @staticmethod
    def events_to_voxel_grid(
        x_values: np.ndarray,
        y_values: np.ndarray,
        t_values: np.ndarray,
        p_values: np.ndarray,
        t_start: float,
        t_duration: float,
        H: int,
        W: int,
        B: int = DEFAULT_BINS,
        time_interpolation: bool = DEFAULT_TIME_INTERP,
        p_positive_value: int = P_POS_VALUE,
    ) -> np.ndarray:
        """
        Returns voxel of shape (2, B, H, W):
            voxel[0] = negative channel
            voxel[1] = positive channel
        """
        if t_duration <= 0:
            raise ValueError("t_duration must be > 0")

        t0 = float(t_start)
        t1 = float(t_start + t_duration)

        # window mask
        mask = (t_values >= t0) & (t_values <= t1)

        x = x_values[mask].astype(np.int64)
        y = y_values[mask].astype(np.int64)
        t = t_values[mask].astype(np.float64)
        p = p_values[mask]

        # bounds check
        valid = (x >= 0) & (x < W) & (y >= 0) & (y < H)
        x, y, t, p = x[valid], y[valid], t[valid], p[valid]

        voxel = np.zeros((2, B, H, W), dtype=np.float32)

        if x.size == 0:
            return voxel  # nothing to add

        # normalize time to [0, B-1]
        tau = (t - t0) / float(t_duration) * (B - 1)

        # polarity channel: 1=pos, 0=neg
        c = (p == p_positive_value).astype(np.int64)

        if time_interpolation:
            b0 = np.floor(tau).astype(np.int64)
            d = (tau - b0).astype(np.float32)

            b0 = np.clip(b0, 0, B - 1)
            b1 = np.clip(b0 + 1, 0, B - 1)

            w0 = 1.0 - d
            w1 = d

            np.add.at(voxel, (c, b0, y, x), w0)
            np.add.at(voxel, (c, b1, y, x), w1)
        else:
            b = np.rint(tau).astype(np.int64)
            b = np.clip(b, 0, B - 1)
            np.add.at(voxel, (c, b, y, x), 1.0)

        return voxel

    # ==========================================================
    # Point extraction helpers (voxel -> scatter points)
    # ==========================================================
    @staticmethod
    def _points_from_channel(channel_bhw: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        channel_bhw: (B,H,W)
        returns x, tbin, y arrays for voxels > threshold
        """
        tb, yy, xx = np.where(channel_bhw > threshold)
        return xx, tb, yy

    @staticmethod
    def _voxel_from_events(
        x_values: np.ndarray,
        y_values: np.ndarray,
        t_values: np.ndarray,
        p_values: np.ndarray,
        t_start: float,
        t_duration: float,
        B: int,
        time_interpolation: bool,
    ) -> np.ndarray:
        """
        Convenience wrapper: infer H/W, create voxel.
        """
        H, W = EventVoxelVisualization._infer_hw(x_values, y_values)
        if H <= 0 or W <= 0:
            # return empty voxel with minimal size to avoid crashes
            return np.zeros((2, B, 1, 1), dtype=np.float32)
        return EventVoxelVisualization.events_to_voxel_grid(
            x_values=x_values,
            y_values=y_values,
            t_values=t_values,
            p_values=p_values,
            t_start=t_start,
            t_duration=t_duration,
            H=H,
            W=W,
            B=B,
            time_interpolation=time_interpolation,
            p_positive_value=EventVoxelVisualization.P_POS_VALUE,
        )

    # ==========================================================
    # Plotting API expected by your GUI
    # ==========================================================
    @staticmethod
    def plot_positive_event_voxel(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot of POSITIVE voxels (red)."""
        EventVoxelVisualization._plot_voxel(
            x_values, y_values, t_values, p_values,
            t_start, t_duration,
            mode="positive",
            ax=ax
        )

    @staticmethod
    def plot_negative_event_voxel(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot of NEGATIVE voxels (blue)."""
        EventVoxelVisualization._plot_voxel(
            x_values, y_values, t_values, p_values,
            t_start, t_duration,
            mode="negative",
            ax=ax
        )

    @staticmethod
    def plot_total_event_voxel(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot of TOTAL voxels (no polarity distinction; grey)."""
        EventVoxelVisualization._plot_voxel(
            x_values, y_values, t_values, p_values,
            t_start, t_duration,
            mode="total",
            ax=ax
        )

    @staticmethod
    def plot_both_events_voxel(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot of both polarities differentiated (neg=blue, pos=red)."""
        EventVoxelVisualization._plot_voxel(
            x_values, y_values, t_values, p_values,
            t_start, t_duration,
            mode="both",
            ax=ax
        )

    # ==========================================================
    # Internal plotting core
    # ==========================================================
    @staticmethod
    def _plot_voxel(
        x_values: np.ndarray,
        y_values: np.ndarray,
        t_values: np.ndarray,
        p_values: np.ndarray,
        t_start: float,
        t_duration: float,
        mode: str,
        ax=None,
        B: int | None = None,
        threshold: float | None = None,
        marker_size: float | None = None,
        time_interpolation: bool | None = None,
    ):
        """
        mode in {"positive","negative","total","both"}
        Scatter axes: (x, time_bin, y) to match your event plots (x, t, y).
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")

        if B is None:
            B = EventVoxelVisualization.DEFAULT_BINS
        if threshold is None:
            threshold = EventVoxelVisualization.DEFAULT_THRESHOLD
        if marker_size is None:
            marker_size = EventVoxelVisualization.DEFAULT_MARKER_SIZE
        if time_interpolation is None:
            time_interpolation = EventVoxelVisualization.DEFAULT_TIME_INTERP

        voxel = EventVoxelVisualization._voxel_from_events(
            x_values, y_values, t_values, p_values,
            t_start, t_duration,
            B=B,
            time_interpolation=time_interpolation,
        )

        ax.clear()

        neg = voxel[0]  # (B,H,W)
        pos = voxel[1]  # (B,H,W)

        if mode == "positive":
            x, tb, y = EventVoxelVisualization._points_from_channel(pos, threshold)
            ax.scatter(x, tb, y, color="red", s=marker_size)
            ax.set_title("Positive Voxel Visualization (p = 1)")
            ax.invert_zaxis()  # Invert z-axis to match typical image coordinates

        elif mode == "negative":
            x, tb, y = EventVoxelVisualization._points_from_channel(neg, threshold)
            ax.scatter(x, tb, y, color="blue", s=marker_size)
            ax.set_title("Negative Voxel Visualization (p = 0)")
            ax.invert_zaxis()  # Invert z-axis to match typical image coordinates

        elif mode == "total":
            total = neg + pos
            x, tb, y = EventVoxelVisualization._points_from_channel(total, threshold)
            ax.scatter(x, tb, y, color="grey", s=marker_size)
            ax.set_title("Total Voxel Visualization (no differentiation)")
            ax.invert_zaxis()  # Invert z-axis to match typical image coordinates

        elif mode == "both":
            xn, tbn, yn = EventVoxelVisualization._points_from_channel(neg, threshold)
            xp, tbp, yp = EventVoxelVisualization._points_from_channel(pos, threshold)

            if xn.size:
                ax.scatter(xn, tbn, yn, color="blue", s=marker_size)
            if xp.size:
                ax.scatter(xp, tbp, yp, color="red", s=marker_size)

            ax.invert_zaxis()  # Invert z-axis to match typical image coordinates
            ax.set_title("Positive & Negative Voxel Visualization")

            legend_elements = [
                Line2D([0], [0], marker='o', color='w', label='Negative',
                       markerfacecolor='blue', markersize=8),
                Line2D([0], [0], marker='o', color='w', label='Positive',
                       markerfacecolor='red', markersize=8),
            ]
            ax.legend(handles=legend_elements,
                loc="upper right",
                bbox_to_anchor=(1, 0.95))  # move slightly down

        else:
            raise ValueError(f"Unknown mode: {mode}")

        ax.set_xlabel("X")
        ax.set_ylabel("Time bin")
        ax.set_zlabel("Y")