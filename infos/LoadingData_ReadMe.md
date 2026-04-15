# Loading Data

---
## Description
This module contains the class `LoadingData`, which provides helper functions to:
- select a data file via GUI,
- detect its file type,
- load event-based sensor data from multiple formats,
- and return the data in a unified format:  
  **x, y, t, p** arrays

The data represents events from an event camera / event sensor:

- **x**: x-coordinate (pixel column)
- **y**: y-coordinate (pixel row)
- **t**: timestamp (time of the event)
- **p**: polarity (typically 0/1 or -1/1 depending on format)

Returned arrays are NumPy arrays, optimized for further processing.

---
## GetFilePath_Type()
Opens a file dialog (`tkinter.filedialog`) so the user can select a file from his directory.

Returns
- filepath (str): full path to the selected file
- filetype (str): file extension without the dot (e.g. "csv", "raw", "hdf5")

---
## Load_RawData(filepath)
Loads Prophesee RAW (.raw) event files and returns NumPy arrays: `x`, `y`, `t`, `p`.

It uses `metavision_core.event_io.EventsIterator` to stream event packets, then merges all packets into one continuous event array.

Returns NumPy arrays: `x_values`, `y_values`, `t_values`, `p_values`.

 ⚠️ The function utilizes a library from Prophesee that is only accessible to users having Metavision SDK / OpenEB installed. [See Metavision SDK installation](../README.md#metavision-sdk-required-for-loading-raw-files)

---
### How It Works

1. **Create RAW Event Iterator**
   - Initializes `EventsIterator(filepath)` for the selected `.raw` file
   - The iterator yields event chunks in structured format

2. **Collect All Event Chunks**
   - Converts the iterator to a list (`list(events_iterator)`)
   - This gathers all chunks before concatenation

3. **Concatenate Event Data**
   - Uses `np.concatenate(all_events)` once
   - Avoids repeated append operations and improves performance

4. **Extract Event Fields**
   - Reads structured array fields directly:
     - `x = all_events['x']`
     - `y = all_events['y']`
     - `t = all_events['t']`
     - `p = all_events['p']`

5. **Return Values**
   - Returns `x_values`, `y_values`, `t_values`, `p_values` as NumPy arrays

---
## Load_CsvData(filepath)
Data loader for header-less CSV files with unknown column order.  

It automatically detects:

- CSV delimiter (`;` or `,`)  
- Time column (`t_values`) via monotonic increasing values  
- Polarity column (`p_values`) with a few unique values (0/1, -1, or boolean)  
- Spatial columns (`x` and `y`), automatically ordered by maximum value  

Returns NumPy arrays: `x_values`, `y_values`, `t_values`, `p_values`.  

The function is optimized for performance using PyArrow (Apache Arrow) for multithreaded CSV reading and fast integer parsing.

---
### How It Works

1. **Delimiter Detection**  
   - Uses Python’s CSV Sniffer first.  
   - If that fails, a heuristic chooses the delimiter producing the most consistent column count.

2. **CSV Loading with Arrow**  
   - Forces 4 generic column names (`c0`, `c1`, `c2`, `c3`)  
   - Reads all columns as `int64`  
   - Uses multithreading for speed

3. **Conversion to NumPy Arrays**  
   - Arrow columns are converted to NumPy arrays for numerical processing.

4. **Classification of Columns**  
   - **Time column**: checks first 100 elements for monotonic increasing values  
   - **Polarity column**: checks first 100 elements for values in `{0,1,0.0,1.0,True,False,-1}`  
   - Remaining two arrays are treated as spatial `x` and `y`

5. **Spatial Columns (x, y)**  
   - `x` is the array with the larger maximum value  
   
6. **Time Offset and Unit Adjustment**  
   - Time values are offset to start at zero  
   - If the first time step is very small (<0.001), values are assumed to be in seconds and converted to microseconds 
   - function cannot correctly identify data in other units than microseconds and seconds

7. **Return Values**  
   Returns `x_values, y_values, t_values, p_values` as NumPy arrays

---
## Load_Hdf5Data(filepath)
Loads data from HDF5 (.h5 / .hdf5) files and classifies arrays as x, y, t, p.

It automatically detects:

- Time column (`t_values`) via monotonicity
- Polarity (`p_values`) with 0/1 or boolean values
- Spatial columns (`x` and `y`, automatically ordered by maximum value)

Returns NumPy arrays: `x_values`, `y_values`, `t_values`, `p_values`.

⚠️This function utilizes a library (`h5py`) which is only available for users having the ECF_Filter installed. [See ECF Filter installation](../README.md#ecf-filter-hdf5-plugin)

---
### How It Works

1. **Load All Arrays**  
   - Opens the HDF5 file with `h5py.File`  
   - Recursively visits all datasets  
   - Loads compound datasets (with multiple fields) and regular datasets  
   - Stores all non-empty arrays in a list

2. **Select Largest Arrays**  
   - Filters arrays by size  
   - Only arrays with the maximum number of elements are considered for classification
   - Arrays with fewer elements are reduced datasets (e.g.`EXT_TRIGGER`)

3. **Time Column Detection**  
   - Checks first 100 elements for monotonic increasing values 
   - Assigned as `t_values`  
   - Applies a time offset correction so it starts at zero  
   - Converts units to microseconds if differences are very small (<0.001)

4. **Polarity Column Detection**  
   - Checks first 100 elements for values in `{0, 1, 0.0, 1.0, True, False}`  
   - Assigned as `p_values`

5. **Spatial Columns (x, y)**  
   - Remaining two arrays are treated as spatial  
   - `x` is the array with larger maximum value

6. **Time Offset and Unit Adjustment**  
   - Time values are offset to start at zero  
   - If the first time step is very small (<0.001), values are assumed to be in seconds and converted to microseconds  
   - function cannot correctly identify data in other units than microseconds and seconds
   
7. **Return Values**  
   Returns `x_values, y_values, t_values, p_values` as NumPy arrays

---
## Load_BinData(bin_path)
Loads compressed `.bin`  files by first decompressing them to `.txt` with `Main.exe` (BIN Converter), then loading the decompressed file as event data.

Returns NumPy arrays: `x_values`, `y_values`, `t_values`, `p_values`.

⚠️ This function requires the BIN converter executable (`Main.exe`) to be installed and available in your system `PATH`. [See BIN Converter installation](../README.md#event-converter-bin---required-for-loading--exporting-bin-files)

---
### How It Works

1. **Validate Input File**
   - Resolves `bin_path` to an absolute path
   - Checks if the `.bin` file exists
   - Raises `FileNotFoundError` if the file is missing

2. **Check Decompression Dependency**
   - Verifies that `Main.exe` is callable via `PATH` (`shutil.which("Main.exe")`)
   - Raises an environment error if `Main.exe` is not found

3. **Create Output Path**
   - Builds a target `.txt` path in the same location as the input file
   - Uses the same filename with `.txt` as extension

4. **Run Decompression Command**
   - Executes `Main.exe d <input.bin> <output.txt>` using `subprocess.run`
   - Checks the return code and raises a runtime error if decompression fails

5. **Validate Decompression Result**
   - Confirms that the output `.txt` file was created
   - Raises a runtime error if no output file exists

6. **Load Decompressed Event Data**
   - Calls `Load_TxtData(output_txt_path)`
   - Extracts event arrays in unified order: `x, y, t, p`

7. **Return Values**
   - Returns `x_values, y_values, t_values, p_values` as NumPy arrays

---
## Load_TxtData(filepath)
Loads `.txt` event files while only accepting the standard txt format from the BIN converter (comma delimited & fixed column order `x, y, p, t`).

The loader automatically checks whether the first row is a header and skips it if needed.

Returns NumPy arrays: `x_values`, `y_values`, `t_values`, `p_values`.

---
### How It Works

1. **Detect Header Row**
   - Reads the first line of the file
   - Tries to parse all first-row entries as integers
   - If parsing fails, the first row is treated as a header and skipped

2. **Load TXT Data**
   - Reads the file using `np.loadtxt`
   - Uses comma `,` as delimiter
   - Uses `int32` as data type for efficient loading

3. **Assign Columns**
   - Assigns event columns in fixed order:
     - `x = data[:, 0]`
     - `y = data[:, 1]`
     - `p = data[:, 2]`
     - `t = data[:, 3]`

4. **Normalize Time**
   - Shifts all timestamps so the first event starts at `t = 0`

5. **Validate Time Sequence**
   - Checks that time values are monotonic increasing
   - Raises a `ValueError` if time order is invalid

6. **Return Values**
   - Returns `x_values, y_values, t_values, p_values` as NumPy arrays

---
## File_Parameters(x_values, y_values, p_values, t_values=None)
Computes basic statistics for loaded event data.

Functionality:
- Computes spatial limits:
   - maximum x value (`max_x`)
   - maximum y value (`max_y`)
- Computes event counts:
   - total number of events
   - number of positive events (sum of polarity array)
   - number of negative events (total minus positive)
- Optionally computes time range when `t_values` is provided:
   - minimum timestamp (`min_t`)
   - maximum timestamp (`max_t`)

Return order:
- `max_x, max_y, total_events, positive_events, negative_events, min_t, max_t`


