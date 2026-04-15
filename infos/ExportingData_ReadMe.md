# Exporting Data

---
## Description
This module contains the class `ExportingData`, which provides helper functions to:
- export visualizations as static images (PNG, JPEG, PDF),
- save video frames and recordings as MP4 files,
- generate analysis reports,
- and export filtered event data in multiple formats (HDF5, TXT, BIN).

All export functions automatically generate descriptive filenames and support GUI-based file selection via tkinter dialogs.

The exported data maintains full compatibility with the original event camera format:

- **Images**: High-resolution exports at 200 DPI for publication quality
- **Videos**: Preserves exact timing and duration of event recordings
- **Data files**: Maintains consistent standard file structure
- **Metadata**: Automatically includes filter information and timestamps in filenames

All functions provide user feedback through status labels showing success or error messages.

---
## Save Image

### Overview
The save image functions allow you to export the current visualization as a static image file. Two functions are available based on your visualization context:
- **`save_plot`**: Saves individual analysis plots (frame, 3D, voxel, lognormal)
- **`save_screenshot`**: Saves video frame screenshots with timestamp

### Key Features

#### Automatic Filename Generation
Both functions generate descriptive filenames automatically based on:
- **Original file name**: The name of the input event camera recording
- **Source/type**: Indicates which visualization type was saved
  - `frame` → 2D Frame visualization
  - `3d` → 3D visualization
  - `voxel` → Voxel visualization
  - `lognormal_frame` → Lognormal frame visualization
  - `video` → Video frame screenshot
- **Applied filters**: Which filters were active during export
  - `HP` → Hot Pixel Filter
  - `VA` → Voxel Activity Filter
  - `VD` → Voxel Density Filter
  - `ME` → Median Filter
- **Time information**: Timestamp or time range of the saved data

#### Generated Filename Format
```
{original_name}_{source}_{filters}_{time_range}.{extension}
```

Example:
```
Berlin15DegMin_120FPS_frame_cleaned_HP_ME_time_range_0ms_500ms.png
```

#### File Format Support
Both functions support multiple export formats:
- **PNG** (default, highest quality)
- **JPEG** (compressed)
- **PDF** (vector format)

---

## Save Video
### Description
The `save_video` function exports event camera data as an `.mp4` video using **Matplotlib + ffmpeg**.  

The function is optimized for performance and preserves the **exact original recording duration**.

### Core Idea
Efficient frame slicing using precomputed time indices (`searchsorted`) instead of per-frame event filtering.

### Key Features

#### Accurate Timing (No Time Distortion)
- Video duration exactly matches the event data  
  Uses:
- `dt = 1e6 / fps` (frame duration in µs)
- `n_frames = ceil((t1 - t0) / dt) + 1` (ensures full time coverage)


#### Efficient Frame Generation
- Events are sorted once by timestamp  
- Frame windows are precomputed using `np.searchsorted`  
- Avoids expensive per-frame masking → scalable to large datasets  


#### Automatic Filename Generation
- Based on original file name  
- Includes applied filters:
  - `HP` → Hot Pixel Filter  
  - `VA` → Voxel Activity Filter  
  - `VD` → Voxel Density Filter  
  - `ME` → Median Filter  

#### Independent Export Rendering
- Uses a separate figure (does not interfere with GUI)  
- Maintains correct sensor aspect ratio  
- Inverts y-axis to match event camera coordinates  

#### Fast Video Encoding
- Uses `ffmpeg` with `libx264`  
- Optimized with:
  - `ultrafast` preset  
  - `yuv420p` compatibility  
  - `+faststart` for better playback  


### Main Parameters

| Parameter        | Description |
|------------------|-------------|
| `x, y, t, p`     | Event data (coordinates, timestamps in µs, polarity) |
| `fps`            | Frames per second of output video |
| `persistence_us` | Time window of visible events per frame |
| `cumulative`     | If `True`, shows all past events |
| `mode`           | Visualization mode (`positive`, `negative`, `both`, `all`) |
| `marker_size`    | Size of plotted events |


### Output
- `.mp4` video file  
- Duration exactly matches input event recording  
- Visualization consistent with real-time animation logic  
---
## Save Report

### Description
The `export_report` function creates a structured report file with dataset and filter statistics from the currently loaded `file`.

