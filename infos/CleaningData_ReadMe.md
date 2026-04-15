# CleaningData

---
## Description
The `CleaningData` class provides multiple filtering methods to clean event-based sensor data.
Its goal is to remove noise, hot pixels, isolated events, and low-density artifacts while preserving meaningful event activity.

All methods operate on event arrays:

- x — spatial x coordinate
- y — spatial y coordinate
- t — timestamp
- p — polarity

Each filter returns cleaned versions of these arrays.

---
## Overview of Filters
The module contains several complementary filters:

| Filter                   | Purpose                              |
|--------------------------|--------------------------------------|
| Hot Pixel Filter         | Removes pixels firing excessively    |
| Voxel Activity Filter    | Removes isolated events in spacetime |
| Neighbor Activity Filter | Keeps events with nearby neighbors   |
| Subsampling Filter       | Probabilistic density-based denoising |
| Voxel Density Filter     | Probabilistic density-based denoising |
| Median Filter            | Removes events in sparsely populated voxels using a median threshold.                      |

These filters can be used individually or combined in a pipeline.
If multiple filters are selected, they are applied in the following fixed order:  

1. Hot Pixel Filter  
2. Voxel Activity Filter
3. Voxel Density Filter 
4. Median Filter 

The output of each filter is passed as input to the next, and the user cannot change this sequence.

Additionally, Neighbor Activity Filter and Subsampling Filter were removed from the GUI because they were too slow to use effectively, though they may be implemented again manually in the code.
## Hot_Pixel_Filter

### Purpose
Detects and removes hot pixels — pixels that generate an abnormally high number of events due to sensor noise or defects.

### Method
1. Builds an event count image (rate map).
2. Computes a percentile threshold (99.999 by default).
3. Pixels above the threshold are classified as hot.
4. All events from those pixels are removed.

### Key Idea
Hot pixels are statistical outliers in event rate.

### Inputs
- x_values, y_values — event coordinates
- t_values — timestamps
- p_values — polarity
- x_max, y_max — sensor resolution

### Outputs
- cleaned event arrays

### Printed Info
- threshold value
- number of hot pixels
- events before/after

---
## Voxel_Activity_Filter

### Purpose
Removes events that occur alone within a spatiotemporal voxel.

---

### Method  
1. **Quantization**  
   - Spatial coordinates `(x, y)` are grouped into coarse grids using `spatial_window`.  
   - Time `t` is grouped into bins using `time_window`.

2. **Voxel Encoding**  
   - Each event is assigned a unique voxel ID by combining `(t, y, x)` into a single integer.  
   - This allows fast sorting and grouping using vectorized operations, avoiding slower multidimensional comparisons.

3. **Sorting & Grouping**  
   - Voxel IDs are sorted so identical voxels are adjacent.  
   - Run-length encoding is used to count how many events fall into each voxel.

4. **Filtering**  
   - Voxels with only one event are considered noise.  
   - Only events in voxels with more than one event are kept.

5. **Reconstruction**  
   - The filtered mask is mapped back to the original event order.

---

### Key Idea  
Real signal tends to produce clusters in space and time,  
while noise is typically isolated.

### Tuning the Filter
- Increasing spatial and temporal windows → larger voxels → fewer events filtered out.  
- Decreasing spatial and temporal windows → smaller voxels → more isolated events removed.

**Note:**  
Increasing the spatial window makes voxels larger. In the visualization, the voxel boundaries may become visible, potentially giving the output a blocky appearance.
This blockiness can be reduced by decreasing the spatial window.  

---

### Inputs  
- `x, y` — spatial event coordinates  
- `t` — timestamps  
- `p` — polarity  
- `spatial_window` — spatial bin size (default: 5)  
- `time_window` — temporal bin size (default: 5000)  

---

### Outputs  
- Filtered event arrays: `x, y, t, p`


---
## Neighbor_Activity_Filter

### Purpose
Keeps only events that have neighbors nearby in space and time.

---

### Method  
1. **Scaling Time**  
   - Time is scaled to match spatial units so space and time can be treated together.

2. **3D Representation**  
   - Each event is represented as a point `(x, y, t_scaled)` in 3D space.

3. **KDTree Construction**  
   - A KDTree is built for fast neighbor searching.

4. **Neighbor Search**  
   - For each event, nearby events within a defined radius are counted.

5. **Filtering**  
   - Events that have no neighboring events (only themselves in the neighborhood) are removed.
---

### Key Idea  
Real events occur in local clusters,  
while noise tends to appear alone.

