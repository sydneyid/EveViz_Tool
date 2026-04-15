# EveViz - GUI

---
## Description
EveViz is the main Python GUI for this project. It combines data loading, filter configuration, visualization, and export actions in a single workflow for event-based sensor recordings.

The application is organized into a small set of windows that guide the user from loading a file to inspecting and exporting the processed result. The windows are listed below, followed by a general overview of what they provide.

### Windows
- Loading Data Window
- Event Visualization Window
- Filter Parameter Tuning Window
- Frame Visualization Window
- Lognormal Frame Visualization Window
- Frame Video Window
- 3D Visualization Window
- Voxel Visualization Window

### General Workflow
1. Load a supported event file in the Loading Data window.
2. Get an overview of the loaded data and apply cleaning filters in the Event Visualization window.
3. Open one of the visualization windows to inspect the filtered or unfiltered event stream.
4. Export reports, plots, videos, or cleaned event data when needed.

The GUI is intentionally centered around the current recording state. Loaded data, selected filters, and export options are shared across the visualization windows so the user can move between them without reloading the file.

---
## Window Overview

### Loading Data Window
This is the entry point of the application. It allows file selection, type detection, and conversion of different source formats into the unified event representation used across EveViz.

What happens in this window:
- File selection via browse dialog
- Automatic loader routing based on extension
- Initial metadata extraction (event count, polarity split, recording length, sensor bounds)
- Transfer of loaded arrays into shared app state

Detailed loading behavior, supported formats, and dependency notes are documented in:
- [Loading Data](LoadingData_ReadMe.md)


### Event Visualization Window
This is the central control hub after loading. It provides dataset context, filter selection, filter execution, statistics, and routing to visualization/export actions.

What this window provides:
- Recording overview (filename, duration, total/positive/negative counts)
- Cleaning filter selection and execution pipeline
- Live filter statistics (per filter and total removed events)
- Access to parameter tuning
- Launch buttons for frame, lognormal frame, voxel, 3D, and frame-video windows
- Export actions (cleaned data export and report export)

For cleaning logic and filter theory, see:
- [Cleaning Data](CleaningData_ReadMe.md)

For visualization behavior and plotting details, see:
- [Visualization](Visualization_ReadMe.md)

