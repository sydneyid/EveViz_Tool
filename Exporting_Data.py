import tkinter as tk
from tkinter import filedialog
import os
import h5py
import numpy as np
import shutil, subprocess, uuid
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from GUI_helper import truncate_message
from Loading_Data import LoadingData


class ExportingData:

    @staticmethod
    def save_plot(frame_win, fig, time_status, state, source=""):
        """
        Save a plot with a unique filename depending on the source window.
        source: 'frame', '3d', or 'voxel'
        """
        if state.filename:
            original_name = os.path.splitext(os.path.basename(state.filename))[0]
        else:
            original_name = "plot"
        applied_filters = []
        if state.hot_pixel_filter_applied:
            applied_filters.append("HP")
        if state.voxel_activity_filter_applied:
            applied_filters.append("VA")
        # (Neighbor Activity Filter removed)
        if state.density_filter_applied:
            applied_filters.append("VD")
        if state.median_filter_applied:
            applied_filters.append("ME")
        filters_str = "cleaned_" + "_".join(applied_filters) if applied_filters else "no_filters"
        
        if state.start_time_us is not None and state.duration_us is not None:
            end_time = state.start_time_us + state.duration_us
            start_ms = int(state.start_time_us / 1000)
            end_ms = int(end_time / 1000)
            time_range = f"{start_ms}ms_{end_ms}ms"
        else:
            time_range = "0ms_0ms"
     
        initialfile = f"{original_name}_{source}_{filters_str}_time_range_{time_range}.png"
        fpath = filedialog.asksaveasfilename(
            parent=frame_win,
            defaultextension='.png',
            filetypes=[('PNG image', '*.png'), ('JPEG image', '*.jpg'), ('PDF document', '*.pdf')],
            initialfile=initialfile
        )
        if not fpath:
            return
        try:
            fig.savefig(fpath, dpi=200)
            time_status.config(text=f"Saved plot to: {fpath}", fg="green")
        except Exception as e:
            time_status.config(text=f"Save failed: {e}", fg="red")

    @staticmethod
    def save_screenshot(frame_win, fig, timestamp_us, time_status, state):
        # Construct default filename based on naming convention
        if state.filename:
            original_name = os.path.splitext(os.path.basename(state.filename))[0]
        else:
            original_name = "screenshot"
        
        applied_filters = []
        if state.hot_pixel_filter_applied:
            applied_filters.append("HP")
        if state.voxel_activity_filter_applied:
            applied_filters.append("VA")
        # (Neighbor Activity Filter removed)
        if state.density_filter_applied:
            applied_filters.append("VD")
        if state.median_filter_applied:
            applied_filters.append("ME")
        filters_str = "cleaned_" + "_".join(applied_filters) if applied_filters else "no_filters"
        
        timestamp_ms = int(timestamp_us / 1000) if timestamp_us is not None else 0
        timestamp = f"{timestamp_ms}ms"
        
        initialfile = f"{original_name}_video_{filters_str}_timestamp_{timestamp}.png"
        
        # Ask for filename
        fpath = filedialog.asksaveasfilename(
            parent=frame_win,
            defaultextension='.png',
            filetypes=[('PNG image', '*.png'), ('JPEG image', '*.jpg'), ('PDF document', '*.pdf')],
            initialfile=initialfile
        )
        if not fpath:
            return
        try:
            fig.savefig(fpath, dpi=200)
            time_status.config(text=f"Saved screenshot to: {fpath}", fg="green")
        except Exception as e:
            time_status.config(text=f"Save failed: {e}", fg="red")

    @staticmethod
    def save_video(parent_window, fig,
        x,
        y,
        t,
        p,
        max_x,
        max_y,
        export_status,
        state=None,
        fps=30,
        persistence_us=None,
        cumulative=False,
        mode="both",
        marker_size=5,
    ):
        """
        Save FULL filtered recording as MP4 using ffmpeg (via Matplotlib),
        optimized to avoid O(n_frames * n_events) masking.

        IMPORTANT: Video duration is preserved exactly via:
        n_frames = ceil((t1 - t0) / dt) + 1, dt = 1e6/fps
        """

        # Construct default filename based on naming convention
        if state and state.filename:
            original_name = os.path.splitext(os.path.basename(state.filename))[0]
        else:
            original_name = "video"

        applied_filters = []
        if state:
            if state.hot_pixel_filter_applied:
                applied_filters.append("HP")
            if state.voxel_activity_filter_applied:
                applied_filters.append("VA")
            if state.density_filter_applied:
                applied_filters.append("VD")
            if state.median_filter_applied:
                applied_filters.append("ME")
        filters_str = "cleaned_" + "_".join(applied_filters) if applied_filters else "no_filters"

        initialfile = f"{original_name}_video_{filters_str}.mp4"

        # --- Ask for output file ---
        out_path = filedialog.asksaveasfilename(
            parent=parent_window,
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")],
            title="Save video as MP4",
            initialfile=initialfile,
        )
        if not out_path:
            return  # user cancelled

        # --- Load data ---
        x = np.asarray(x)
        y = np.asarray(y)
        t = np.asarray(t)
        p = np.asarray(p)

        if x.size == 0 or t.size == 0:
            export_status.config(text=truncate_message("Error: No events to save"), fg="red")
            return

        # --- Sort by time (required for searchsorted slicing) ---
        order = np.argsort(t, kind="quicksort")
        x = x[order]
        y = y[order]
        t = t[order]
        p = p[order]

        # --- Timing / frames (duration preserved) ---
        t0 = float(t[0])
        t1 = float(t[-1])

        dt = 1e6 / float(fps)  # microseconds per frame
        if dt <= 0:
            export_status.config(text=truncate_message("Error: Invalid fps"), fg="red")
            return

        # ceil to avoid shortening the video (no time compression)
        span = max(0.0, t1 - t0)
        n_frames = int(np.ceil(span / dt)) + 1
        if n_frames <= 0:
            export_status.config(text=truncate_message("Error: Invalid frame count/time range"), fg="red")
            return

        if persistence_us is None:
            persistence_us = dt
        else:
            persistence_us = float(persistence_us)

        # --- Precompute frame timestamps and index windows ---
        frame_times = t0 + np.arange(n_frames, dtype=np.float64) * dt
        # clamp last time to t1 for nicer display (does NOT change frame count)
        frame_times[-1] = min(frame_times[-1], t1)

        # right edge: events with t <= cur_t
        rights = np.searchsorted(t, frame_times, side="right")

        if cumulative:
            lefts = np.zeros_like(rights)
        else:
            # left edge: events with t > cur_t - persistence_us  (strictly greater)
            left_times = frame_times - persistence_us
            lefts = np.searchsorted(t, left_times, side="right")

        # --- New figure for export (don't reuse GUI fig) ---
        fig_out = Figure()
        FigureCanvasAgg(fig_out)  # Attach canvas for rendering
        ax = fig_out.add_subplot(111)

        if max_x is not None and max_y is not None:
            ax.set_xlim(0, max_x)
            ax.set_ylim(0, max_y)
        else:
            ax.set_xlim(float(x.min()), float(x.max())+1)
            ax.set_ylim(float(y.min()), float(y.max())+1)

        # Optional: keep sensor aspect ratio
        ax.set_aspect("equal", adjustable="box")
        ax.invert_yaxis()  # Invert y-axis to match typical event camera coordinate system
        ax.set_xlabel("x")
        ax.set_ylabel("y")

        # --- Single scatter plot matching animate_frame_video logic ---
        sc = ax.scatter([], [], s=marker_size, marker="o", facecolors=np.zeros((0, 4)), edgecolors="none")

        # Lightweight timestamp text instead of ax.set_title (less layout work)
        # ts_text = ax.text(0.5, 0.98, "", transform=ax.transAxes, va="top", ha="center")

        EMPTY = np.empty((0, 2), dtype=np.float32)

        def update(i):
            l = int(lefts[i])
            r = int(rights[i])

            if r <= l:
                sc.set_offsets(EMPTY)
                ax.set_title(f"{(frame_times[i] - t0)/1e3:.2f} ms")
                return (sc,)

            xf = x[l:r]
            yf = y[l:r]
            pf = p[l:r]

            # Build colors matching animate_frame_video logic
            alpha = 0.9
            if mode == "positive":
                sel = pf > 0
                xf, yf = xf[sel], yf[sel]
                colors = np.tile([1, 0, 0, alpha], (len(xf), 1))
            elif mode == "negative":
                sel = pf <= 0
                xf, yf = xf[sel], yf[sel]
                colors = np.tile([0, 0, 1, alpha], (len(xf), 1))
            elif mode == "all":
                colors = np.tile([0.5, 0.5, 0.5, alpha], (len(xf), 1))
            else:  # "both"
                colors = np.zeros((len(xf), 4))
                pos = pf > 0
                colors[pos] = [1, 0, 0, alpha]
                colors[~pos] = [0, 0, 1, alpha]

            # Set offsets and colors
            if xf.size > 0:
                sc.set_offsets(np.column_stack((xf, yf)))
                sc.set_facecolors(colors)
            else:
                sc.set_offsets(EMPTY)

            ax.set_title(f"{(frame_times[i] - t0)/1e3:.2f} ms")
            return (sc,)

        # --- Build animation ---
        # blit=True is usually faster; if it causes issues on your system, set to False.
        ani = animation.FuncAnimation(
            fig_out,
            update,
            frames=n_frames,
            blit=False,
            interval=1000.0 / float(fps),  # does not affect saved video timing, but keeps it consistent
        )

        # --- Save using ffmpeg (fast preset; duration preserved by fps + n_frames) ---
        try:
            writer = animation.FFMpegWriter(
                fps=fps,
                codec="libx264",
                extra_args=[
                    "-pix_fmt",
                    "yuv420p",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "23",
                    "-movflags",
                    "+faststart",
                ],
            )

            export_status.config(text=truncate_message("Saving video..."), fg="orange")
            ani.save(out_path, writer=writer, dpi=150)
            export_status.config(text=truncate_message(f"Video sucessfully saved to: {out_path}"), fg="green")

        except Exception as e:
            export_status.config(text=truncate_message(f"Error saving video: {str(e)}"), fg="red")

        finally:
            fig_out.clear()

    
    @staticmethod
    def export_report(state, parent=None):
        """Export a report file with event and filter statistics from AppState. Prompts for save location."""

        if not state.filename:
            return False, "No file loaded."
        default_name = f"EV_{os.path.splitext(state.filename)[0]}.out"
        fpath = filedialog.asksaveasfilename(
            parent=parent,
            defaultextension='.out',
            filetypes=[('Report file', '*.out'), ('Text file', '*.txt'), ('All files', '*.*')],
            initialfile=default_name
        )
        if not fpath:
            return False, None

        # Camera type detection
        cam_types = {
            (128, 128): "DVS128",
            (240, 180): "DAVIS240",
            (346, 260): "DAVIS346",
            (640, 480): "DAVIS640",
            (1280, 720): "Prophesee Gen4"
        }
        cam_type = cam_types.get((state.max_x + 1, state.max_y + 1), None)
        # Special case for Prophesee Gen3
        if (state.max_x, state.max_y) == (640, 480) and getattr(state, 'is_pure_event', False):
            cam_type = "Prophesee Gen3"
        if not cam_type:
            cam_type = "Unknown"

        try:
            with open(fpath, 'w') as f:
                f.write(f"EVENT VISUALIZATION REPORT\n")
                f.write(f"\nFilename: {state.filename}\n")
                f.write(f"Camera Frame: {state.max_x + 1} x {state.max_y + 1}\n")
                f.write(f"Camera Type: \"{cam_type}\" (Based on frame dimensions)\n")
                f.write(f"Recording Length: {state.min_t} - {state.max_t} microseconds\n")
                f.write(f"\n--- Raw Event Counts ---\n")
                f.write(f"Total Events: {state.raw_total_events}\n")
                f.write(f"  Positive Events: {state.raw_positive_events}\n")
                f.write(f"  Negative Events: {state.raw_negative_events}\n")
                f.write(f"\n--- Filters Applied ---\n")
                if state.hot_pixel_filter_applied:
                    f.write(f"Hot Pixel Filter: Removed {state.hot_pixel_removed} events ({state.hot_pixel_percentage:.2f}%) | Candidate threshold (percentile {state.hot_pixel_threshold}): {state.hot_pixel_threshold_display} | Validated hot pixels: {state.hot_pixel_validated}\n")
                if state.voxel_activity_filter_applied:
                    f.write(f"Voxel Activity Filter: Removed {state.voxel_activity_removed} events ({state.voxel_activity_percentage:.2f}%) | Spatial Window: {state.voxel_activity_spatial_window}, Time Window: {state.voxel_activity_time_window}\n")
                # (Neighbor Activity Filter removed)
                if state.density_filter_applied:
                    f.write(f"Voxel Density Filter: Removed {state.density_removed} events ({state.density_percentage:.2f}%) | Percentile: {state.density_percentile}, Alpha: {state.density_alpha}\n")
                if state.median_filter_applied:
                    f.write(f"Median Filter: Removed {state.median_removed} events ({state.median_percentage:.2f}%) | Spatial Window: {state.median_spatial_window}, Time Window: {state.median_time_window}\n")
                if not (state.hot_pixel_filter_applied or state.voxel_activity_filter_applied or state.density_filter_applied or state.median_filter_applied):
                    f.write("No filters applied.\n")
                f.write(f"\nTotal Removed: {state.total_removed} events ({state.total_percentage:.2f}%) | Events Remaining: {state.raw_total_events - state.total_removed}\n")
            return True, fpath
        except Exception as e:
            return False, None

    @staticmethod
    def export_clean_data(state, parent=None):
        """
        Open a file dialog to export cleaned data as .hdf5 or .bin, using a filename that includes filter info.
        """
        if state.filename:
            original_name = os.path.splitext(os.path.basename(state.filename))[0]
        else:
            original_name = "cleaned_data"
        applied_filters = []
        if state.hot_pixel_filter_applied:
            applied_filters.append("HP")
        if state.voxel_activity_filter_applied:
            applied_filters.append("VA")
        # (Neighbor Activity Filter removed)
        if state.density_filter_applied:
            applied_filters.append("VD")
        if state.median_filter_applied:
            applied_filters.append("ME")
        filters_str = "cleaned_" + "_".join(applied_filters) if applied_filters else "no_filters"
        initialfile = f"{original_name}_{filters_str}"

        filetypes = [
            ("HDF5 file", "*.hdf5"),
            ("BIN file", "*.bin"),
            ("TXT file", "*.txt"),
            ("All files", "*.*")
        ]
        fpath = filedialog.asksaveasfilename(
            parent=parent,
            defaultextension='.hdf5',
            filetypes=filetypes,
            initialfile=initialfile
        )
        if not fpath:
            return False
        ext = os.path.splitext(fpath)[1].lower()
        if ext == ".hdf5":
            ExportingData.export_hdf5(state, fpath)
        elif ext == ".bin":
            ExportingData.export_bin(state, fpath)
        elif ext == ".txt":
            ExportingData.export_txt(state, fpath)
        else:
            ExportingData.export_hdf5(state, fpath)
        return True

    @staticmethod
    def export_hdf5(state, fpath):
         
         with h5py.File(fpath, "w") as f:
            f.create_dataset("x", data=state.x_values)
            f.create_dataset("y", data=state.y_values)
            f.create_dataset("t", data=state.t_values)
            f.create_dataset("p", data=state.p_values)


    @staticmethod
    def export_txt(state, fpath):
        """
        Export x, y, p, t as comma-separated int32 columns, no header.
        """
        arr = np.column_stack((state.x_values, state.y_values, state.p_values, state.t_values)).astype(np.int32)
        np.savetxt(fpath, arr, fmt='%d', delimiter=',')

    @staticmethod
    def export_bin(state, fpath):
        """
        Export to .bin by first exporting to .txt (in the same folder), then calling Main.exe c txtfile binfile, then deleting the txt.
        EveViz runs without this converter; export HDF5 or TXT if Main.exe is not installed.
        """

        main_exe = LoadingData.get_bin_converter_command()
        if main_exe is None:
            raise EnvironmentError(LoadingData.bin_converter_not_found_message())

        bin_dir = os.path.dirname(fpath)
        base = os.path.splitext(os.path.basename(fpath))[0]
        unique = uuid.uuid4().hex[:8]
        txt_path = os.path.join(bin_dir, f"{base}_tmp_{unique}.txt")
        try:
            ExportingData.export_txt(state, txt_path)
            try:
                result = subprocess.run(
                    [main_exe, "c", str(txt_path), str(fpath)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise EnvironmentError(
                    "BIN compression (Main.exe) was not found during export. "
                    "Export as HDF5 or TXT, or install Main.exe for .bin export."
                ) from exc
            except OSError as exc:
                raise RuntimeError(
                    f"Failed to run {LoadingData.BIN_CONVERTER_EXE}: {exc}"
                ) from exc

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                raise RuntimeError(
                    f"{LoadingData.BIN_CONVERTER_EXE} failed during .bin export"
                    + (f": {stderr}" if stderr else ".")
                )
        finally:
            if os.path.exists(txt_path):
                os.remove(txt_path)
