import tkinter as tk
from tkinter import ttk
import os
import threading
import queue
import itertools
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from Loading_Data import LoadingData as ld
from Event_Frame_Visualization import EventFrameVisualization
from Event_3D_Visualization import Event3DVisualization
from Event_Voxel_Visualization import EventVoxelVisualization
from Exporting_Data import ExportingData
from Cleaning_Data import CleaningData

from GUI_helper import setup_time_range_section, reset_for_new_file


# Optional BIN converter — EveViz runs fully without Main.exe on PATH.
try:
    bin_not_available = not ld.is_bin_converter_available()
except Exception:
    bin_not_available = True

def _bin_not_installed_message():
    return ld.bin_converter_not_found_message()


def _bin_installed_hint():
    found = ld.find_bin_converter_path()
    if found is None:
        return _bin_not_installed_message()
    return f"BIN converter found: {found}"


# Application state container to avoid scattered module-level globals
class AppState:
    def __init__(self):

        # original (raw) data backup
        self.raw_x = None
        self.raw_y = None
        self.raw_t = None
        self.raw_p = None

        # event data arrays
        self.x_values = None
        self.y_values = None
        self.t_values = None
        self.p_values = None

        # time range (microseconds)
        self.start_time_us = None
        self.duration_us = None
        # last-used units for time range
        self.start_time_unit = ""  # Default to empty for startup
        self.duration_unit = ""

        # axis limits for persistent scaling
        self.max_x = None
        self.max_y = None

        #temporal duration of the file
        self.min_t = None
        self.max_t = None

        # filter flags
        self.hot_pixel_filter_applied = False
        self.voxel_activity_filter_applied = False
        # self.neighbor_activity_filter_applied = False
        self.density_filter_applied = False
        self.median_filter_applied = False

        # file information
        self.filename = None

        # raw event counts (before cleaning)
        self.raw_total_events = None
        self.raw_positive_events = None
        self.raw_negative_events = None

        # filter parameters with defaults
        self.hot_pixel_threshold = 99.999
        self.voxel_activity_spatial_window = 5
        self.voxel_activity_time_window = 5000
        # self.neighbor_activity_spatial_window = 10
        # self.neighbor_activity_time_window = 500
        self.density_percentile = 80.0
        self.density_alpha = 0.2
        self.median_spatial_window = 10
        self.median_time_window = 3000

        # filter statistics (events removed, percentage removed)
        self.hot_pixel_removed = 0
        self.hot_pixel_percentage = 0.0
        self.hot_pixel_threshold_display = None
        self.hot_pixel_validated = None
        self.voxel_activity_removed = 0
        self.voxel_activity_percentage = 0.0
        # self.neighbor_activity_removed = 0
        # self.neighbor_activity_percentage = 0.0
        self.density_removed = 0
        self.density_percentage = 0.0
        self.median_removed = 0
        self.median_percentage = 0.0
        # total statistics
        self.total_removed = 0
        self.total_percentage = 0.0

# single shared state instance
state = AppState()

"--------------------------------------------------------------------------------------------------------------------------------------"
"         PARAMETER TUNING WINDOW CODE BELOW                                                                                           "
"--------------------------------------------------------------------------------------------------------------------------------------"