The report is intended for documentation, reproducibility, and quick comparison between different filter configurations.

### Key Features

#### GUI-Based Save Dialog
- Opens a Save As dialog via tkinter
- Supports `.out` (default) and `.txt`
- Allows custom filename and location

#### Automatic Default Filename
- Uses the currently loaded file from `state.filename`
- Default pattern:
```
EV_{original_filename}.out
```

#### Camera Type Detection
Camera type is inferred from frame dimensions (`max_x + 1`, `max_y + 1`):
- `(128, 128)` -> `DVS128`
- `(240, 180)` -> `DAVIS240`
- `(346, 260)` -> `DAVIS346`
- `(640, 480)` -> `DAVIS640`
- `(1280, 720)` -> `Prophesee Gen4`
- Otherwise: `Unknown`

#### Full Filter Summary
Includes per-filter statistics when applied:
- `HP` Hot Pixel Filter
- `VA` Voxel Activity Filter
- `VD` Voxel Density Filter
- `ME` Median Filter

For each active filter, the report writes removed-event count, percentage, and the relevant filter parameters.

#### Final Aggregated Statistics
The report also includes:
- total removed events,
- total removed percentage,
- events remaining after filtering.

### Report Content Structure
The generated file contains the following sections:
- `EVENT VISUALIZATION REPORT` header
- Filename
- Camera frame and detected camera type
- Recording length (`min_t` to `max_t` in microseconds)
- Raw event counts:
  - total
  - positive
  - negative
- Filters applied and their parameter summaries
- Total removed and events remaining

### Output
- `.out` or `.txt` report file
- Human-readable, line-based summary
- Suitable for experiment logs and filter comparison
---
## Export HDF5/TXT/BIN

### Description
The export data functions save the currently filtered event stream from the loaded `file` to disk in one of three formats:
- `.hdf5` for structured dataset storage,
- `.txt` for plain-text interoperability,
- `.bin` for compressed binary export via external converter.

The entry point is `export_clean_data`, which opens a file dialog and dispatches to the correct format-specific export function.

### Key Features

#### GUI-Based Format Selection
- Uses one Save As dialog with selectable file types:
  - `HDF5 file (*.hdf5)`
  - `BIN file (*.bin)`
  - `TXT file (*.txt)`
- Default extension is `.hdf5`

#### Automatic Filename Generation
Default filename combines:
- source file base name,
- currently active filter tags (`HP`, `VA`, `DE`, `ME`) or `no_filters`.

Pattern:
```
{original_name}_{cleaned_filter_tags}
```

Example:
```
sun_sensing_panning_cleaned_HP_VA_ME.hdf5
```

### Function Overview

#### `export_clean_data(state, parent=None)`
- Opens the save dialog
- Detects selected extension
- Dispatches to:
  - `export_hdf5`
  - `export_txt`
  - `export_bin`
- Returns:
  - `True` when export is completed
  - `False` if dialog is canceled

#### `export_hdf5(state, fpath)`
Writes HDF5 datasets utilizing the h5py library:
- `x y t p`: Saved into four different unnested folders

Most efficient and reusable data type.

⚠️This function utilizes a library (`h5py`) which is only available for users having the ECF_Filter installed. [See ECF Filter installation](../README.md#ecf-filter-hdf5-plugin)

#### `export_txt(state, fpath)`
Writes comma-separated integer rows with no header in this column order:
```
x, y, p, t
```
Useful for interoperability with generic tools and external converters.

⚠️ Complete build-up might take some time depending on the array size

#### `export_bin(state, fpath)`
Binary export flow:
1. Creates a temporary `.txt` file in the target folder
2. Exports events to that temp file via `export_txt`
3. Runs external converter:
   - `Main.exe c <txtfile> <binfile>`
4. Deletes the temporary `.txt` file

Validation:
- checks that `Main.exe` is available on `PATH`
- raises an error if converter is missing or conversion fails

⚠️ This function requires the BIN converter executable (`Main.exe`) to be installed and available in your system `PATH`. [See BIN Converter installation](../README.md#event-converter-bin---required-for-loading--exporting-bin-files)



### Output
- One exported file in selected format (`.hdf5`, `.txt`, or `.bin`)
- Filename includes current filter state
- Exported content reflects currently filtered events of the loaded `file`