### Tuning the Filter
- Increasing spatial and temporal windows → larger voxels → fewer events filtered out.  
- Decreasing spatial and temporal windows → smaller voxels → more isolated events removed.

---

### Inputs  
- `x, y` — spatial event coordinates  
- `t` — timestamps  
- `p` — polarity  
- `spatial_window` — size of spatial neighborhood (default: 10)  
- `time_window` — size of temporal neighborhood (default: 500)  

---

### Outputs  
- Filtered event arrays: `x, y, t, p`

## Voxel vs. Neighbor Activity Filter  

### Difference  
The Voxel Activity Filter divides space and time into fixed bins (voxels) and filters events based on how many fall into the same voxel.  
In contrast, the Neighbor Activity Filter checks the local neighborhood around each individual event in continuous space and time.

### Implications  
- The two methods may remove different events, since one uses fixed regions while the other uses local proximity.  
- The Neighbor Activity Filter is significantly slower, as it performs a neighbor search for every event, whereas the Voxel method relies on fast grouping operations.

---
## Subsampling_Filter

### Purpose
Performs probabilistic density-based denoising by retaining events that occur in regions of high spatiotemporal activity, while suppressing isolated or weak events.  
Instead of applying a hard threshold, the filter uses probabilistic sampling based on local density, allowing gradual suppression of noise while preserving important structures in high-activity regions.

This filter is more aggressive than other methods and is primarily intended for strong noise reduction scenarios.


### Method  
1. **Time Sorting**  
   - Events are sorted chronologically to ensure proper temporal processing.

2. **Polarity Separation**  
   - Events are split by polarity and processed independently.

3. **Local Accumulation Map**  
   - A 2D accumulation map is maintained for each polarity.  
   - Each pixel stores a decaying activity value based on recent events.

4. **Temporal Decay**  
   - Past activity decays exponentially over time using a time constant `tau_us`.  
   - Recent events contribute more strongly than older ones.

5. **Gaussian Spatial Weighting**  
   - A Gaussian kernel (size `filter_size × filter_size`) is applied around each event.  
   - Nearby pixels contribute more to the density than distant ones.

6. **Density Estimation**  
   - A local density value is computed as a weighted sum of nearby accumulated activity.

7. **Probabilistic Sampling**  
   - Each event is kept with probability:
     ```
     prob = sampling_threshold × density
     ```
   - This probability is clipped to the range [0, 1].  
   - High-density events are more likely to be kept, while low-density events are often removed.

8. **Reconstruction**  
   - The filtered mask is mapped back to the original event order.


### Tuning the Filter
- Increasing `sampling_threshold` → more events are kept (less aggressive filtering)  
- Decreasing `sampling_threshold` → more events are removed (stronger denoising)  

- Increasing `tau_us` → longer memory → smoother, more persistent density  
- Decreasing `tau_us` → faster decay → emphasizes only recent events  

- Increasing `filter_size` → larger spatial neighborhood → smoother density estimation  
- Decreasing `filter_size` → more local, sharper filtering  

**Note:**  
This filter can be very aggressive and may remove meaningful data if parameters are not chosen carefully.


### Inputs  
- `x, y` — spatial event coordinates  
- `t` — timestamps  
- `p` — polarity  
- `H, W` — sensor resolution  
- `tau_us` — temporal decay constant (default: 40000)  
- `filter_size` — size of Gaussian kernel (must be odd, default: 7)  
- `sampling_threshold` — density scaling factor (default: 0.3)  
- `seed` — random seed for reproducibility  


### Outputs  
- Filtered event arrays: `x, y, t, p`

## Voxel_Density_Filter

### Purpose
Reduces event clutter by probabilistically thinning regions with high voxel density, keeping the dataset balanced across space and time.

---

### Method

1. **Quantization**  
   - Spatial coordinates `(x, y)` are grouped into coarse grids using `spatial_window`.  
   - Time `t` is grouped into bins using `time_window`.

2. **Voxel Encoding**  
   - Each event is assigned a unique voxel ID by combining `(t, y, x)` into a single integer.  
   - This allows fast sorting and grouping using vectorized operations, avoiding slower multidimensional comparisons.

3. **Sorting & Grouping**  
   - Voxel IDs are sorted so identical voxels are adjacent.  
   - Run-length encoding is used to count how many events fall into each voxel.

4. **Adaptive Thresholding**
   - Computes a threshold Cmax as the chosen percentile of events per voxel.
   
