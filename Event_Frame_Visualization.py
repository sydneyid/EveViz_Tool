'''
First Draft for 2D Frame Visualization:
    Input:
        from Loading_Data: x, y, t, and p values
        from User: start time and time duration
    Output:
        2D plot
'''

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.animation as animation
from matplotlib.lines import Line2D

class EventFrameVisualization:

    @staticmethod
    def plot_positive_event(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """Plot only positive events, filtered by time. If `ax` is provided the plot
        is drawn into that axes (used for embedding in a GUI). Otherwise a new
        figure is created and shown.
        """
        mask = (t_values >= t_start) & (t_values <= t_duration + t_start) & (p_values == 1)

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        ax.clear()
        ax.scatter(x_values[mask], y_values[mask], color="red",s=1)
        ax.set_title("Positive Frame Visualization (p = 1)")
        ax.set_xlabel("X Values")
        ax.set_ylabel("Y Values")

        if ax is None:
            plt.show()

    '''
        Plot only negative events (= blue) in the given time range
    '''
    @staticmethod
    def plot_negative_event(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """Plot only negative events, filtered by time."""
        mask = (t_values >= t_start) & (t_values <= t_duration + t_start) & (p_values == 0)

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        ax.clear()
        ax.scatter(x_values[mask], y_values[mask], color="blue",s=1)
        ax.set_title("Negative Frame Visualization (p = 0)")
        ax.set_xlabel("X Values")
        ax.set_ylabel("Y Values")

        if ax is None:
            plt.show()

    '''
        Plot the total events (= all events with no distinction between positive and negative)
    '''
    @staticmethod
    def plot_total_event(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """Plot all events without distinction, filtered by time."""
        mask = (t_values >= t_start) & (t_values <= t_duration + t_start)

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        ax.clear()
        ax.scatter(x_values[mask], y_values[mask], color="grey",s=1)
        ax.set_title("Total Frame Visualization (no differentiation)")
        ax.set_xlabel("X Values")
        ax.set_ylabel("Y Values")

        if ax is None:
            plt.show()

    '''
        Plot both positive (=red) and negative (=blue) events together
    '''
    @staticmethod
    def plot_both_events(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """Plot both positive and negative events together, filtered by time."""
        mask = (t_values >= t_start) & (t_values <= t_duration + t_start)
        cmap = ListedColormap(["blue", "red"])

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        ax.clear()
        ax.scatter(x_values[mask],y_values[mask],c=p_values[mask],cmap=cmap,s=1)
        ax.set_title("Positive & Negative Frame Visualization")
        ax.set_xlabel("X Values")
        ax.set_ylabel("Y Values")

        # --- Add legend using proxy artists ---
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='Negative',
                    markerfacecolor='blue', markersize=8),
            Line2D([0], [0], marker='o', color='w', label='Positive',
                    markerfacecolor='red', markersize=8)
        ]

        ax.legend(
            handles=legend_elements,
            loc='center left',  # anchor point of legend box
            bbox_to_anchor=(0.75, 1.1),  # x = horizontal, y >1 is above plot
            bbox_transform=ax.transAxes,
            frameon=True,
            ncol=2
        )

        if ax is None:
            plt.show()

    @staticmethod
    def plot_postive_event_accumulated_frame(x_values, y_values, t_values, p_values, t_start, t_duration,image_w, image_h, ax=None):
        frame = np.ones((image_h +1, image_w+1), dtype=np.float32)
      # Create axis if none provided
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        # Create accumulation frame
        frame = np.ones((image_h + 1, image_w + 1), dtype=np.float32)

        # Select time window
        mask = (t_values >= t_start) & (t_values <= t_start + t_duration)

        x = x_values[mask]
        y = y_values[mask]
        p = p_values[mask]

        # Optional polarity filtering (positive only)
        mask2 = p > 0
        x = x[mask2]
        y = y[mask2]

        # Accumulate events
        np.add.at(frame, (image_h - y, x), 1)

        # Compute display scaling
        counts = frame[frame > 1]
        vmax = np.percentile(counts, 99.2) if counts.size else 2.0

        # Clear previous content in the axis
        ax.clear()

        # Display image
        ax.imshow(frame,
                norm=matplotlib.colors.LogNorm(vmin=1, vmax=vmax),
                cmap="magma", origin="upper")

        # Labels
        ax.set_title("Positive Accumulated Frame Visualization (p = 1)")
        ax.set_xlabel("x")
        ax.set_ylabel("y")

    @staticmethod
    def plot_negative_event_accumulated_frame(x_values, y_values, t_values, p_values, t_start, t_duration,image_w, image_h, ax=None):
        frame = np.ones((image_h + 1, image_w + 1), dtype=np.float32)
        # Create axis if none provided
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        # Create accumulation frame
        frame = np.ones((image_h + 1, image_w + 1), dtype=np.float32)

        # Select time window
        mask = (t_values >= t_start) & (t_values <= t_start + t_duration)

        x = x_values[mask]
        y = y_values[mask]
        p = p_values[mask]

        # Optional polarity filtering (positive only)
        mask2 = p == 0
        x = x[mask2]
        y = y[mask2]

        # Accumulate events
        np.add.at(frame, (image_h - y, x), 1)

        # Compute display scaling
        counts = frame[frame > 1]
        vmax = np.percentile(counts, 99.2) if counts.size else 2.0

        # Clear previous content in the axis
        ax.clear()

        # Display image
        ax.imshow(frame,
                norm=matplotlib.colors.LogNorm(vmin=1, vmax=vmax),
                cmap="magma", origin="upper")

        # Labels
        ax.set_title("Negative Accumulated Frame Visualization (p = 0)")
        ax.set_xlabel("x")
        ax.set_ylabel("y")

    @staticmethod
    def plot_both_event_accumulated_frame(x_values, y_values, t_values, p_values, t_start, t_duration,image_w, image_h, ax=None):
        frame = np.ones((image_h +1, image_w+1), dtype=np.float32)
        # Create axis if none provided
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        # Create accumulation frame
        frame = np.ones((image_h + 1, image_w + 1), dtype=np.float32)

        # Select time window
        mask = (t_values >= t_start) & (t_values <= t_start + t_duration)

        x = x_values[mask]
        y = y_values[mask]

        # Accumulate events
        np.add.at(frame, (image_h - y, x), 1)

        # Compute display scaling
        counts = frame[frame > 1]
        vmax = np.percentile(counts, 99.2) if counts.size else 2.0

        # Clear previous content in the axis
        ax.clear()

        # Display image
        ax.imshow(frame,
                norm=matplotlib.colors.LogNorm(vmin=1, vmax=vmax),
                cmap="magma", origin="upper")

        # Labels
        ax.set_title("Positive & Negative Accumulated Frame Visualization")
        ax.set_xlabel("x")
        ax.set_ylabel("y")

    @staticmethod
    def animate_frame_video(
        x_values,
        y_values,
        t_values,
        p_values=None,
        ax=None,
        fps: int = 60,
        persistence_us: float | None = None,
        cumulative: bool = False,
        marker_size: float = 5,
        mode: str = "both",
        max_x=None,
        max_y=None,
        progressbar=None,
        time_label=None,
        start_offset_us: float = 0.0,
    ):
        """
        TRUE real-time event animation (clock-driven).

        - Wall clock controls time (no drift)
        - t_values are in microseconds
        - Skips frames if rendering is slow
        - Always stays synchronized to real time
        """

        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
        import time

        # --- Load arrays ---
        xs = np.asarray(x_values)
        ys = np.asarray(y_values)
        ts = np.asarray(t_values)
        ps = np.asarray(p_values) if p_values is not None else np.zeros_like(ts)

        if xs.size == 0:
            raise ValueError("No events provided")

        # --- Sort by time ---
        order = np.argsort(ts)
        xs, ys, ts, ps = xs[order], ys[order], ts[order], ps[order]

        t_start = float(ts[0])
        t_end = float(ts[-1])
        t_duration = t_end - t_start

        # --- Figure ---
        created_fig = False
        if ax is None:
            created_fig = True
            fig, ax = plt.subplots()
        else:
            fig = ax.figure

        # --- Axis limits ---
        if max_x is not None and max_y is not None:
            ax.set_xlim(0, max_x + 1)
            ax.set_ylim(0, max_y + 1)
        else:
            x_min, x_max = xs.min(), xs.max()
            y_min, y_max = ys.min(), ys.max()
            x_pad = max(1.0, 0.02 * (x_max - x_min))
            y_pad = max(1.0, 0.02 * (y_max - y_min))
            ax.set_xlim(x_min - x_pad, x_max + x_pad)
            ax.set_ylim(y_min - y_pad, y_max + y_pad)
        ax.set_xlabel("X Values")
        ax.set_ylabel("Y Values")
        ax.invert_yaxis()   # Invert y-axis to match typical event camera coordinate system  

        # --- Persistence ---
        if persistence_us is None:
            persistence_us = (1e6 / fps)  # ~1 frame

        # --- Scatter ---
        sc = ax.scatter([], [], s=marker_size, marker="o",
                        facecolors=np.zeros((0, 4)), edgecolors="none")

        start_wall_time = None
        seek_offset_us = start_offset_us

        # --- Progressbar init ---
        if progressbar is not None:
            progressbar["maximum"] = 100
            progressbar["value"] = 0

        # --- Update function ---
        def update(_):
            nonlocal start_wall_time, seek_offset_us

            now = time.perf_counter()
            if start_wall_time is None:
                start_wall_time = now

            elapsed_us = (now - start_wall_time) * 1e6 + seek_offset_us
            current_t = t_start + elapsed_us
            if current_t > t_end:
                current_t = t_end

            if cumulative:
                mask = ts <= current_t
            else:
                mask = (ts > current_t - persistence_us) & (ts <= current_t)

            if not mask.any():
                sc.set_offsets(np.empty((0, 2)))
                return (sc,)

            xf = xs[mask]
            yf = ys[mask]
            pf = ps[mask]

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
            else:  # both
                colors = np.zeros((len(xf), 4))
                pos = pf > 0
                colors[pos] = [1, 0, 0, alpha]
                colors[~pos] = [0, 0, 1, alpha]

            sc.set_offsets(np.column_stack((xf, yf)))
            sc.set_facecolors(colors)

            # --- Progress + time label ---
            frac = (current_t - t_start) / t_duration
            frac = max(0.0, min(1.0, frac))

            if progressbar is not None:
                progressbar["value"] = frac * 100
            if time_label is not None:
                time_label.config(text=f"{(current_t - t_start)/1e3:.1f} / {t_duration/1e3:.1f} ms")

            ax.set_title(f"{(current_t - t_start)/1e3:.2f} ms")
            return (sc,)

        # --- Timer ---
        anim = animation.FuncAnimation(
            fig,
            update,
            interval=1000 / fps,
            blit=False,
            cache_frame_data=False
        )

        # --- Scrubbing / seek support ---
        def seek(frac):
            nonlocal start_wall_time, seek_offset_us
            frac = max(0.0, min(1.0, frac))
            seek_offset_us = frac * t_duration
            anim.seek_offset_us = seek_offset_us
            start_wall_time = None  # timer will restart on resume
        anim.seek = seek

        # --- Pause / resume support ---
        def pause():
            nonlocal start_wall_time, seek_offset_us
            if anim.event_source is not None:
                now = time.perf_counter()
                if start_wall_time is not None:
                    seek_offset_us += (now - start_wall_time) * 1e6
                anim.seek_offset_us = seek_offset_us
                start_wall_time = None
                anim.event_source.stop()
        def resume():
            nonlocal start_wall_time
            if anim.event_source is not None and not anim.event_source.running:
                start_wall_time = time.perf_counter()
                anim.event_source.start()
                update(0)  # Force immediate update when resuming

        anim.pause = pause
        anim.resume = resume

        if created_fig:
            plt.show()

        return anim