def create_parameter_tuning_window(parent, state):
    """Open a window for tuning filter parameters.
    
    Parameters:
    - parent: parent Tk window (used as master for Toplevel)
    - state: AppState instance with filter parameters
    """
    tuning_win = tk.Toplevel(parent)
    tuning_win.title("EveViz - Filter Parameter Tuning")
    tuning_win.geometry("750x300")
    
    # Title
    title_label = tk.Label(tuning_win, text="Filter Parameter Tuning", font=("Arial", 14, "bold"))
    title_label.pack(pady=10)
    
    # Create a main frame for parameters with grid layout
    main_frame = tk.Frame(tuning_win)
    main_frame.pack(fill="both", expand=True, padx=15, pady=10)
    
    # ===== HOT PIXEL FILTER =====
    hot_pixel_frame = tk.LabelFrame(main_frame, text="Hot Pixel", font=("Arial", 9, "bold"), padx=8, pady=6)
    hot_pixel_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
    
    tk.Label(hot_pixel_frame, text="Threshold (%):", font=("Arial", 8)).pack(anchor="w")
    hot_pixel_var = tk.DoubleVar(value=state.hot_pixel_threshold)
    hot_pixel_spinbox = tk.Spinbox(
        hot_pixel_frame, from_=0, to=100, width=12, textvariable=hot_pixel_var, increment=0.001, font=("Arial", 8)
    )
    hot_pixel_spinbox.pack(anchor="w", pady=(2, 4))
    tk.Label(hot_pixel_frame, text="(Rec: 99.0-99.999 %)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,4))
    
    # ===== VOXEL ACTIVITY FILTER =====
    voxel_frame = tk.LabelFrame(main_frame, text="Voxel Activity", font=("Arial", 9, "bold"), padx=8, pady=6)
    voxel_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
    
    tk.Label(voxel_frame, text="Spatial (px):", font=("Arial", 8)).pack(anchor="w")
    voxel_spatial_var = tk.IntVar(value=state.voxel_activity_spatial_window)
    voxel_spatial_spinbox = tk.Spinbox(
        voxel_frame, from_=1, to=999999, width=12, textvariable=voxel_spatial_var, increment=1, font=("Arial", 8)
    )
    voxel_spatial_spinbox.pack(anchor="w", pady=(2, 2))
    tk.Label(voxel_frame, text="(Rec: 5-15 px)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,2))
    
    tk.Label(voxel_frame, text="Temporal (µs):", font=("Arial", 8)).pack(anchor="w")
    voxel_time_var = tk.IntVar(value=state.voxel_activity_time_window)
    voxel_time_spinbox = tk.Spinbox(
        voxel_frame, from_=1, to=999999, width=12, textvariable=voxel_time_var, increment=100, font=("Arial", 8)
    )
    voxel_time_spinbox.pack(anchor="w", pady=(2, 4))
    tk.Label(voxel_frame, text="(Rec: 100-10000 µs)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,4))
    
    # (Neighbor Activity Filter removed)
    
    # ===== DENSITY FILTER =====
    density_frame = tk.LabelFrame(main_frame, text="Voxel Density", font=("Arial", 9, "bold"), padx=8, pady=6)
    density_frame.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

    tk.Label(density_frame, text="Percentile (%):", font=("Arial", 8)).pack(anchor="w")
    density_percentile_var = tk.DoubleVar(value=state.density_percentile)
    density_percentile_spinbox = tk.Spinbox(
        density_frame, from_=0, to=100, width=12, textvariable=density_percentile_var, increment=1, font=("Arial", 8)
    )
    density_percentile_spinbox.pack(anchor="w", pady=(2, 2))
    tk.Label(density_frame, text="(Rec: 60-99 %)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,2))

    tk.Label(density_frame, text="Strength α (0-1):", font=("Arial", 8)).pack(anchor="w")
    density_alpha_var = tk.DoubleVar(value=state.density_alpha)
    density_alpha_spinbox = tk.Spinbox(
        density_frame, from_=0.0, to=1.0, width=12, textvariable=density_alpha_var, increment=0.1, font=("Arial", 8)
    )
    density_alpha_spinbox.pack(anchor="w", pady=(2, 4))
    tk.Label(density_frame, text="(Rec: 0.01-0.6)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,4))

    # ===== MEDIAN FILTER =====
    median_frame = tk.LabelFrame(main_frame, text="Median", font=("Arial", 9, "bold"), padx=8, pady=6)
    median_frame.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")

    tk.Label(median_frame, text="Spatial Window (px):", font=("Arial", 8)).pack(anchor="w")
    median_spatial_var = tk.IntVar(value=state.median_spatial_window)
    median_spatial_spinbox = tk.Spinbox(
        median_frame, from_=1, to=999999, width=12, textvariable=median_spatial_var, increment=1, font=("Arial", 8)
    )
    median_spatial_spinbox.pack(anchor="w", pady=(2, 2))
    tk.Label(median_frame, text="(Rec: 5-15 px)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,2))

    tk.Label(median_frame, text="Time Window (µs):", font=("Arial", 8)).pack(anchor="w")
    median_time_var = tk.IntVar(value=state.median_time_window)
    median_time_spinbox = tk.Spinbox(
        median_frame, from_=1, to=999999, width=12, textvariable=median_time_var, increment=100, font=("Arial", 8)
    )
    median_time_spinbox.pack(anchor="w", pady=(2, 4))
    tk.Label(median_frame, text="(Rec: 50-10000 µs)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,4))

    # Configure grid weights for proper spacing
    for i in range(4):
        main_frame.grid_columnconfigure(i, weight=1)
    main_frame.grid_rowconfigure(0, weight=1)
    
    # Button frame - similar to visualization buttons
    button_frame = tk.Frame(tuning_win)
    button_frame.pack(pady=10)
    
    def confirm_settings():
        """Apply the tuned parameters to state and close window."""
        state.hot_pixel_threshold = hot_pixel_var.get()
        state.voxel_activity_spatial_window = voxel_spatial_var.get()
        state.voxel_activity_time_window = voxel_time_var.get()
        # (Neighbor Activity Filter removed)
        state.density_percentile = density_percentile_var.get()
        state.density_alpha = density_alpha_var.get()
        state.median_spatial_window = median_spatial_var.get()
        state.median_time_window = median_time_var.get()
        tuning_win.destroy()
    
    def reset_to_defaults():
        """Reset all parameters to their default values."""
        hot_pixel_var.set(99.999)
        voxel_spatial_var.set(5)
        voxel_time_var.set(5000)
        # (Neighbor Activity Filter removed)
        density_percentile_var.set(80.0)
        density_alpha_var.set(0.2)
        median_spatial_var.set(10)
        median_time_var.set(3000)
    
    confirm_btn = tk.Button(
        button_frame, text="Confirm Settings", width=20, command=confirm_settings
    )
    confirm_btn.pack(side="left", padx=6)
    
    reset_btn = tk.Button(
        button_frame, text="Reset to Defaults", width=18, command=reset_to_defaults
    )
    reset_btn.pack(side="left", padx=6)


"--------------------------------------------------------------------------------------------------------------------------------------"
"         FRAME VISUALIZATION WINDOW CODE BELOW                                                                                        "
"--------------------------------------------------------------------------------------------------------------------------------------"

def create_frame_visualization_window(parent, state, time_status):
    """Open a Toplevel window containing left-side buttons and a right-side embedded plot.

    Parameters:
    - parent: parent Tk window (used as master for Toplevel)
    - state: AppState instance with data and time range
    - time_status: a Label widget where status/error messages are shown
    """
    # create Toplevel (child window)
    frame_win = tk.Toplevel(parent)
    frame_win.title("EveViz - Frame Visualization")
    frame_win.geometry("1200x700")

    # Left panel for controls
    left_panel = tk.Frame(frame_win)
    left_panel.pack(side="left", fill="y", padx=10, pady=10)

    # Time Range input section (top of left panel)
    time_range_widgets = setup_time_range_section(
        left_panel,
        state,
        start_value=str(state.start_time_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.start_time_unit]) if state.start_time_us is not None else "",
        start_unit=state.start_time_unit,
        duration_value=str(state.duration_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.duration_unit]) if state.duration_us is not None else "",
        duration_unit=state.duration_unit
    )

    # Plotting section (box around plot function buttons)
    plotting_frame = tk.LabelFrame(
        left_panel,
        text="Plotting",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    plotting_frame.pack(pady=(0, 10), fill="x")

    # Right panel for plot (matplotlib canvas)
    right_panel = tk.Frame(frame_win)
    right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    # Create matplotlib Figure and Axes
    fig = Figure(figsize=(7, 6), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, state.max_x + 1)  # Set fixed axis limits
    ax.set_ylim(0, state.max_y + 1)
    ax.invert_yaxis()  # Invert y-axis to match typical image coordinates
    ax.set_aspect('equal', adjustable='box')
    ax.figure.subplots_adjust(right=0.9)
    ax.figure.subplots_adjust(top=0.9)
    canvas = FigureCanvasTkAgg(fig, master=right_panel)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    # Save button below the plot to export the current figure
    save_btn = tk.Button(right_panel, text="Save Plot", width=12, command=lambda: ExportingData.save_plot(frame_win, fig, time_status, state, source="frame"))
    save_btn.pack(pady=(6,0))

    # Track last-used plot function for compare
    last_plot_func = {'func': None}

    # helper that validates and calls plotting functions with ax
    def _validate_and_call(plot_func):
        last_plot_func['func'] = plot_func
        # Use time_status if available, else fallback to status_label
        status_widget = time_status if time_status is not None else status_label
        if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
            status_widget.config(text="No data loaded. Please load data first.", fg="red")
            return
        if state.start_time_us is None or state.duration_us is None:
            status_widget.config(text="Please set time range", fg="red")
            return
        try:
            plot_func(state.x_values, state.y_values, state.t_values, state.p_values, state.start_time_us, state.duration_us, ax=ax)
            ax.set_xlim(0, state.max_x + 1)
            ax.set_ylim(0, state.max_y + 1)
            ax.invert_yaxis()  # Invert y-axis to match typical image coordinates
            canvas.draw()
        except Exception as e:
            status_widget.config(text=f"Plot error: {e}", fg="red")

    def compare_raw_vs_cleaned():
        if last_plot_func['func'] is None:
            status_label.config(text="No plot to compare", fg="red")
            return
        if state.raw_x is None or state.raw_y is None or state.raw_t is None or state.raw_p is None:
            status_label.config(text="No raw data available.", fg="red")
            return
        if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
            status_label.config(text="No cleaned data available.", fg="red")
            return
        if state.start_time_us is None or state.duration_us is None:
            status_label.config(text="Please set time range", fg="red")
            return
    
        pad = 1
        max_x = getattr(state, 'max_x', 0)
        max_y = getattr(state, 'max_y', 0)
        aspect = (max_x + pad) / (max_y + pad) if (max_y + pad) > 0 else 1
        base_height = 6
        fig_width = min(base_height * 2 * aspect, 14)
        fig, (ax1, ax2) = plt.subplots(
            1, 2,
            figsize=(fig_width, base_height),
            gridspec_kw={'width_ratios': [1, 1]},
            constrained_layout=True
        )
        fig.suptitle("Comparison of Raw vs Clean data", fontsize=16, fontweight="bold", y=0.92)

        # Raw
        last_plot_func['func'](state.raw_x, state.raw_y, state.raw_t, state.raw_p, state.start_time_us, state.duration_us, ax=ax1)
        ax1.set_title("Raw Data")
        ax1.set_xlim(0, max_x + pad)
        ax1.set_ylim(0, max_y + pad)
        ax1.invert_yaxis()  # Invert y-axis to match typical image coordinates
        ax1.set_aspect('equal', adjustable='box')
        # Cleaned
        last_plot_func['func'](state.x_values, state.y_values, state.t_values, state.p_values, state.start_time_us, state.duration_us, ax=ax2)
        ax2.set_title("Cleaned Data")
        ax2.set_xlim(0, max_x + pad)
        ax2.set_ylim(0, max_y + pad)
        ax2.invert_yaxis()  # Invert y-axis to match typical image coordinates
        ax2.set_aspect('equal', adjustable='box')
        plt.show()
        
    # Create plotting buttons on the left panel
    btn_positive = tk.Button(plotting_frame, text="Positive Events", width=16,
                             command=lambda: _validate_and_call(EventFrameVisualization.plot_positive_event))
    btn_positive.pack(pady=4)

    btn_negative = tk.Button(plotting_frame, text="Negative Events", width=16,
                             command=lambda: _validate_and_call(EventFrameVisualization.plot_negative_event))
    btn_negative.pack(pady=4)

    btn_total = tk.Button(plotting_frame, text="Total Events", width=16,
                          command=lambda: _validate_and_call(EventFrameVisualization.plot_total_event))
    btn_total.pack(pady=4)

    btn_both = tk.Button(plotting_frame, text="Both Events", width=16,
                         command=lambda: _validate_and_call(EventFrameVisualization.plot_both_events))
    btn_both.pack(pady=4)

    # Compare section (box around compare button)
    compare_frame = tk.LabelFrame(
        left_panel,
        text="Compare",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    compare_frame.pack(pady=(0, 10), fill="x")
    compare_btn = tk.Button(compare_frame, text="Raw vs Clean", width=16, height=1, command=compare_raw_vs_cleaned)
    compare_btn.pack(pady=4)

    # Dedicated status label between Compare and Close
    status_label = tk.Label(left_panel, text="", font=("Arial", 9), fg="blue")
    status_label.pack(pady=(4, 8))

    # Add space before close button
    tk.Label(left_panel, text="").pack(pady=8)

    # Smaller close button
    close_btn = tk.Button(left_panel, text="Close", width=12, height=1, command=frame_win.destroy)
    close_btn.pack(pady=(2,6))

"--------------------------------------------------------------------------------------------------------------------------------------"
"         LOGNORMAL FRAME VISUALIZATION WINDOW CODE BELOW                                                                                           "
"--------------------------------------------------------------------------------------------------------------------------------------"

def create_lognormal_frame_visualization_window(parent, state, time_status):
    """Create a Lognormal Frame Visualization Toplevel with same layout as frame/voxel/3D, using accumulated plot functions."""
    frame_win = tk.Toplevel(parent)
    frame_win.title("EveViz - Lognormal Frame Visualization")
    frame_win.geometry("1200x700")

    # Left panel for buttons
    left_panel = tk.Frame(frame_win)
    left_panel.pack(side="left", fill="y", padx=10, pady=10)

    # Local time range state for Lognormal window
    local_start_value = str(state.start_time_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.start_time_unit]) if state.start_time_us is not None else ""
    local_start_unit = state.start_time_unit
    local_duration_value = str(state.duration_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.duration_unit]) if state.duration_us is not None else ""
    local_duration_unit = state.duration_unit

    # Setup time range section with local variables
    time_range_widgets = setup_time_range_section(
        left_panel,
        None,  # Do not pass AppState, use local
        start_value=local_start_value,
        start_unit=local_start_unit,
        duration_value=local_duration_value,
        duration_unit=local_duration_unit
    )

    # Local variables to track time range
    lognormal_time_range = {
        "start_value": time_range_widgets["start_var"],
        "start_unit": time_range_widgets["start_unit_var"],
        "duration_value": time_range_widgets["dur_var"],
        "duration_unit": time_range_widgets["dur_unit_var"]
    }

    def get_lognormal_time_us():
        s = lognormal_time_range["start_value"].get().strip()
        d = lognormal_time_range["duration_value"].get().strip()
        s_unit = lognormal_time_range["start_unit"].get().strip()
        d_unit = lognormal_time_range["duration_unit"].get().strip()
        if s == "" or d == "" or s_unit == "" or d_unit == "":
            return None, None, s_unit, d_unit
        try:
            s_val = float(s)
            d_val = float(d)
            unit_factor = {"µs": 1, "ms": 1_000, "s": 1_000_000}
            return s_val * unit_factor[s_unit], d_val * unit_factor[d_unit], s_unit, d_unit
        except Exception:
            return None, None, s_unit, d_unit


    # Right panel for plot (matplotlib canvas)
    right_panel = tk.Frame(frame_win)
    right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    # Create matplotlib Figure and Axes
    fig = Figure(figsize=(7, 6), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, state.max_x + 1)
    ax.set_ylim(0, state.max_y + 1)
    ax.invert_yaxis()  # Invert y-axis to match typical image coordinates
    ax.set_aspect('equal', adjustable='box')
    ax.figure.subplots_adjust(right=0.9)
    ax.figure.subplots_adjust(top=0.9)
    canvas = FigureCanvasTkAgg(fig, master=right_panel)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    # Save button below the plot to export the current figure
    save_btn = tk.Button(right_panel, text="Save Plot", width=12, command=lambda: ExportingData.save_plot(frame_win, fig, time_status, state, source="lognormal_frame"))
    save_btn.pack(pady=(6,0))

    # Track last-used plot function for compare
    last_plot_func = {'func': None}

    # helper that validates and calls plotting functions with ax
    def _validate_and_call(plot_func):
        last_plot_func['func'] = plot_func
        status_widget = time_status if time_status is not None else status_label
        if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
            status_widget.config(text="No data loaded. Please load data first.", fg="red")
            return
        # Use local time range values
        start_us, duration_us, s_unit, d_unit = get_lognormal_time_us()
        if start_us is None or duration_us is None:
            status_widget.config(text="Please set time range", fg="red")
            return
        try:
            plot_func(state.x_values, state.y_values, state.t_values, state.p_values, start_us, duration_us, state.max_x, state.max_y, ax=ax)
            ax.set_xlim(0, state.max_x + 1)
            ax.set_ylim(0, state.max_y + 1)
            ax.invert_yaxis()  # Invert y-axis to match typical image coordinates
            canvas.draw()
        except Exception as e:
            status_widget.config(text=f"Plot error: {e}", fg="red")

    def compare_raw_vs_cleaned():
        # Use local time input if present, else fall back to global state
        status_widget = status_label
        try:
            s = lognormal_time_range["start_value"].get().strip()
            d = lognormal_time_range["duration_value"].get().strip()
            s_unit = lognormal_time_range["start_unit"].get().strip()
            d_unit = lognormal_time_range["duration_unit"].get().strip()
            if s and d and s_unit and d_unit:
                try:
                    s_val = float(s)
                    d_val = float(d)
                    unit_factor = {"µs": 1, "ms": 1_000, "s": 1_000_000}
                    start_us = s_val * unit_factor[s_unit]
                    dur_us = d_val * unit_factor[d_unit]
                except Exception:
                    start_us = state.start_time_us
                    dur_us = state.duration_us
            else:
                start_us = state.start_time_us
                dur_us = state.duration_us
        except Exception:
            start_us = state.start_time_us
            dur_us = state.duration_us

        if last_plot_func['func'] is None:
            status_widget.config(text="No plot to compare", fg="red")
            return
        if state.raw_x is None or state.raw_y is None or state.raw_t is None or state.raw_p is None:
            status_widget.config(text="No raw data available.", fg="red")
            return
        if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
            status_widget.config(text="No cleaned data available.", fg="red")
            return
        if start_us is None or dur_us is None:
            status_widget.config(text="Please set time range", fg="red")
            return
        pad = 1
        max_x = getattr(state, 'max_x', 0)
        max_y = getattr(state, 'max_y', 0)
        aspect = (max_x + pad) / (max_y + pad) if (max_y + pad) > 0 else 1
        base_height = 6
        fig_width = min(base_height * 2 * aspect, 14)
        fig, (ax1, ax2) = plt.subplots(
            1, 2,
            figsize=(fig_width, base_height),
            gridspec_kw={'width_ratios': [1, 1]},
            constrained_layout=True
        )
        fig.suptitle("Comparison of Raw vs Clean data", fontsize=16, fontweight="bold", y=0.92)
        # Raw
        last_plot_func['func'](state.raw_x, state.raw_y, state.raw_t, state.raw_p, start_us, dur_us, state.max_x, state.max_y, ax=ax1)
        ax1.set_title("Raw Data")
        ax1.set_xlim(0, max_x + pad)
        ax1.set_ylim(0, max_y + pad)
        ax1.invert_yaxis()  # Invert y-axis to match typical image coordinates
        ax1.set_aspect('equal', adjustable='box')
        # Cleaned
        last_plot_func['func'](state.x_values, state.y_values, state.t_values, state.p_values, start_us, dur_us, state.max_x, state.max_y, ax=ax2)
        ax2.set_title("Cleaned Data")
        ax2.set_xlim(0, max_x + pad)
        ax2.set_ylim(0, max_y + pad)
        ax2.invert_yaxis()  # Invert y-axis to match typical image coordinates
        ax2.set_aspect('equal', adjustable='box')
        plt.show()

    # Plotting section (box around plot function buttons)
    plotting_frame = tk.LabelFrame(
        left_panel,
        text="Plotting",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    plotting_frame.pack(pady=(0, 10), fill="x")

    btn_positive = tk.Button(plotting_frame, text="Positive Events", width=16,
                             command=lambda: _validate_and_call(EventFrameVisualization.plot_postive_event_accumulated_frame))
    btn_positive.pack(pady=4)

    btn_negative = tk.Button(plotting_frame, text="Negative Events", width=16,
                             command=lambda: _validate_and_call(EventFrameVisualization.plot_negative_event_accumulated_frame))
    btn_negative.pack(pady=4)

    btn_both = tk.Button(plotting_frame, text="Both Events", width=16,
                         command=lambda: _validate_and_call(EventFrameVisualization.plot_both_event_accumulated_frame))
    btn_both.pack(pady=4)

    # Compare section (box around compare button)
    compare_frame = tk.LabelFrame(
        left_panel,
        text="Compare",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    compare_frame.pack(pady=(0, 10), fill="x")
    compare_btn = tk.Button(compare_frame, text="Raw vs Clean", width=16, height=1, command=compare_raw_vs_cleaned)
    compare_btn.pack(pady=4)

    # Dedicated status label between Compare and Close
    status_label = tk.Label(left_panel, text="", font=("Arial", 9), fg="blue")
    status_label.pack(pady=(4, 8))

    # Add space before close button
    tk.Label(left_panel, text="").pack(pady=8)
    # Close button
    close_btn = tk.Button(left_panel, text="Close", width=12, height=1, command=frame_win.destroy)
    close_btn.pack(pady=(2,6))

"--------------------------------------------------------------------------------------------------------------------------------------"
"         VOXEL VISUALIZATION WINDOW CODE BELOW                                                                                           "
"--------------------------------------------------------------------------------------------------------------------------------------"

def create_voxel_visualization_window(parent, state, time_status):
        """Create a Voxel Visualization Toplevel with the same layout as the 3D visualization."""
        frame_win = tk.Toplevel(parent)
        frame_win.title("EveViz - Voxel Visualization")
        frame_win.geometry("1200x750")

        # Left panel for buttons
        left_panel = tk.Frame(frame_win)
        left_panel.pack(side="left", fill="y", padx=10, pady=10)

        # Time Range input section (reuse helper)
        time_range_widgets = setup_time_range_section(
            left_panel,
            state,
            start_value=str(state.start_time_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.start_time_unit]) if state.start_time_us is not None else "",
            start_unit=state.start_time_unit,
            duration_value=str(state.duration_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.duration_unit]) if state.duration_us is not None else "",
            duration_unit=state.duration_unit
        )

        # Right panel for plot (matplotlib canvas)
        right_panel = tk.Frame(frame_win)
        right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Create matplotlib Figure and 3D Axes
        fig = Figure(figsize=(7, 6), dpi=100)
        ax = fig.add_subplot(111, projection='3d')
        ax.zaxis._axinfo['juggled'] = (1, 2, 0)
        ax.set_xlim(0, state.max_x + 1)  # Set fixed axis limits
        ax.set_zlim(0, state.max_y + 1)
        ax.invert_zaxis()  # Invert z-axis to match typical image coordinates
        # Set equal aspect for x and z axes based on their max values
        max_x = getattr(state, 'max_x', 1)
        max_y = getattr(state, 'max_y', 1)
        time_scale = max_x * 0.9  # Scale time axis to be visually proportional to spatial axis
        ax.set_box_aspect([max_x + 1, time_scale, max_y + 1])

        canvas = FigureCanvasTkAgg(fig, master=right_panel)
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # Save button below the plot to export the current figure
        save_btn = tk.Button(right_panel, text="Save Plot", width=12, command=lambda: ExportingData.save_plot(frame_win, fig, time_status, state, source="voxel"))
        save_btn.pack(pady=(6,0))

        # Store last-used plot function for auto-refresh and compare
        last_plot_func = {'func': None}

        def _validate_and_call(plot_func):
            last_plot_func['func'] = plot_func
            status_widget = time_status if time_status is not None else status_label
            if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
                status_widget.config(text="No data loaded. Please load data first.", fg="red")
                return
            if state.start_time_us is None or state.duration_us is None:
                status_widget.config(text="Please set time range", fg="red")
                return
            try:
                plot_func(state.x_values, state.y_values, state.t_values, state.p_values, state.start_time_us, state.duration_us, ax=ax)
                ax.set_xlim(0, state.max_x + 1)  # Set fixed axis limits
                ax.set_zlim(0, state.max_y + 1)
                ax.invert_zaxis()  # Invert z-axis to match typical image coordinates
                canvas.draw()
            except Exception as e:
                status_widget.config(text=f"Plot error: {e}", fg="red")

        def compare_raw_vs_cleaned():
            status_widget = status_label
            if last_plot_func['func'] is None:
                status_widget.config(text="No plot to compare", fg="red")
                return
            if state.raw_x is None or state.raw_y is None or state.raw_t is None or state.raw_p is None:
                status_widget.config(text="No raw data available.", fg="red")
                return
            if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
                status_widget.config(text="No cleaned data available.", fg="red")
                return
            if state.start_time_us is None or state.duration_us is None:
                status_widget.config(text="Please set time range", fg="red")
                return
            fig = plt.figure(figsize=(14, 6))
            ax1 = fig.add_subplot(121, projection='3d')
            ax1.set_box_aspect([max_x + 1, time_scale, max_y + 1])
            ax1.zaxis._axinfo['juggled'] = (1, 2, 0)
            ax1.invert_zaxis()  # Invert z-axis to match typical image coordinates
            ax2 = fig.add_subplot(122, projection='3d')
            ax2.set_box_aspect([max_x + 1, time_scale, max_y + 1])
            ax2.zaxis._axinfo['juggled'] = (1, 2, 0)
            ax2.invert_zaxis()  # Invert z-axis to match typical image coordinates
            fig.suptitle("Comparison of Raw vs Clean data", fontsize=16, fontweight="bold", y=0.92)
            last_plot_func['func'](state.raw_x, state.raw_y, state.raw_t, state.raw_p, state.start_time_us, state.duration_us, ax=ax1)
            ax1.set_title("Raw Data",y=0.98)
            last_plot_func['func'](state.x_values, state.y_values, state.t_values, state.p_values, state.start_time_us, state.duration_us, ax=ax2)
            ax2.set_title("Cleaned Data",y=0.98)
            plt.tight_layout()
            plt.show()


        # Plotting section (box around plot function buttons)
        plotting_frame = tk.LabelFrame(
            left_panel,
            text="Plotting",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=8
        )
        plotting_frame.pack(pady=(0, 10), fill="x")

        btn_positive = tk.Button(plotting_frame, text="Positive Events", width=16,
                     command=lambda: _validate_and_call(EventVoxelVisualization.plot_positive_event_voxel))
        btn_positive.pack(pady=4)

        btn_negative = tk.Button(plotting_frame, text="Negative Events", width=16,
                     command=lambda: _validate_and_call(EventVoxelVisualization.plot_negative_event_voxel))
        btn_negative.pack(pady=4)

        btn_total = tk.Button(plotting_frame, text="Total Events", width=16,
                      command=lambda: _validate_and_call(EventVoxelVisualization.plot_total_event_voxel))
        btn_total.pack(pady=4)

        btn_both = tk.Button(plotting_frame, text="Both Events", width=16,
                     command=lambda: _validate_and_call(EventVoxelVisualization.plot_both_events_voxel))
        btn_both.pack(pady=4)


        # Compare section (box around compare button)
        compare_frame = tk.LabelFrame(
            left_panel,
            text="Compare",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=8
        )
        compare_frame.pack(pady=(0, 2), fill="x")
        compare_btn = tk.Button(compare_frame, text="Raw vs Clean", width=16, height=1, command=compare_raw_vs_cleaned)
        compare_btn.pack(pady=4)

        # Time Bins section (box around input, set value button, status label, and set_default_bins logic)
        time_bins_frame = tk.LabelFrame(
            left_panel,
            text="Time Bins",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=8
        )
        time_bins_frame.pack(pady=(0, 2), fill="x")

        # Widget to set DEFAULT_BINS with more space and feedback
        def set_default_bins():
            try:
                val = int(bins_var.get())
                if val > 0:
                    from Event_Voxel_Visualization import EventVoxelVisualization
                    EventVoxelVisualization.DEFAULT_BINS = val
                    bins_status.config(text=f"Time bins set to {val}.", fg="green")
                    # Auto-refresh plot if one was used
                    if last_plot_func['func']:
                        _validate_and_call(last_plot_func['func'])
                else:
                    bins_status.config(text="Value must be > 0.", fg="red")
            except Exception:
                bins_status.config(text="Invalid input. Enter a positive integer.", fg="red")

        bins_var = tk.StringVar(value="20")
        bins_entry = tk.Entry(time_bins_frame, textvariable=bins_var, width=8, font=("Arial", 10))
        bins_entry.pack(pady=(8, 12))

        bins_status = tk.Label(time_bins_frame, text="", font=("Arial", 9))
        bins_status.pack(pady=(0, 8))

        set_btn = tk.Button(time_bins_frame, text="Set value", width=12, command=set_default_bins)
        set_btn.pack(pady=(0, 2))

        bins_entry.bind("<Return>", lambda e: set_default_bins())
        bins_entry.bind("<FocusOut>", lambda e: set_default_bins())

        # Dedicated status label between time bins and close button
        status_label = tk.Label(left_panel, text="", font=("Arial", 9), fg="blue")
        status_label.pack(pady=(8, 8))

        # Move close button after status label
        close_btn = tk.Button(left_panel, text="Close", width=12, height=1, command=frame_win.destroy)
        close_btn.pack(pady=(10,12))

"--------------------------------------------------------------------------------------------------------------------------------------"
"         3D VISUALIZATION WINDOW CODE BELOW                                                                                           "
"--------------------------------------------------------------------------------------------------------------------------------------"

def create_3d_visualization_window(parent, state, time_status):
    """Create a 3D Visualization Toplevel with the same layout as the frame visualization."""
    frame_win = tk.Toplevel(parent)
    frame_win.title("EveViz - 3D Visualization")
    frame_win.geometry("1200x700")

    # Left panel for buttons
    left_panel = tk.Frame(frame_win)
    left_panel.pack(side="left", fill="y", padx=10, pady=10)

    # Time Range input section (reuse helper)
    time_range_widgets = setup_time_range_section(
        left_panel,
        state,
        start_value=str(state.start_time_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.start_time_unit]) if state.start_time_us is not None else "",
        start_unit=state.start_time_unit,
        duration_value=str(state.duration_us / {"µs": 1, "ms": 1_000, "s": 1_000_000}[state.duration_unit]) if state.duration_us is not None else "",
        duration_unit=state.duration_unit
    )

    # Right panel for plot (matplotlib canvas)
    right_panel = tk.Frame(frame_win)
    right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    # Create matplotlib Figure and 3D Axes
    fig = Figure(figsize=(7, 6), dpi=100)
    ax = fig.add_subplot(111, projection='3d')
    ax.zaxis._axinfo['juggled'] = (1, 2, 0)
    ax.set_xlim(0, state.max_x + 1)  # Set fixed axis limits
    ax.set_zlim(0, state.max_y + 1)
    ax.invert_zaxis()  # Invert y-axis to match typical image coordinates
    # Set equal aspect for x and z axes based on their max values
    max_x = getattr(state, 'max_x', 1)
    max_y = getattr(state, 'max_y', 1)
    time_scale = max_x * 0.9  # Scale time axis to be visually proportional to spatial axis
    ax.set_box_aspect([max_x + 1, time_scale, max_y + 1])

    canvas = FigureCanvasTkAgg(fig, master=right_panel)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    # Save button below the plot to export the current figure
    save_btn = tk.Button(right_panel, text="Save Plot", width=12, command=lambda: ExportingData.save_plot(frame_win, fig, time_status, state, source="3d"))
    save_btn.pack(pady=(6,0))

    # Track last-used plot function for compare
    last_plot_func = {'func': None}

    # helper that validates and calls plotting functions with ax
    def _validate_and_call(plot_func):
        last_plot_func['func'] = plot_func
        status_widget = time_status if time_status is not None else status_label
        if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
            status_widget.config(text="No data loaded. Please load data first.", fg="red")
            return
        if state.start_time_us is None or state.duration_us is None:
            status_widget.config(text="Please set time range", fg="red")
            return
        try:
            plot_func(state.x_values, state.y_values, state.t_values, state.p_values, state.start_time_us, state.duration_us, ax=ax)
            ax.set_xlim(0, state.max_x + 1)  # Set fixed axis limits
            ax.set_zlim(0, state.max_y + 1)
            ax.invert_zaxis()  # Invert z-axis to match typical image coordinates
            canvas.draw()
        except Exception as e:
            status_widget.config(text=f"Plot error: {e}", fg="red")

    def compare_raw_vs_cleaned():
        status_widget = status_label
        if last_plot_func['func'] is None:
            status_widget.config(text="No plot to compare", fg="red")
            return
        if state.raw_x is None or state.raw_y is None or state.raw_t is None or state.raw_p is None:
            status_widget.config(text="No raw data available.", fg="red")
            return
        if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
            status_widget.config(text="No cleaned data available.", fg="red")
            return
        if state.start_time_us is None or state.duration_us is None:
            status_widget.config(text="Please set time range", fg="red")
            return
        fig = plt.figure(figsize=(14, 6))
        ax1 = fig.add_subplot(121, projection='3d')
        ax1.set_box_aspect([max_x + 1, time_scale, max_y + 1])
        ax1.zaxis._axinfo['juggled'] = (1, 2, 0)
        ax1.invert_zaxis()  # Invert z-axis to match typical image coordinates
        ax2 = fig.add_subplot(122, projection='3d')
        ax2.set_box_aspect([max_x + 1, time_scale, max_y + 1])
        ax2.zaxis._axinfo['juggled'] = (1, 2, 0)
        ax2.invert_zaxis()  # Invert z-axis to match typical image coordinates
        fig.suptitle("Comparison of Raw vs Clean data", fontsize=16, fontweight="bold", y=0.92)
        last_plot_func['func'](state.raw_x, state.raw_y, state.raw_t, state.raw_p, state.start_time_us, state.duration_us, ax=ax1)
        ax1.set_title("Raw Data",y=0.98)
        last_plot_func['func'](state.x_values, state.y_values, state.t_values, state.p_values, state.start_time_us, state.duration_us, ax=ax2)
        ax2.set_title("Cleaned Data",y=0.98)
        plt.tight_layout()
        plt.show()

    # Plotting section (box around plot function buttons)
    plotting_frame = tk.LabelFrame(
        left_panel,
        text="Plotting",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    plotting_frame.pack(pady=(0, 10), fill="x")

    btn_positive = tk.Button(plotting_frame, text="Positive Events", width=16,
                             command=lambda: _validate_and_call(Event3DVisualization.plot_positive_event_3d))
    btn_positive.pack(pady=4)

    btn_negative = tk.Button(plotting_frame, text="Negative Events", width=16,
                             command=lambda: _validate_and_call(Event3DVisualization.plot_negative_event_3d))
    btn_negative.pack(pady=4)

    btn_total = tk.Button(plotting_frame, text="Total Events", width=16,
                          command=lambda: _validate_and_call(Event3DVisualization.plot_total_event_3d))
    btn_total.pack(pady=4)

    btn_both = tk.Button(plotting_frame, text="Both Events", width=16,
                         command=lambda: _validate_and_call(Event3DVisualization.plot_both_events_3d))
    btn_both.pack(pady=4)

    # Compare section (box around compare button)
    compare_frame = tk.LabelFrame(
        left_panel,
        text="Compare",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    compare_frame.pack(pady=(0, 10), fill="x")
    compare_btn = tk.Button(compare_frame, text="Raw vs Clean", width=16, height=1, command=compare_raw_vs_cleaned)
    compare_btn.pack(pady=4)

    # Dedicated status label between Compare and Close
    status_label = tk.Label(left_panel, text="", font=("Arial", 9), fg="blue")
    status_label.pack(pady=(4, 8))

    # Add space before close button
    tk.Label(left_panel, text="").pack(pady=8)
    # Smaller close button
    close_btn = tk.Button(left_panel, text="Close", width=12, height=1, command=frame_win.destroy)
    close_btn.pack(pady=(2,6))

"--------------------------------------------------------------------------------------------------------------------------------------"
"         FRAME VIDEO WINDOW CODE BELOW                                                                                        "
"--------------------------------------------------------------------------------------------------------------------------------------"

def create_frame_video_window(parent, state, viz_status):
    """Open a Toplevel window dedicated to frame video animation.

    Parameters:
    - parent: parent Tk window (used as master for Toplevel)
    - state: AppState instance with data and time range
    - viz_status: a Label widget where status/error messages are shown
    """
    # create Toplevel (child window)
    video_win = tk.Toplevel(parent)
    video_win.title("EveViz - Frame Video")
    video_win.geometry("1200x700")

    # Left panel for buttons
    left_panel = tk.Frame(video_win)
    left_panel.pack(side="left", fill="y", padx=10, pady=10)

    # Right panel for plot (matplotlib canvas)
    right_panel = tk.Frame(video_win)
    right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    # Create matplotlib Figure and Axes
    fig = Figure(figsize=(7, 6), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, state.max_x + 1)  # Set fixed axis limits
    ax.set_ylim(0, state.max_y + 1)
    ax.set_aspect('equal', adjustable='box')
    ax.invert_yaxis()  # Invert y-axis to match typical event camera coordinate system
    ax.figure.subplots_adjust(right=0.9)
    ax.figure.subplots_adjust(top=0.9)
    canvas = FigureCanvasTkAgg(fig, master=right_panel)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    # --- TIME LABEL & PROGRESS BAR ---
    time_label = ttk.Label(right_panel, text="0.0 / 0.0 ms")
    time_label.pack(pady=(6, 0))

    video_progress = ttk.Progressbar(
        right_panel,
        orient="horizontal",
        mode="determinate",
        length=500
    )
    video_progress.pack(fill="x", pady=(2, 6))

    # Save button below the plot to export the video with current mode
    def save_video_callback():
        def save_in_background():
            current_mode = anim_mode['mode']
            ExportingData.save_video(
                video_win,
                fig,
                state.x_values,
                state.y_values,
                state.t_values,
                state.p_values,
                state.max_x,
                state.max_y,
                export_status,
                state=state,
                mode=current_mode
            )

        # Run save_video in a background thread to avoid freezing the GUI
        save_thread = threading.Thread(target=save_in_background, daemon=True)
        save_thread.start()

    def save_screenshot_callback():
        """Save a screenshot of the current frame displayed"""
        anim = getattr(video_win, "current_anim", None)
        
        # Try to get the current timestamp from the animation's time label
        current_timestamp_us = state.start_time_us if state.start_time_us is not None else state.min_t
        
        # Extract the current time (in ms) from the time_label text (format: "X.X / Y.Y ms")
        try:
            time_text = time_label.cget("text").strip()
            if " / " in time_text:
                current_time_ms = float(time_text.split(" / ")[0])
                current_timestamp_us = int(current_time_ms * 1000)  # Convert ms to microseconds
        except Exception:
            pass  # Fall back to default if parsing fails
        
        ExportingData.save_screenshot(video_win, fig, current_timestamp_us, export_status, state)

    # Button frame to hold both save buttons side by side
    button_frame = tk.Frame(right_panel)
    button_frame.pack(pady=(6, 0))

    save_btn = tk.Button(button_frame, text="Save Video", width=12, command=save_video_callback)
    save_btn.pack(side="left", padx=(0, 6))

    screenshot_btn = tk.Button(button_frame, text="Save Screenshot", width=12, command=save_screenshot_callback)
    screenshot_btn.pack(side="left")

    # Track current animation mode
    anim_mode = {'mode': 'both'}

    # DISPLAY FRAME FUNCTION (static, no animation)
    def display_frame(mode):
        """Display a single starting frame without animation"""
        anim_mode['mode'] = mode

        if state.x_values is None or state.y_values is None or state.t_values is None:
            export_status.config(text="No data loaded.", fg="red")
            return

        # Stop any running animation
        anim = getattr(video_win, "current_anim", None)
        if anim is not None:
            try:
                anim.pause()
            except:
                pass
            video_win.current_anim = None

        # Use full time range if not explicitly set
        start_time = state.start_time_us if state.start_time_us is not None else state.min_t
        duration = state.duration_us if state.duration_us is not None else 5_000  # 5 ms default

        try:
            ax.cla()
            if mode == "positive":
                EventFrameVisualization.plot_positive_event(
                    state.x_values, state.y_values, state.t_values, state.p_values,
                    start_time, duration, ax=ax
                )
            elif mode == "negative":
                EventFrameVisualization.plot_negative_event(
                    state.x_values, state.y_values, state.t_values, state.p_values,
                    start_time, duration, ax=ax
                )
            elif mode == "all":
                EventFrameVisualization.plot_total_event(
                    state.x_values, state.y_values, state.t_values, state.p_values,
                    start_time, duration, ax=ax
                )
            else:  # both
                EventFrameVisualization.plot_both_events(
                    state.x_values, state.y_values, state.t_values, state.p_values,
                    start_time, duration, ax=ax
                )

            ax.set_xlim(0, state.max_x + 1)
            ax.set_ylim(0, state.max_y + 1)
            ax.invert_yaxis()
            canvas.draw()
        except Exception as e:
            export_status.config(text=f"Frame display error: {e}", fg="red")

    # ANIMATION FUNCTIONS
    def animate_video():
        if state.x_values is None or state.y_values is None or state.t_values is None:
            export_status.config(text="No data loaded.", fg="red")
            return

        # If animation exists, get the current offset and stop it
        start_offset_us = 0.0
        anim = getattr(video_win, "current_anim", None)
        if anim is not None:
            start_offset_us = getattr(anim, 'seek_offset_us', 0.0)
            try:
                anim.pause()
            except:
                pass
            video_win.current_anim = None

        # Create new animation from the offset
        try:
            ax.cla()
            anim = EventFrameVisualization.animate_frame_video(
                state.x_values,
                state.y_values,
                state.t_values,
                state.p_values,
                ax=ax,
                max_x=state.max_x,
                max_y=state.max_y,
                progressbar=video_progress,
                time_label=time_label,
                start_offset_us=start_offset_us,
                mode=anim_mode['mode'],
            )
            video_win.current_anim = anim
            canvas.draw_idle()
            
        except Exception as e:
            export_status.config(text=f"Animation error: {e}", fg="red")

    def stop_animation():
        anim = getattr(video_win, "current_anim", None)
        if anim is None:
            export_status.config(text="No animation running", fg="red")
            return
        try:
            anim.pause()
        except Exception as e:
            export_status.config(text=f"Error stopping animation: {e}", fg="red")

    def restart_video():
        prev = getattr(video_win, "current_anim", None)
        if prev is not None:
            try:
                prev.pause()  # stop timer safely
            except:
                pass
            video_win.current_anim = None
        animate_video()  # create new animation from t = 0  
    
    # --- SCRUBBING / CLICK-TO-SEEK ---
    def on_progress_click(event):
        frac = event.x / video_progress.winfo_width()
        anim = getattr(video_win, "current_anim", None)
        if anim and hasattr(anim, "seek"):
            anim.seek(frac)
            # Force update immediately
            anim._func(0)  # call the update function once
            canvas.draw_idle()

    video_progress.bind("<Button-1>", on_progress_click)

    # --- CONTROLS BOX ---
    controls_frame = tk.LabelFrame(
        left_panel,
        text="Controls",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    controls_frame.pack(pady=(12, 10), fill="x")

    btn_animate = tk.Button(controls_frame, text="Start Video", width=16, command=animate_video)
    btn_animate.pack(pady=4)

    btn_stop = tk.Button(controls_frame, text="Stop Video", width=16, command=stop_animation)
    btn_stop.pack(pady=4)

    btn_restart = tk.Button(controls_frame, text="Restart Video", width=16, command=restart_video)
    btn_restart.pack(pady=4)

    # --- ANIMATING BOX ---
    animating_frame = tk.LabelFrame(
        left_panel,
        text="Animating",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    animating_frame.pack(pady=(0, 10), fill="x")

    btn_positive = tk.Button(animating_frame, text="Positive Events", width=16,
                             command=lambda: display_frame("positive"))
    btn_positive.pack(pady=4)

    btn_negative = tk.Button(animating_frame, text="Negative Events", width=16,
                             command=lambda: display_frame("negative"))
    btn_negative.pack(pady=4)

    btn_total = tk.Button(animating_frame, text="Total Events", width=16,
                          command=lambda: display_frame("all"))
    btn_total.pack(pady=4)

    btn_both = tk.Button(animating_frame, text="Both Events", width=16,
                         command=lambda: display_frame("both"))
    btn_both.pack(pady=4)

    # --- EXPORT STATUS LABEL ---
    export_status = tk.Label(left_panel, text="", wraplength=180, justify="left", height=2)
    export_status.pack(pady=10, fill="x")

    # Space before close button
    tk.Label(left_panel, text="").pack(pady=2)

    # Smaller close button
    close_btn = tk.Button(left_panel, text="Close", width=12, height=1, command=video_win.destroy)
    close_btn.pack(pady=(2, 6))
    close_btn.bind("<ButtonPress-1>", lambda e: viz_status.config(text="", fg="black"))

"--------------------------------------------------------------------------------------------------------------------------------------"
"         EVENT VISUALIZATION WINDOW CODE BELOW - OPENS FRAME VISUALIZATION WINDOW AND 3D VISUALIZATION WINDOW AND FRAME VIDEO WINDOW  "                                                           
"--------------------------------------------------------------------------------------------------------------------------------------"

def open_event_visualization(loading_window):
    """Open the Event Visualization window"""

    # Close the loading window
    loading_window.destroy()

    # Create new window for Event Visualization (this window stays open)
    viz_root = tk.Tk()
    viz_root.title("EveViz - Homepage")
    viz_root.geometry("900x700")

    # --- SCROLLABLE CANVAS SETUP (improved layout) ---
    # Create a containing frame for canvas + scrollbar
    container = tk.Frame(viz_root)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, borderwidth=0, background="#f0f0f0", highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    vscrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    vscrollbar.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=vscrollbar.set)

    # The frame that will contain all content
    content_frame = tk.Frame(canvas, background="#f0f0f0")
    # Set a minimum width to preserve layout
    min_width = 860
    content_frame_id = canvas.create_window((0, 0), window=content_frame, anchor="nw", width=min_width)

    def _on_frame_configure(event):
        # Set scroll region to encompass the inner frame
        canvas.configure(scrollregion=canvas.bbox("all"))
        # Always keep the content frame at least min_width wide
        canvas.itemconfig(content_frame_id, width=max(canvas.winfo_width(), min_width))

    def _on_canvas_configure(event):
        # Keep content frame width in sync with canvas width (but not smaller than min_width)
        canvas.itemconfig(content_frame_id, width=max(event.width, min_width))

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    content_frame.bind("<Configure>", _on_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # Title and info
    title_label = tk.Label(content_frame, text="Event Visualization", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)

    # ---------------- OVERVIEW SECTION ----------------#
    overview_frame = tk.LabelFrame(
        content_frame,
        text="Overview",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    overview_frame.pack(pady=6, fill="x", padx=20)

    # File name
    filename_label = tk.Label(overview_frame, text=f"File: {state.filename}", font=("Arial", 10))
    filename_label.pack(anchor="w")

    #Recoding length
    min_t_ms = state.min_t / 1000
    max_t_ms = state.max_t / 1000
    rec_length_label = tk.Label(
        overview_frame,
        text=f"Recording length: {min_t_ms:,.0f} - {max_t_ms:,.0f} ms",
        font=("Arial", 10)
    )
    rec_length_label.pack(anchor="w")

    # Number of events
    events_label = tk.Label(overview_frame, text=f"Total Events: {state.raw_total_events:,}", font=("Arial", 10))
    events_label.pack(anchor="w")

    # Positive and negative events
    pos_neg_label = tk.Label(overview_frame, text=f"Positive Events: {state.raw_positive_events:,} | Negative Events: {state.raw_negative_events:,}", font=("Arial", 10))
    pos_neg_label.pack(anchor="w")

    # Export report button (lower right corner)
    def on_export_report():
        ExportingData.export_report(state)

    export_btn = tk.Button(overview_frame, text="Export Report", width=16, command=on_export_report)
    export_btn.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)


    # ---------------- CLEANING FILTERS SECTION ----------------#
    filters_frame = tk.LabelFrame(
        content_frame,
        text="Cleaning Filters",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    filters_frame.pack(pady=6, fill="x", padx=20)

    # Checkbox variables
    hot_pixel_var = tk.BooleanVar()
    voxel_activity_var = tk.BooleanVar()
    # neighbor_activity_var = tk.BooleanVar()
    density_var = tk.BooleanVar()
    median_var = tk.BooleanVar()

    # Create two-column layout: Selection and Statistics
    selection_stats_frame = tk.Frame(filters_frame)
    selection_stats_frame.pack(fill="x", pady=(4, 0))
    
    # Selection column (left)
    selection_frame = tk.Frame(selection_stats_frame)
    selection_frame.pack(side="left", fill="both", expand=True)
    
    tk.Label(selection_frame, text="Selection", font=("Arial", 9, "bold")).pack(anchor="w")
    # Per-filter rows with indicator labels
    hot_row = tk.Frame(selection_frame)
    hot_row.pack(anchor="w")
    hot_pixel_cb = tk.Checkbutton(hot_row, text="Hot Pixel Filter", variable=hot_pixel_var)
    hot_pixel_cb.pack(side="left")
    hot_ind = tk.Label(hot_row, text=" ", width=2)
    hot_ind.pack(side="left", padx=(6, 0))

    voxel_row = tk.Frame(selection_frame)
    voxel_row.pack(anchor="w")
    voxel_activity_cb = tk.Checkbutton(voxel_row, text="Voxel Activity Filter", variable=voxel_activity_var)
    voxel_activity_cb.pack(side="left")
    voxel_ind = tk.Label(voxel_row, text=" ", width=2)
    voxel_ind.pack(side="left", padx=(6, 0))

    # (Neighbor Activity Filter row removed)

    density_row = tk.Frame(selection_frame)
    density_row.pack(anchor="w")
    density_cb = tk.Checkbutton(density_row, text="Voxel Density Filter", variable=density_var)
    density_cb.pack(side="left")
    density_ind = tk.Label(density_row, text=" ", width=2)
    density_ind.pack(side="left", padx=(6, 0))

    median_row = tk.Frame(selection_frame)
    median_row.pack(anchor="w")
    median_cb = tk.Checkbutton(median_row, text="Median Filter", variable=median_var)
    median_cb.pack(side="left")
    median_ind = tk.Label(median_row, text=" ", width=2)
    median_ind.pack(side="left", padx=(6, 0))

    # Map short names to indicator widgets for easy updates
    indicator_map = {
        'hot': hot_ind,
        'voxel': voxel_ind,
        # 'neighbor': neighbor_ind,
        'density': density_ind,
        'median': median_ind,
    }
    
    # Statistics column (right) with collapsible details
    stats_frame = tk.Frame(selection_stats_frame)
    stats_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

    tk.Label(stats_frame, text="Statistics", font=("Arial", 9, "bold")).pack(anchor="w")

    # Total row (always visible) using separate labels so only keywords are bold
    total_row = tk.Frame(stats_frame)
    total_row.pack(anchor="w", fill="x")
    bold_font = ("Arial", 9, "bold")
    normal_font = ("Arial", 9)
    total_label = tk.Label(total_row, text="Total:", font=bold_font, fg="gray")
    total_label.pack(side="left")
    # show same format as populated state but with placeholders when collapsed
    total_removed_label = tk.Label(total_row, text=" — events removed (—%) |", font=normal_font, fg="gray")
    total_removed_label.pack(side="left")
    remaining_bold_label = tk.Label(total_row, text=" Remaining:", font=bold_font, fg="gray")
    remaining_bold_label.pack(side="left")
    remaining_info_label = tk.Label(total_row, text=" — events", font=normal_font, fg="gray")
    remaining_info_label.pack(side="left")

    # Toggle button for expanding/collapsing detailed stats
    toggle_btn = tk.Button(total_row, text="▶", width=2)
    toggle_btn.pack(side="left", padx=(6, 0))

    # Detail frame (contains per-filter stats); start collapsed (not packed)
    detail_frame = tk.Frame(stats_frame)

    hot_pixel_stats = tk.Label(detail_frame, text="Hot Pixel: — events (—%)", font=("Arial", 8), fg="gray")
    hot_pixel_stats.pack(anchor="w")
    voxel_activity_stats = tk.Label(detail_frame, text="Voxel Activity: — events (—%)", font=("Arial", 8), fg="gray")
    voxel_activity_stats.pack(anchor="w")
    # (Neighbor Activity Filter stats removed)
    density_stats = tk.Label(detail_frame, text="Voxel Density: — events (—%)", font=("Arial", 8), fg="gray")
    density_stats.pack(anchor="w")
    median_stats = tk.Label(detail_frame, text="Median: — events (—%)", font=("Arial", 8), fg="gray")
    median_stats.pack(anchor="w")

    # toggle implementation
    def toggle_details():
        if detail_frame.winfo_ismapped():
            detail_frame.pack_forget()
            toggle_btn.config(text="▶")
        else:
            detail_frame.pack(anchor="w", pady=(4, 0))
            toggle_btn.config(text="▼")

    toggle_btn.config(command=toggle_details)

    # Status label for cleaning
    cleaning_status = tk.Label(filters_frame, text="", font=("Arial", 9))
    cleaning_status.pack(pady=(4, 0))

    # Background worker infrastructure: queue + single-worker executor + spinner
    progress_queue = queue.Queue()
    executor = ThreadPoolExecutor(max_workers=1)
    _spinner_chars = itertools.cycle("|/-\\")

    def animate_spinner(label):
        # start a spinner on the given label (runs on main thread via after)
        if getattr(label, '_spinner_running', False):
            return
        label._spinner_running = True

        def _tick():
            if not getattr(label, '_spinner_running', False):
                return
            label.config(text=next(_spinner_chars), fg='black')
            label._after_id = label.after(120, _tick)

        _tick()

    def stop_spinner(label):
        label._spinner_running = False
        aid = getattr(label, '_after_id', None)
        try:
            if aid:
                label.after_cancel(aid)
        except Exception:
            pass
        # clear spinner text
        label.config(text=' ')

    def cleaning_worker(filters_to_run, q):
        try:
            x = state.raw_x.copy()
            y = state.raw_y.copy()
            t = state.raw_t.copy()
            p = state.raw_p.copy()
            events_before = len(x)
            stats = {}

            for name in filters_to_run:
                q.put(('start', name))
                prev_len = len(x)
                if name == 'hot':
                    x, y, t, p, threshold, num_validated = CleaningData.Hot_Pixel_Filter(x, y, t, p, state.max_x, state.max_y, percentile=state.hot_pixel_threshold)
                else:
                    threshold = None
                    num_validated = None
                if name == 'voxel':
                    x, y, t, p = CleaningData.Voxel_Activity_Filter(x, y, t, p, spatial_window=state.voxel_activity_spatial_window, time_window=state.voxel_activity_time_window)
                # (Neighbor Activity Filter removed)
                elif name == 'density':
                    x, y, t, p = CleaningData.Voxel_Density_Filter(x, y, t, p, percentile=state.density_percentile, alpha=state.density_alpha)
                elif name == 'median':
                    x, y, t, p = CleaningData.Median_Filter(x, y, t, p, spatial_window=state.median_spatial_window, time_window=state.median_time_window)

                removed = prev_len - len(x)
                pct = (removed / events_before * 100) if events_before > 0 else 0.0
                stats[name] = (removed, pct, threshold, num_validated)
                q.put(('done', name, removed, pct, threshold, num_validated))

            # final result
            q.put(('finished', x, y, t, p, stats))
        except Exception as e:
            q.put(('error', str(e)))

    def poll_progress():
        try:
            while True:
                msg = progress_queue.get_nowait()
                typ = msg[0]
                if typ == 'start':
                    name = msg[1]
                    ind = indicator_map.get(name)
                    if ind:
                        animate_spinner(ind)
                elif typ == 'done':
                    name, removed, pct = msg[1], msg[2], msg[3]
                    ind = indicator_map.get(name)
                    if ind:
                        stop_spinner(ind)
                        ind.config(text='✔', fg='green')
                    # update per-filter stats in UI
                    if name == 'hot':
                        # For 'hot', the queue message now includes threshold and num_validated
                        threshold = msg[4]
                        num_validated = msg[5]
                        rounded_threshold = round(threshold, 1) if threshold is not None else None
                        state.hot_pixel_removed = removed
                        state.hot_pixel_percentage = pct
                        state.hot_pixel_threshold_display = rounded_threshold
                        state.hot_pixel_validated = num_validated
                        hot_pixel_stats.config(
                            text=f"Hot Pixel: {removed:,} events removed ({pct:.1f}%) | Threshold: {rounded_threshold if rounded_threshold is not None else '—'} | Hot Pixel found: {num_validated if num_validated is not None else '—'}",
                            fg="black"
                        )
                        state.hot_pixel_filter_applied = True
                    elif name == 'voxel':
                        state.voxel_activity_removed = removed
                        state.voxel_activity_percentage = pct
                        voxel_activity_stats.config(text=f"Voxel Activity: {removed:,} events removed ({pct:.1f}%)", fg="black")
                        state.voxel_activity_filter_applied = True
                    # (Neighbor Activity Filter removed)
                    elif name == 'density':
                        state.density_removed = removed
                        state.density_percentage = pct
                        density_stats.config(text=f"Voxel Density: {removed:,} events removed ({pct:.1f}%)", fg="black")
                        state.density_filter_applied = True
                    elif name == 'median':
                        state.median_removed = removed
                        state.median_percentage = pct
                        median_stats.config(text=f"Median: {removed:,} events removed ({pct:.1f}%)", fg="black")
                        state.median_filter_applied = True

                elif typ == 'finished':
                    x, y, t, p, stats = msg[1], msg[2], msg[3], msg[4], msg[5]
                    # save cleaned data to state
                    state.x_values = x
                    state.y_values = y
                    state.t_values = t
                    state.p_values = p

                    # compute totals
                    events_before = len(state.raw_x) if state.raw_x is not None else 0
                    total_removed = sum(v[0] for v in stats.values())
                    total_pct = (total_removed / events_before * 100) if events_before > 0 else 0.0
                    state.total_removed = total_removed
                    state.total_percentage = total_pct
                    remaining = events_before - total_removed

                    total_label.config(fg="black")
                    total_removed_label.config(text=f" {total_removed:,} events removed ({total_pct:.1f}%) |", fg="black")
                    remaining_bold_label.config(fg="black")
                    remaining_info_label.config(text=f" {remaining:,} events", fg="black")

                    cleaning_status.config(text="Cleaning applied successfully.", fg="green")
                    # re-enable Apply button only
                    clean_btn.config(state="normal")

                elif typ == 'error':
                    err = msg[1]
                    # stop all spinners
                    for ind in indicator_map.values():
                        stop_spinner(ind)
                    cleaning_status.config(text=f"Cleaning error: {err}", fg="red")
                    # re-enable Apply button only
                    clean_btn.config(state="normal")

        except queue.Empty:
            pass
        finally:
            # continue polling while worker may be running
            viz_root.after(120, poll_progress)

    def apply_cleaning():
        # Start cleaning in background worker (non-blocking)
        if state.raw_x is None:
            cleaning_status.config(text="No data loaded to clean.", fg="red")
            return

        # Reset hot pixel stats before cleaning
        state.hot_pixel_threshold_display = None
        state.hot_pixel_validated = None

        # Collect selected filters in order
        filters = []
        if hot_pixel_var.get():
            filters.append('hot')
        if voxel_activity_var.get():
            filters.append('voxel')
        # (Neighbor Activity Filter removed)
        if density_var.get():
            filters.append('density')
        if median_var.get():
            filters.append('median')

        if not filters:
            cleaning_status.config(text="Warning: No cleaning filters selected. Please select at least one filter.", fg="orange")
            return

        # Reset per-filter state and UI hints
        state.hot_pixel_filter_applied = False
        state.voxel_activity_filter_applied = False
        # (Neighbor Activity Filter removed)
        state.density_filter_applied = False
        state.median_filter_applied = False

        state.hot_pixel_removed = 0
        state.hot_pixel_percentage = 0.0
        state.voxel_activity_removed = 0
        state.voxel_activity_percentage = 0.0
        # (Neighbor Activity Filter removed)
        state.density_removed = 0
        state.density_percentage = 0.0
        state.median_removed = 0
        state.median_percentage = 0.0

        hot_pixel_stats.config(text="Hot Pixel: — events (—%)", fg="gray")
        voxel_activity_stats.config(text="Voxel Activity: — events (—%)", fg="gray")
        # (Neighbor Activity Filter removed)
        density_stats.config(text="Voxel Density: — events (—%)", fg="gray")
        median_stats.config(text="Median: — events (—%)", fg="gray")

        for ind in indicator_map.values():
            ind.config(text=' ', fg='black')

        # Disable only the Apply button while background job runs
        clean_btn.config(state="disabled")

        cleaning_status.config(text="Cleaning started...", fg="black")

        # Submit worker
        executor.submit(cleaning_worker, filters, progress_queue)
        # Start polling the queue for UI updates
        viz_root.after(120, poll_progress)

    # Button container frame for centering - similar to visualization buttons
    button_container = tk.Frame(filters_frame)
    button_container.pack(pady=(6, 0))

    def reset_filters():
        # Reset state.x/y/t/p to raw values
        state.x_values = state.raw_x.copy() if state.raw_x is not None else None
        state.y_values = state.raw_y.copy() if state.raw_y is not None else None
        state.t_values = state.raw_t.copy() if state.raw_t is not None else None
        state.p_values = state.raw_p.copy() if state.raw_p is not None else None
        # Uncheck all filter checkboxes
        hot_pixel_var.set(False)
        voxel_activity_var.set(False)
        # (Neighbor Activity Filter removed)
        density_var.set(False)
        median_var.set(False)
        # Reset UI indicators and stats
        for ind in indicator_map.values():
            ind.config(text=' ', fg='black')
        hot_pixel_stats.config(text="Hot Pixel: — events (—%)", fg="gray")
        voxel_activity_stats.config(text="Voxel Activity: — events (—%)", fg="gray")
        # (Neighbor Activity Filter removed)
        density_stats.config(text="Voxel Density: — events (—%)", fg="gray")
        median_stats.config(text="Median: — events (—%)", fg="gray")
        total_label.config(fg="gray")
        total_removed_label.config(text=" — events removed (—%) |", fg="gray")
        remaining_bold_label.config(fg="gray")
        remaining_info_label.config(text=" — events", fg="gray")
        cleaning_status.config(text="Filters reset. Data restored to raw values.", fg="green")
        # Optionally reset filter-applied state
        state.hot_pixel_filter_applied = False
        state.voxel_activity_filter_applied = False
        # (Neighbor Activity Filter removed)
        state.density_filter_applied = False
        state.median_filter_applied = False

    reset_btn = tk.Button(
        button_container,
        text="Reset Filters",
        width=14,
        command=reset_filters
    )
    reset_btn.pack(side="left", padx=6)

    clean_btn = tk.Button(
        button_container,
        text="Apply Cleaning",
        width=18,
        command=apply_cleaning
    )
    clean_btn.pack(side="left", padx=6)

    clean_btn.bind("<ButtonPress-1>", lambda e: cleaning_status.config(text="", fg="black"))


    # Button to open parameter tuning window
    tune_params_btn = tk.Button(
        button_container,
        text="Tune Parameters",
        width=14,
        command=lambda: create_parameter_tuning_window(viz_root, state)
    )
    tune_params_btn.pack(side="left", padx=6)

    # Export Data button (placed in lower right corner of cleaning box)
    def on_export_data():
        def run_export():
            try:
                result = ExportingData.export_clean_data(state, parent=viz_root)
                if result:
                    viz_root.after(0, lambda: cleaning_status.config(text="Cleaned data exported: This process might take some time!", fg="blue"))
            except Exception as e:
                import tkinter.messagebox as mb
                viz_root.after(0, lambda: mb.showerror("Export Error", str(e)))
        threading.Thread(target=run_export, daemon=True).start()

    export_data_btn = tk.Button(
        filters_frame,
        text="Export Data",
        width=16,
        command=on_export_data
    )
    export_data_btn.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)

    # ---------------- VISUALIZATION OPTIONS SECTION ----------------#
    viz_frame = tk.LabelFrame(
        content_frame,
        text="Visualizations",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    viz_frame.pack(pady=6, fill="x", padx=20)

    # Helper function to validate state and open visualization windows
    def validate_and_open_viz(create_window_func):
        if state.x_values is None or state.y_values is None or state.t_values is None or state.p_values is None:
            viz_status.config(text="No data loaded. Please load data first.", fg="red")
            return
        viz_status.config(text="", fg="black")  # Clear any previous messages
        create_window_func(viz_root, state, None)

    def open_frame_video():
        # Only allow video if x_values is under 10 million events
        if state.x_values is None or len(state.x_values) >= 10_000_000:
            viz_status.config(text="File too large (> 10M events): Apply more filters", fg="red")
            return
        create_frame_video_window(viz_root, state, viz_status)

    # Regrouped visualization buttons: Frame, 3D, Voxel
    viz_btns_frame = tk.Frame(viz_frame)
    viz_btns_frame.pack(pady=2, fill="x")

    # Use grid for equal spacing (no barrier columns)
    viz_btns_frame.grid_columnconfigure(0, weight=1)
    viz_btns_frame.grid_columnconfigure(1, weight=1)
    viz_btns_frame.grid_columnconfigure(2, weight=1)

    # Frame box
    frame_box = tk.LabelFrame(viz_btns_frame, text="Frame", font=("Arial", 10, "bold"), padx=8, pady=8, bd=2, relief="ridge")
    frame_box.grid(row=0, column=0, sticky="nsew", padx=(0, 0), pady=0)
    tk.Button(frame_box, text="Linear Visual", width=20, command=lambda: validate_and_open_viz(create_frame_visualization_window)).pack(pady=4)
    tk.Button(frame_box, text="Lognormal Visual", width=20, command=lambda: validate_and_open_viz(create_lognormal_frame_visualization_window)).pack(pady=4)
    tk.Button(frame_box, text="Frame Video", width=20, command=open_frame_video).pack(pady=4)

    # 3D box
    box_3d = tk.LabelFrame(viz_btns_frame, text="3D", font=("Arial", 10, "bold"), padx=8, pady=8, bd=2, relief="ridge")
    box_3d.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
    tk.Button(box_3d, text="Linear Visual", width=20, command=lambda: validate_and_open_viz(create_3d_visualization_window)).pack(pady=12)

    # Voxel box
    voxel_box = tk.LabelFrame(viz_btns_frame, text="Voxel", font=("Arial", 10, "bold"), padx=8, pady=8, bd=2, relief="ridge")
    voxel_box.grid(row=0, column=2, sticky="nsew", padx=(0, 0), pady=0)
    tk.Button(voxel_box, text="Linear Visual", width=20, command=lambda: validate_and_open_viz(create_voxel_visualization_window)).pack(pady=12)

    # Status label for visualizations (moved below the boxes)
    viz_status = tk.Label(viz_frame, text="", font=("Arial", 9))
    viz_status.pack(pady=(8, 0))

    def load_new_file(viz_root):
        """Close all windows, reset state, and restart with loading window."""
        # Close all Toplevel windows (visualization windows)
        for widget in viz_root.winfo_children():
            if isinstance(widget, tk.Toplevel):
                widget.destroy()
        # Also explicitly close any remaining Toplevel windows
        for widget in tk.Tk.winfo_toplevel(viz_root).winfo_children():
            try:
                if isinstance(widget, tk.Toplevel):
                    widget.destroy()
            except:
                pass

        # Close the main Event Visualization window
        viz_root.destroy()

        # Reset application state
        reset_for_new_file(state)

        # Create and show the loading window
        root = setup_loading_window(state)
        root.mainloop()

    # Load new file button - centered at the bottom
    load_new_file_frame = tk.Frame(content_frame)
    load_new_file_frame.pack(pady=10, fill="x")

    load_new_file_btn = tk.Button(
        load_new_file_frame,
        text="Load New File",
        width=20,
        height=1,
        command=lambda: load_new_file(viz_root)
    )
    load_new_file_btn.pack()

    # keep the Event Visualization window running
    viz_root.mainloop()


"--------------------------------------------------------------------------------------------------------------------------------------"
"          LOADING WINDOW CODE BELOW - OPENS EVENT VISUALIZATION WINDOW ON SUCCESSFUL LOAD                                             "                            
"--------------------------------------------------------------------------------------------------------------------------------------"

def setup_loading_window(state):
    """Create and return the Loading Data window.

    Parameters:
    - state: AppState instance to populate with loaded data

    Returns:
    - root: the Tk loading window
    """
    root = tk.Tk()
    root.title("EveViz - Loading Data")
    root.geometry("500x575")

    # In-window title at the top of the GUI (separate from OS title bar)
    gui_title_label = tk.Label(root, text="EveViz", font=("Arial", 18, "bold"))
    gui_title_label.pack(pady=(10, 2))

  
    # Loading Data LabelFrame
    loading_frame = tk.LabelFrame(root, text="Loading Data", font=("Arial", 12, "bold"), padx=12, pady=10, bd=2, relief="ridge")
    loading_frame.pack(padx=15, pady=10, fill="both", expand=True)

    # Variable to store file path and type
    file_path_var = tk.StringVar()
    file_type_var = tk.StringVar()

    def browse_file():
        filepath, filetype = ld.GetFilePath_Typ()
        file_path_var.set(filepath)
        file_type_var.set(filetype)

    browse_btn = tk.Button(loading_frame, text="Browse", width=15, command=browse_file)
    browse_btn.pack(pady=5)

    # Display selected file
    file_display = tk.Entry(loading_frame, textvariable=file_path_var, width=40)
    file_display.pack(pady=5)

    # Label for type
    type_label = tk.Label(loading_frame, text="File Type:", font=("Arial", 10))
    type_label.pack()

    # Display file type
    file_type_display = tk.Entry(loading_frame, textvariable=file_type_var, width=12)
    file_type_display.pack(pady=5)

    bin_hint = tk.Label(
        loading_frame,
        text=_bin_installed_hint(),
        font=("Arial", 9),
        fg="gray" if bin_not_available else "green",
        wraplength=420,
        justify="left",
    )
    bin_hint.pack(pady=(0, 6), anchor="w")

    def select_loader():
        filepath = file_path_var.get()
        filetype = file_type_var.get()

        try:
            if filetype == "csv":
                state.x_values, state.y_values, state.t_values, state.p_values = ld.Load_CsvData(filepath)
            elif filetype == "raw":
                state.x_values, state.y_values, state.t_values, state.p_values = ld.Load_RawData(filepath)
            elif filetype == "hdf5" or filetype == "h5":
                state.x_values, state.y_values, state.t_values, state.p_values = ld.Load_Hdf5Data(filepath)
            elif filetype == "bin":
                if not ld.is_bin_converter_available():
                    status_label.config(text=_bin_not_installed_message(), fg="red")
                    return
                state.x_values, state.y_values, state.t_values, state.p_values = ld.Load_BinData(filepath)
            elif filetype == "txt":
                state.x_values, state.y_values, state.t_values, state.p_values = ld.Load_TxtData(filepath)
            else:
                status_label.config(text="Unsupported file type.", fg="red")
                return
           
            # Store filename
            state.filename = os.path.basename(filepath)
            
            # Compute axis limits for persistent scaling and raw event counts
            state.max_x, state.max_y, state.raw_total_events, state.raw_positive_events, state.raw_negative_events, state.min_t, state.max_t = ld.File_Parameters(state.x_values, state.y_values, state.p_values, state.t_values)
            
            status_label.config(text="Loading Successful", fg="green")
            
            state.raw_x = state.x_values
            state.raw_y = state.y_values
            state.raw_t = state.t_values
            state.raw_p = state.p_values
          
            # Reset filter flags
            state.hot_pixel_filter_applied = False
            state.voxel_activity_filter_applied = False
            # (Neighbor Activity Filter removed)
            state.density_filter_applied = False

            # Open Event Visualization window after successful load
            root.after(1000, lambda: open_event_visualization(root))
        except Exception as e:
            status_label.config(text=f"Error: {str(e)}", fg="red")

    # Status Label (inside the frame)
    status_label = tk.Label(loading_frame, text="", font=("Arial", 10))
    status_label.pack(pady=5)

    # Load Button (inside the frame)
    load_btn = tk.Button(loading_frame, text="Load", width=15, command=select_loader)
    load_btn.pack(pady=10)

    # Show project logo below the Loading Data box.
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "Logo.png")
    if os.path.exists(logo_path):
        try:
            if Image is not None and ImageTk is not None:
                logo_image = Image.open(logo_path)
                resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                logo_image = logo_image.resize((360, 202), resample)
                root.logo_photo = ImageTk.PhotoImage(logo_image)
            else:
                root.logo_photo = tk.PhotoImage(file=logo_path)

            logo_label = tk.Label(root, image=root.logo_photo)
            logo_label.pack(pady=(2, 8))
        except Exception:
            # Keep the loading window functional if the logo cannot be decoded.
            pass

    contributors_text = "Helena Niethammer | Luca Illig | Pablo Broders | Yael Kaliner"
    contributors_label = tk.Label(
        root,
        text=contributors_text,
        font=("Arial", 10, "italic"),
        justify="center",
        wraplength=460,
    )
    contributors_label.pack(pady=(0, 10))

    return root


def main():
    """Main orchestrator: create the shared state and start the loading window."""
    # The shared state is already created as module-level `state`
    # Start with the loading window
    root = setup_loading_window(state)
    root.mainloop()


if __name__ == "__main__":
    main()