5. **Probabilistic Thinning**
   - Events in voxels exceeding Cmax are kept with probability `P_keep = α * (Cmax / voxel_count)`.  

6. **Reconstruction**  
   - The filtered mask is mapped back to the original event order.


### Key Idea
Dense voxels often correspond to noisy clusters or redundant events, while sparser regions tend to contain meaningful, isolated events.

---

### Tuning the Filter
- Increasing spatial_window / time_window → larger voxels → more thinning in dense regions.  
- Decreasing spatial_window / time_window → smaller voxels → fewer events filtered out.  
- Lower percentile → stricter density threshold → more aggressive filtering.  
- Smaller alpha → fewer events retained in dense voxels.

---

### Inputs
- x, y — spatial event coordinates  
- t — timestamps  
- p — polarity  
- spatial_window — size of spatial voxel (default: 20)  
- time_window — size of temporal voxel (default: 500)  
- percentile — percentile to define dense voxels (default: 80)  
- seed — random seed for reproducibility (default: None)  
- alpha — retention factor for dense voxels (default: 0.2)

---

### Outputs
- Filtered event arrays: x, y, t, p

## Median_Filter  

### Purpose  
Removes events in sparsely populated voxels by keeping only events in voxels with occupancy above an adaptive median-based threshold.

---

### Method  
1. **Quantization**  
   - Spatial coordinates `(x, y)` and time `t` are grouped into coarse voxels using `spatial_window` and `time_window`.

2. **Voxel Encoding**  
   - Each event is assigned a unique voxel ID by combining `(t, y, x)` into a single integer for fast sorting and grouping.

3. **Sorting & Counting**  
   - Voxel IDs are sorted so identical voxels are adjacent.  
   - Run-length encoding counts how many events are in each voxel.

4. **Adaptive Median Threshold**  
   - The median voxel occupancy is computed.  
   - Voxels with fewer events than the threshold are considered sparse, and events in them are removed.

5. **Reconstruction**  
   - The filtered mask is mapped back to the original event order.

---

### Key Idea  
Real events tend to occur in clusters of events, while noise or isolated events appear in sparsely populated voxels.  
Unlike the voxel or neighbor activity filters, this method adapts the threshold per dataset using the median voxel occupancy.

### Tuning the Filter
- Increasing spatial and temporal windows → larger voxels → more events per voxel. The median occupancy typically rises, so fewer voxels fall below the adaptive threshold, and more events are kept.  
- Decreasing spatial and temporal windows → smaller voxels → fewer events per voxel. Median occupancy drops, more voxels fall below the threshold, and more events are filtered out.  

**Note:** The relationship is not strictly linear due to the maximum threshold and the distribution of events; the exact percentage of events filtered depends on the data density and clustering. 
Also, increasing the spatial window makes voxels larger. In the visualization, the voxel boundaries may become visible, potentially giving the output a blocky appearance.
This blockiness can be reduced by decreasing the spatial window.  

### Inputs  
- `x, y` — spatial event coordinates  
- `t` — timestamps  
- `p` — polarity  
- `spatial_window` — voxel size in pixels (default: 10)  
- `time_window` — voxel size in microseconds (default: 3000)  

---

### Outputs  
- Filtered event arrays: `x, y, t, p`

---

## Adding New Filters

This section provides a guide for implementing new filters into the GUI environment. Rather than detailed code explanations, this guide points to all the locations where changes are needed and suggests copying the syntax from existing filters.

### Overview of Files to Modify

To add a new filter, you will need to make changes in **4 main files**:
1. `Cleaning_Data.py` — the filter implementation
2. `EveViz.py` — the GUI integration and control logic  
3. `GUI_helper.py` — reset/initialization logic
4. `Exporting_Data.py` — optional, for filter abbreviation in exported filenames

---

### Step 1: Implement the Filter Function in `Cleaning_Data.py`

**Location:** `Cleaning_Data.py`, inside the `CleaningData` class

**What to do:**
- Add a new static method following the pattern of existing filters
- The method signature should be: `@staticmethod def Your_Filter_Name(x, y, t, p, param1=default1, param2=default2, ...)`
- Return the filtered arrays: `return x[keep], y[keep], t[keep], p[keep]`

**Example to copy from:**
```python
@staticmethod
def Voxel_Activity_Filter(x, y, t, p, spatial_window=20, time_window=500):
    # quantize, filter, and return
    # ... filtering logic ...
    return x[keep], y[keep], t[keep], p[keep]
```

**Key patterns:**
- Use `@staticmethod` decorator
- Always return the 4 filtered arrays in order: `x, y, t, p`

