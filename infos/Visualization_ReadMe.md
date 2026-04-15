# Event Visualization Module (2D, 3D & Voxel)

## Overview
This module provides visualization tools for event-based data using:
- **2D spatial visualization**
- **2D accumulated visualization**
- **3D spatio-temporal visualization**
- **Voxel-based representation**

It enables analysis of event streams using:
- spatial coordinates `(x, y)`
- timestamps `(t)`
- polarity `(p)`

## Remarks
- The visualizations (except frame video) show only events within the selected time window
  - time window recommendations are shown under specific classes
---

# EventFrameVisualization

## Overview
`EventFrameVisualization` is a utility class for visualizing event-based data in 2D.  
It is designed for datasets containing spatial coordinates `(x, y)`, timestamps `(t)`, and polarity `(p)`.

The class provides:
- Static 2D scatter plots
- Accumulated frame visualizations
- Real-time animation of event streams
### Displayed Structure

- every class x axis with displayed x values from 0 to x_max 
- and y axis with displayed y values from y_max to 0
---
## Linear Frame Visualization
Events are displayed as scatter points (red, blue, or grey depending on polarity) in linear frame visualization.
- **time window recommendation:** 0 s to 1 s

### plot_positive_event()
- filters events where p = 1 (positive events, with increasing brightness)
- displays them as red points
### plot_negative_event()
- filters events where p = 0 (negative events, with decreasing brightness)
- displays them as blue points
### plot_total_event()
- displays all events without polarity distinction 
- uses grey color to display events
### plot_both_event()
- displays all events with distinction between positive and negative
  - positive (p = 1) displayed as red points
  - negative (p = 0) displayed as blue points
- includes legend for clarity 
---
## Accumulated Frame Visualization
These methods convert events into a frame-like heatmap by counting events per pixel and uses logarithmic scaling for better contrast
- **time window recommendation:** 0 to 10 s (larger time window for lognormal representation)
### plot_postive_event_accumulated_frame()
- accumulates only positive events
### plot_negative_event_accumulated_frame
- accumulates only negative events
### plot_both_event_accumulated_frame
- accumulates all events regardless of polarity

---
# Frame Video Visualization

## Important!

- video function requires fewer than 10 million events
- user needs to apply filters to reduce the count as needed
- required filters depend on the file; if basic filtering is insufficient, tune the parameters
- for easy, strong tuning, decrease the spatial and temporal window of the Voxel Activity Filter


## Description

`animate_frame_video()` visualizes event-camera data `(x, y, t, p)` as a real-time animation.

The animation is **clock-driven**, meaning playback follows **real elapsed (wall-clock) time** instead of stepping through frames.  
This ensures **accurate timing** and prevents temporal drift.


## Key Features

### True Real-Time Playback
- Playback synchronized with **wall-clock time**
- No artificial frame stepping → **no temporal distortion**
- Automatically skips frames if rendering is too slow to stay in sync


### Event-Based Visualization
- Converts asynchronous events into a continuous visual stream
- Displays events using a **single Matplotlib scatter plot**
- Dynamically selects visible events based on current playback time


### Visualization Modes

| Mode       | Description                      | Color |
|------------|----------------------------------|-------|
| `"positive"` | Positive polarity events only     | Red   |
| `"negative"` | Negative polarity events only     | Blue  |
| `"both"`     | Positive and negative events      | Red & Blue |
| `"all"`      | All events (no polarity split)    | Gray  |

---

### Interactive Controls

| Control     | Function |
|------------|---------|
| `pause()`   | Stops playback while preserving current position |
| `resume()`  | Continues playback from current position |
| Progress Bar | Click or drag to seek through the timeline |


## Notes

- `t_values` must be in **microseconds**
- Events are automatically **sorted by timestamp**
- Uses a **single scatter object** for efficient updates
- Playback starts at `t_start + start_offset_us` (if specified)


## Summary

A lightweight, real-time event visualization tool that preserves **true temporal behavior** using wall-clock synchronization, while remaining **interactive, efficient, and easy to integrate into GUI applications**.

---
# Event3DVisualization

## Overview
`Event3DVisualization` is a utility class for visualizing event-based data in **3D space**.  
It extends traditional 2D visualization by incorporating **time as a third dimension**, enabling spatio-temporal analysis of events.
- **time window recommendation:** 0 s to 1 s

The visualization uses:
- X → spatial horizontal position  
- Y → spatial vertical position  
- Time → represented as the third axis  
### plot_positive_event_3d()
- filters events where p = 1 (positive events, with increasing brightness)
- displays them as red points
### plot_negative_event_3d()
- filters events where p = 0 (negative events, with decreasing brightness)
- displays them as blue points
### plot_total_event_3d()
- displays all events without polarity distinction 
- uses grey color to display events
### plot_both_event_3d()
- displays all events with distinction between positive and negative
  - positive (p = 1) displayed as red points
  - negative (p = 0) displayed as blue points
- includes legend for clarity 

---
# EventVoxelVisualization

## Overview
`EventVoxelVisualization` is a utility class for converting event-based data into a **voxel grid representation** and visualizing it in 3D.

It transforms asynchronous event streams `(x, y, t, p)` into a structured format: 
(x, y, t, p) → voxel grid → 3D scatter plot

The voxel grid captures **spatial and temporal structure** by discretizing time into bins.
- **time window recommendation:** 0 s to 1 s

### _infer_hw()
- infers the spatial resolution (height and width) from input event data.
- returns H and W
- How it works:finds maximum x and y values and adds 1 to determine grid size

### events_to_voxel_grid()
- core function that converts event data into a **voxel grid**.
#### How it works
1. Filters events within time window  
2. Validates spatial bounds  
3. Normalizes time into bins: tau = (t - t_start) / t_duration * (B - 1)
4. Assigns polarity channel:
   - 0 → negative
   - 1 → positive
5. Accumulates events:
   - With interpolation → distributes across bins  
   - Without interpolation → assigns to nearest bin  

### _points_from_channel()
- extracts coordinates of active voxels above a threshold.
- Uses `np.where()` to find non-zero voxels
- Converts voxel indices into scatter plot points

### _voxel_from_events()
- Convenience wrapper that:
  1. Infers spatial resolution  
  2. Calls voxelization  
- returns: voxel grid `(2, B, H, W)`

## Plotting Functions
These functions are designed for direct use in GUI

### plot_positive_event_voxel()
- plots only **positive polarity voxels**
- color: red  
- uses only positive channel 

### plot_negative_event_voxel()
- plots only **negative polarity voxels**
- color: blue  
- uses only negative channel  

### plot_total_event_voxel()
- plots all voxels without polarity distinction
- combines both channels  
- color: grey

### plot_both_events_voxel()
- plots both positive and negative voxels
- Positive → red  
- Negative → blue  
- Includes legend  

## Internal Plotting Function
### _plot_voxel()
1. Creates or uses provided 3D axis  
2. Generates voxel grid  
3. Extracts voxel points  
4. Plots using `ax.scatter()` 

## Visualization Details

- Axes:
  - X → spatial X  
  - Y → time bin  
  - Z → spatial Y

## Limitations
- large voxel grids may consume memory 
- high bin counts increase computation time 
- visualization may become sparse or dense depending on threshold

---
## Summary
- picture of Visualization window?
