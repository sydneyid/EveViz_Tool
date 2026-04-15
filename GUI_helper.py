import tkinter as tk

def reset_for_new_file(state):
    """Reset all state variables to prepare for loading a new file."""
    # Clear data
    state.raw_x = None
    state.raw_y = None
    state.raw_t = None
    state.raw_p = None
    state.x_values = None
    state.y_values = None
    state.t_values = None
    state.p_values = None

    # Reset time range
    state.start_time_us = None
    state.duration_us = None
    state.start_time_unit = ""
    state.duration_unit = ""

    # Reset axis limits
    state.max_x = None
    state.max_y = None
    state.min_t = None
    state.max_t = None

    # Reset filter flags
    state.hot_pixel_filter_applied = False
    state.voxel_activity_filter_applied = False
    state.density_filter_applied = False
    state.median_filter_applied = False

    # Reset file information
    state.filename = None
    state.raw_total_events = None
    state.raw_positive_events = None
    state.raw_negative_events = None

    # Reset filter statistics
    state.hot_pixel_removed = 0
    state.hot_pixel_percentage = 0.0
    state.hot_pixel_threshold_display = None
    state.hot_pixel_validated = None
    state.voxel_activity_removed = 0
    state.voxel_activity_percentage = 0.0
    state.density_removed = 0
    state.density_percentage = 0.0
    state.median_removed = 0
    state.median_percentage = 0.0
    state.total_removed = 0
    state.total_percentage = 0.0

def truncate_message(text, max_length=50):
    """Truncate long messages with ellipsis if needed"""
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

def setup_time_range_section(parent, state, start_value="", start_unit="", duration_value="", duration_unit=""):
    """
    Sets up the Time Range input section in the given parent frame.
    Handles labels, entries, unit menus, status label, and the Set Time Range button.
    Updates the state object directly.
    Returns a dict of created widgets/variables for further use.
    """
    time_range_frame = tk.LabelFrame(
        parent,
        text="Time Range",
        font=("Arial", 11, "bold"),
        padx=10,
        pady=8
    )
    time_range_frame.pack(pady=(0, 10), fill="x")

    # Start Time label row
    start_label_row = tk.Frame(time_range_frame)
    start_label_row.pack(pady=(2,0), fill="x")
    start_label = tk.Label(start_label_row, text="Start Time:", font=("Arial", 10))
    start_label.pack(anchor="w")
    # Start Time input row
    start_input_row = tk.Frame(time_range_frame)
    start_input_row.pack(pady=(0,2), fill="x")
    start_var = tk.StringVar(value=start_value)
    start_entry = tk.Entry(start_input_row, textvariable=start_var, width=7)
    start_entry.pack(side="left", padx=(0, 4))
    start_unit_var = tk.StringVar(value=start_unit)
    start_unit_menu = tk.OptionMenu(start_input_row, start_unit_var, "µs", "ms", "s")
    start_unit_menu.config(width=4)
    start_unit_menu.pack(side="left")

    # Duration label row
    dur_label_row = tk.Frame(time_range_frame)
    dur_label_row.pack(pady=(2,0), fill="x")
    dur_label = tk.Label(dur_label_row, text="Time Duration:", font=("Arial", 10))
    dur_label.pack(anchor="w")
    # Duration input row
    dur_input_row = tk.Frame(time_range_frame)
    dur_input_row.pack(pady=(0,2), fill="x")
    dur_var = tk.StringVar(value=duration_value)
    dur_entry = tk.Entry(dur_input_row, textvariable=dur_var, width=7)
    dur_entry.pack(side="left", padx=(0, 4))
    dur_unit_var = tk.StringVar(value=duration_unit)
    dur_unit_menu = tk.OptionMenu(dur_input_row, dur_unit_var, "µs", "ms", "s")
    dur_unit_menu.config(width=4)
    dur_unit_menu.pack(side="left")

    # Status label for time range
    time_status_local = tk.Label(time_range_frame, text="", font=("Arial", 9))
    time_status_local.pack(pady=(4,6))

    def set_time_range_local():
        s = start_var.get().strip()
        d = dur_var.get().strip()
        s_unit = start_unit_var.get().strip()
        d_unit = dur_unit_var.get().strip()

        # Set to None on any invalid input
        def set_none():
            if state is not None:
                state.start_time_us = None
                state.duration_us = None

        if s == "" or d == "":
            set_none()
            time_status_local.config(text="Invalid input", fg="red")
            return
        if s_unit == "" or d_unit == "":
            set_none()
            time_status_local.config(text="Missing unit", fg="red")
            return
        try:
            s_val = float(s)
            d_val = float(d)
            if s_val < 0 or d_val < 0:
                set_none()
                time_status_local.config(text="Invalid input", fg="red")
                return
            unit_factor = {"µs": 1, "ms": 1_000, "s": 1_000_000}
            if state is not None:
                state.start_time_us = s_val * unit_factor[s_unit]
                state.duration_us = d_val * unit_factor[d_unit]
                # Store last-used units
                state.start_time_unit = s_unit
                state.duration_unit = d_unit
            time_status_local.config(
                text="Time range set",
                fg="green"
            )
        except ValueError:
            set_none()
            time_status_local.config(
                text="Invalid input",
                fg="red"
            )

    set_btn = tk.Button(
        time_range_frame,
        text="Set Time Range",
        width=16,
        command=set_time_range_local
    )
    set_btn.pack(pady=(0,8))

    return {
        "frame": time_range_frame,
        "start_var": start_var,
        "start_unit_var": start_unit_var,
        "dur_var": dur_var,
        "dur_unit_var": dur_unit_var,
        "status_label": time_status_local,
        "set_btn": set_btn
    }