For reporting/export actions from this window, see:
- [Exporting Data - Save Report](ExportingData_ReadMe.md#save-report)
- [Exporting Data - Export HDF5 TXT BIN](ExportingData_ReadMe.md#export-hdf5txtbin)

### Filter Parameter Tuning Window
This window is used to adjust the active numeric parameters for filtering before running cleaning.

Typical tuned parameters include threshold values and spatial/temporal windows used by the selected filters. Parameter choices directly influence event retention and denoising strength. The window displays default values and recommended ranges directly next to the adjustable parameters.

Background and effect of parameter changes are documented in:
- [Cleaning Data](CleaningData_ReadMe.md)

### Frame Visualization Window
This window provides linear 2D event plots and is intended for quick spatial inspection.

What this window offers:
- Event mode switching (positive, negative, total, both)
- Time range selection for focused inspection
- Compare functionality offers comparison of raw vs cleaned data
- Embedded plotting and direct image export

Detailed behavior and method-level overview:
- [Visualization - EventFrameVisualization](Visualization_ReadMe.md#eventframevisualization)
- [Exporting Data - Save Image](ExportingData_ReadMe.md#save-image)

### Lognormal Frame Visualization Window
This window provides accumulated frame rendering with logarithmic scaling. It is useful when event activity is highly non-uniform and linear scatter views hide lower-density structures.

What this window offers:
- Log-scaled accumulated rendering for high dynamic range event density
- Event mode switching (positive, negative, both)
- Time range selection for accumulation interval
- Compare functionality offers comparison of raw vs cleaned data
- Embedded plotting and direct image export

Detailed plotting concepts are covered in:
- [Visualization - Accumulated Frame Visualization](Visualization_ReadMe.md#accumulated-frame-visualization)
- [Exporting Data - Save Image](ExportingData_ReadMe.md#save-image)

### Frame Video Window
This window provides animated playback of the event stream over time. It is optimized for temporal understanding and playback-like inspection.

What this window offers:
- Real-time animation behavior based on event timestamps
- Playback controls and timeline interaction
- Screenshot and MP4 export options

Detailed animation behavior and constraints:
- [Visualization - Frame Video Visualization](Visualization_ReadMe.md#frame-video-visualization)
- [Exporting Data - Save Video](ExportingData_ReadMe.md#save-video)
- [Exporting Data - Save Image](ExportingData_ReadMe.md#save-image)

### 3D Visualization Window
This window renders event points in 3D, where time is represented as one axis. It is intended for spatio-temporal inspection of event evolution.

What this window offers:
- Spatio-temporal rendering with time as a dedicated axis
- Event mode switching (positive, negative, total, both)
- Time range selection for focused inspection
- Compare functionality offers comparison of raw vs cleaned data
- Embedded plotting and direct image export

Detailed method-level description:
- [Visualization - Event3DVisualization](Visualization_ReadMe.md#event3dvisualization)
- [Exporting Data - Save Image](ExportingData_ReadMe.md#save-image)

### Voxel Visualization Window
This window displays a voxelized 3D representation of event streams by discretizing time into bins and combining spatial and temporal structure.

What this window offers:
- Voxelized spatio-temporal rendering for sparse vs dense structure analysis
- Event mode switching (positive, negative, total, both)
- Time range selection for focused inspection
- Compare functionality offers comparison of raw vs cleaned data
- Embedded plotting and direct image export

Detailed implementation notes:
- [Visualization - EventVoxelVisualization](Visualization_ReadMe.md#eventvoxelvisualization)
- [Exporting Data - Save Image](ExportingData_ReadMe.md#save-image)

---
## Functional Overview
EveViz is designed to support the full event-visualization workflow without forcing the user to switch tools.

### Loading and State Management
The app loads event recordings from supported file types and stores them in a shared application state used by all subsequent windows. This allows seamless transitions between filtering, plotting, and exporting without reloading the input.

Detailed references:
- [Loading Data](LoadingData_ReadMe.md)

### Safety Features
EveViz includes built-in safeguards to prevent invalid operations and make the workflow more robust during interactive use.

Current safety features include:
- Input validation for missing or invalid values (for example, time range and filter inputs)
- State checks that block actions when required data is not loaded yet
- Warning/status feedback when filters are not selected or when compare data is unavailable
- Dependency checks for optional external components used by specific file formats or export targets
- Reset and fallback behavior to return from filtered data to raw data when needed

Detailed references:
- [Loading Data](LoadingData_ReadMe.md)
- [Cleaning Data](CleaningData_ReadMe.md)
- [Exporting Data](ExportingData_ReadMe.md)

### Time Range Selection
Time range selection is performed in the visualization windows and determines which segment of the event stream is rendered. This supports focused inspection, faster plotting on large recordings, and better comparability across views. To further enhance comparability the currently stored time range will be proposed in all visualisation windows.

Detailed references:
- [Visualization Module Overview](Visualization_ReadMe.md#overview)

### Cleaning Filters
Cleaning is configured from the main Event Visualization window and executed as a processing pipeline on the loaded event stream. Filter outputs replace the currently active arrays used by all visualization and export windows.

Current GUI-oriented cleaning workflow:
- Select one or multiple filters
- Optionally tune parameters
- Apply cleaning and inspect per-filter statistics
- Reset to raw data if needed

Detailed references:
- [Cleaning Data](CleaningData_ReadMe.md)
- [Cleaning Data - Overview of Filters](CleaningData_ReadMe.md#overview-of-filters)

### Visualization Modes
The visualization windows provide complementary perspectives on the same active event arrays:
- 2D frame-based views for quick spatial inspection
- log-scaled frame views for dense event regions
- 3D views for spatial-temporal inspection
- voxel-style views for structured event analysis
- animated frame playback for time-based review

Detailed references:
- [Visualization Readme](Visualization_ReadMe.md)
- [Visualization - EventFrameVisualization](Visualization_ReadMe.md#eventframevisualization)
- [Visualization - Event3DVisualization](Visualization_ReadMe.md#event3dvisualization)
- [Visualization - EventVoxelVisualization](Visualization_ReadMe.md#eventvoxelvisualization)
- [Visualization - Frame Video Visualization](Visualization_ReadMe.md#frame-video-visualization)

### Export and Reporting
Export is available from the main control window and visualization windows depending on output type. This includes cleaned dataset export, static plot export, frame screenshot export, video export, and report generation.

Detailed references:
- [Exporting Data](ExportingData_ReadMe.md)