---

### Step 2: Add Filter State to `EveViz.py` — AppState Class

**Location:** `EveViz.py`, in the `AppState.__init__()` method (around line 32-100)

You need to add 3 things to AppState initialization:

**2a) Add a filter applied flag:**
```python
self.your_filter_applied = False
```
Copy the pattern from: `self.voxel_activity_filter_applied = False` (line 64)

**2b) Add filter parameters:**
```python
self.your_filter_param1 = default_value1
self.your_filter_param2 = default_value2
```
Copy the pattern from: `self.voxel_activity_spatial_window = 5` (line 79)

**2c) Add filter statistics:**
```python
self.your_filter_removed = 0
self.your_filter_percentage = 0.0
```
Copy the pattern from: `self.voxel_activity_removed = 0` (line 93)

---

### Step 3: Add Parameter Tuning UI in `EveViz.py`

**Location:** `EveViz.py`, in the `create_parameter_tuning_window()` function (around line 112-246)

**3a) Add a parameter frame in the main layout:**
```python
your_filter_frame = tk.LabelFrame(main_frame, text="Your Filter Name", font=("Arial", 9, "bold"), padx=8, pady=6)
your_filter_frame.grid(row=0, column=X, padx=5, pady=5, sticky="nsew")  # Use next available column
```
Copy from: `voxel_frame = tk.LabelFrame(main_frame, text="Voxel Activity", ...)` (line 144)

**3b) Add spinbox widgets for each parameter:**
```python
tk.Label(your_filter_frame, text="Param 1 (units):", font=("Arial", 8)).pack(anchor="w")
your_filter_param1_var = tk.IntVar(value=state.your_filter_param1)
your_filter_param1_spinbox = tk.Spinbox(
    your_filter_frame, from_=min_val, to=max_val, width=12, textvariable=your_filter_param1_var, increment=1, font=("Arial", 8)
)
your_filter_param1_spinbox.pack(anchor="w", pady=(2, 2))
tk.Label(your_filter_frame, text="(Rec: X-Y units)", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", pady=(0,2))
```
Copy the pattern from: lines 147-161 (Voxel Activity spinbox setup)

**3c) Add to confirm_settings() function:**
```python
state.your_filter_param1 = your_filter_param1_var.get()
state.your_filter_param2 = your_filter_param2_var.get()
```
Copy from: lines 218-223

**3d) Add to reset_to_defaults() function:**
```python
your_filter_param1_var.set(default_value1)
your_filter_param2_var.set(default_value2)
```
Copy from: lines 228-235

**3e) Update grid column configuration:**
Change line 206 from `for i in range(4):` to `for i in range(5):` (if adding a 5th filter)

---

### Step 4: Add Filter Checkbutton UI in `EveViz.py`

**Location:** `EveViz.py`, around line 1365-1395 where filter checkbuttons are created

**What to do:**
```python
your_filter_row = tk.Frame(checkbox_container)
your_filter_row.pack(anchor="w", pady=2)
your_filter_var = tk.BooleanVar(value=False)
your_filter_cb = tk.Checkbutton(your_filter_row, text="Your Filter Name", variable=your_filter_var)
your_filter_cb.pack(side="left", padx=5)
your_filter_indicator = tk.Label(your_filter_row, text=' ', font=("Arial", 8), fg='black')
your_filter_indicator.pack(side="left", padx=5)
indicator_map['your_filter_abbreviation'] = your_filter_indicator
```
Copy from: lines 1365-1375 (Hot Pixel Filter checkbutton setup)

---

### Step 5: Add Filter Statistics Label in `EveViz.py`

**Location:** `EveViz.py`, around line 1430-1440 where stats labels are created

**What to do:**
```python
your_filter_stats = tk.Label(detail_frame, text="Your Filter: — events (—%)", font=("Arial", 8), fg="gray")
your_filter_stats.pack(anchor="w", padx=5, pady=1)
```
Copy from: line 1432 (Voxel Activity stats label)

---

### Step 6: Update `apply_cleaning()` Function in `EveViz.py`

**Location:** `EveViz.py`, in the `apply_cleaning()` function (around line 1608-1668)

**6a) Add filter to the filters list:**
```python
if your_filter_var.get():
    filters.append('your_filter')  # Use a short identifier like 'hot', 'voxel', etc.
```
Copy from: lines 1620-1628

**6b) Add reset state before cleaning:**
```python
state.your_filter_applied = False
state.your_filter_removed = 0
state.your_filter_percentage = 0.0
```
Copy from: lines 1635-1649

**6c) Add UI reset:**
```python
your_filter_stats.config(text="Your Filter: — events (—%)", fg="gray")
```
Copy from: lines 1651-1655

---

### Step 7: Update `reset_filters()` Function in `EveViz.py`

**Location:** `EveViz.py`, in the `reset_filters()` function (around line 1674-1705)

**7a) Reset the checkbox:**
```python
your_filter_var.set(False)
```
Copy from: lines 1681-1685

**7b) Reset the state flag:**
```python
state.your_filter_applied = False
```
Copy from: lines 1700-1704

**7c) Reset the statistics label:**
```python
your_filter_stats.config(text="Your Filter: — events (—%)", fg="gray")
```
Copy from: lines 1689-1693

---

### Step 8: Add Filter to `cleaning_worker()` Function in `EveViz.py`

**Location:** `EveViz.py`, in the `cleaning_worker()` function (around line 1485-1519)

**What to do:**
```python
elif name == 'your_filter':
    x, y, t, p = CleaningData.Your_Filter_Name(
        x, y, t, p, 
        param1=state.your_filter_param1, 
        param2=state.your_filter_param2
    )
```
Copy structure from: lines 1502-1508 (where other filters are called)

**Note:** Add this to the if-elif chain. The order of filters here determines the pipeline execution order.

---

### Step 9: Add Filter Handling to `poll_progress()` Function in `EveViz.py`

**Location:** `EveViz.py`, in the `poll_progress()` function (around line 1520-1567)

**What to do:**
```python
elif name == 'your_filter':
    state.your_filter_removed = removed
    state.your_filter_percentage = pct
    your_filter_stats.config(text=f"Your Filter: {removed:,} events removed ({pct:.1f}%)", fg="black")
    state.your_filter_applied = True
```
Copy from: lines 1551-1555 (Voxel Activity filter handling)

---

### Step 10: Update `reset_for_new_file()` in `GUI_helper.py`

**Location:** `GUI_helper.py`, in the `reset_for_new_file()` function (around line 3-52)

**What to do:**
```python
state.your_filter_applied = False
state.your_filter_removed = 0
state.your_filter_percentage = 0.0
```
Copy pattern from: lines 28-31

---

### Step 11 (Optional): Add Filter Abbreviation to `Exporting_Data.py`

**Location:** `Exporting_Data.py`, in **ALL** the following functions:

If you want the filter to appear in exported filenames and reports, add an abbreviation in all 5 locations:

**Function 1: `save_plot()` (lines 26-35)**
**Function 2: `save_screenshot()` (lines 69-78)**
**Function 3: `save_video()` (lines 131-140)**
**Function 4: `export_clean_data()` (lines 382-391)**
**Function 5: `export_report()` (lines 357-365)**

**Add to each location:**
```python
if state.your_filter_applied:
    applied_filters.append("YF")  # Your filter abbreviation (2 chars recommended)
```

Copy the pattern from any of the existing filters (HP, VA, VD, ME) in each function.

**Note:** `export_report()` doesn't build an abbreviation string, but still needs the filter check for the report output.

---

### Quick Checklist for Adding a New Filter

**1. `Cleaning_Data.py`**
- [ ] Add filter function as `@staticmethod`

**2. `EveViz.py` - AppState class**
- [ ] Add filter applied flag
- [ ] Add filter parameters
- [ ] Add filter statistics

**3. `EveViz.py` - GUI & Functions**
- [ ] Add parameter tuning UI in `create_parameter_tuning_window()`
- [ ] Add checkbutton and statistics label
- [ ] Add to `apply_cleaning()` function
- [ ] Add to `reset_filters()` function
- [ ] Add filter execution in `cleaning_worker()`
- [ ] Add filter handling in `poll_progress()`

**4. `GUI_helper.py`**
- [ ] Update `reset_for_new_file()` function

**5. `Exporting_Data.py` (Optional)**
- [ ] Add abbreviation to `save_plot()`
- [ ] Add abbreviation to `save_screenshot()`
- [ ] Add abbreviation to `save_video()`
- [ ] Add abbreviation to `export_clean_data()`
- [ ] Add filter check to `export_report()`

---

### Filter Pipeline Order

Filters are executed in a **fixed order** (only selected filters run). The current order is:
1. Hot Pixel Filter
2. Voxel Activity Filter
3. Voxel Density Filter
4. Median Filter

When adding a new filter, insert it in this list according to the logical flow. Each filter receives the output of the previous one, so order matters for the results.
