import os
import pandas as pd
import h5py
from tkinter import filedialog
import csv as pycsv
import numpy as np
import pyarrow as pa
from pyarrow import csv
import shutil
from pathlib import Path
import subprocess
try:
    from metavision_core.event_io import EventsIterator
except ModuleNotFoundError:
    print("Could not import metavision_core.event_io")
    
    



class LoadingData:

    BIN_CONVERTER_EXE = "Main.exe"
    # Optional full path or folder — use if Main.exe is not on the PATH EveViz inherits.
    BIN_CONVERTER_ENV_VARS = ("EVEVIZ_MAIN_EXE", "EVEVIZ_BIN_CONVERTER", "BIN_CONVERTER_PATH")

    @staticmethod
    def find_bin_converter_path():
        """
        Locate Main.exe on this machine (not in the EveViz repo).

        Search order:
          1. EVEVIZ_MAIN_EXE / EVEVIZ_BIN_CONVERTER / BIN_CONVERTER_PATH (file or folder)
          2. Directories in the process PATH environment variable (via shutil.which)
        """
        try:
            for env_name in LoadingData.BIN_CONVERTER_ENV_VARS:
                raw = os.environ.get(env_name, "").strip()
                if not raw:
                    continue
                candidate = Path(os.path.expanduser(raw)).resolve()
                if candidate.is_file():
                    return candidate
                exe_in_dir = candidate / LoadingData.BIN_CONVERTER_EXE
                if exe_in_dir.is_file():
                    return exe_in_dir

            # shutil.which walks os.environ["PATH"] (and PATHEXT on Windows).
            on_path = shutil.which(LoadingData.BIN_CONVERTER_EXE)
            if on_path:
                return Path(on_path).resolve()
        except Exception:
            return None
        return None

    @staticmethod
    def is_bin_converter_available():
        """Return True if Main.exe was found via env override or system PATH."""
        return LoadingData.find_bin_converter_path() is not None

    @staticmethod
    def get_bin_converter_command():
        """Absolute path to Main.exe for subprocess, or None if not installed."""
        found = LoadingData.find_bin_converter_path()
        return str(found) if found is not None else None

    @staticmethod
    def GetFilePath_Typ():      #Get file path and type of the data file
        # Open a file dialog and extract the selected file path.
        filepath = filedialog.askopenfilename(
            title="Select a file",
            filetypes=[("All Files", "*.*")]
        )
        # Extract file extension without the dot, e.g. "txt"
        filetype = os.path.splitext(filepath)[1].lower().replace(".", "")

        return filepath, filetype
        

    @staticmethod
    def Load_RawData(filepath):     #Load raw data into x,y,t,p arrays
        """
        Load Prophesee RAW data and return x, y, t, p arrays.
        Requires the Prophesee Metavision SDK / OpenEB to be installed.
        """
        events_iterator = EventsIterator(filepath)

        # Collect all events into a list first (no .append loop)
        all_events = list(events_iterator)  # much faster than manual append

        # Concatenate once
        all_events = np.concatenate(all_events)

        # Extract components (no need to copy)
        x = all_events['x']
        y = all_events['y']
        t = all_events['t']
        p = all_events['p']

        return x, y, t, p

    @staticmethod
    def Load_CsvData(filepath):
        """
        Fast load for header-less CSV with unknown column order (x,y,t,p) and
        unknown delimiter ("," or ";").
        Returns: x_values, y_values, t_values, p_values (all NumPy arrays)
        """

        # ---- Delimiter detection ----
        def detect_delimiter(path, sample_size=4096):
            # Read a small sample (4KB) from the file to guess the delimiter
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                sample = f.read(sample_size)

            # 1. Try Python's built-in CSV Sniffer (automatic detection)
            try:
                dialect = pycsv.Sniffer().sniff(sample, delimiters=";,")
                return dialect.delimiter
            except Exception:
                pass  # fallback if sniffing fails

            # 2. Fallback heuristic:
            # choose delimiter that produces most consistent column counts
            candidates = [",", ";"]
            scores = {}

            for delim in candidates:
                # Split lines using this delimiter
                rows = [line.split(delim) for line in sample.splitlines() if line.strip()]
                if not rows:
                    scores[delim] = 0
                    continue

                # Measure how consistent row lengths are
                lengths = [len(r) for r in rows]
                avg = sum(lengths) / len(lengths)
                variance = sum((l - avg) ** 2 for l in lengths)

                scores[delim] = -variance  # lower variance = more consistent

            # Return the delimiter with best (lowest variance) score
            return max(scores, key=scores.get)

        # Detect delimiter automatically ("," or ";")
        delimiter = detect_delimiter(filepath)

        # Define how to read the file:
        # - use multiple threads for speed
        # - assign generic column names since no header exists
        read_options = csv.ReadOptions(
            use_threads=True,
            column_names=["c0", "c1", "c2", "c3"]
        )

        # Define how to parse CSV text:
        # use detected delimiter to split columns
        parse_options = csv.ParseOptions(delimiter=delimiter)

        # Define how to convert parsed data:
        # force all columns to int64 for performance and consistency
        convert_options = csv.ConvertOptions(
            column_types={
                "c0": pa.int64(),
                "c1": pa.int64(),
                "c2": pa.int64(),
                "c3": pa.int64()
            }
        )

        # -------- Main CSV read with Arrow --------
        # Reads the CSV into a PyArrow table using the defined options
        table = csv.read_csv(
            filepath,
            read_options=read_options,
            parse_options=parse_options,
            convert_options=convert_options
        )

        # Convert Arrow columns into NumPy arrays for easier processing
        cols = [table[f"c{i}"].to_numpy(zero_copy_only=False) for i in range(4)]

        # ---------------- Classification logic ----------------

        def check_for_time(arr):
            # Time is assumed to be monotonically increasing
            subset = arr[:min(100, len(arr))]
            return pd.Series(subset).is_monotonic_increasing

        def check_for_polarity(arr):
            # Polarity is assumed to contain only binary values (0/1 or True/False)
            subset = arr[:min(100, len(arr))]
            return set(subset).issubset({0, 1, 0.0, 1.0, True, False})

        t_values = None
        p_values = None
        others = []

        # Identify which column is time, polarity, or spatial (x/y)
        for arr in cols:
            if t_values is None and check_for_time(arr):
                t_values = arr  # assign time column
            elif p_values is None and check_for_polarity(arr):
                p_values = arr  # assign polarity column
            else:
                others.append(arr)  # remaining are x/y candidates

        # Ensure exactly two columns remain for x and y
        if len(others) != 2:
            raise ValueError(
                f"Classification failed: expected 2 x/y arrays but found {len(others)}.\n"
                f"Time column found: {t_values is not None}\n"
                f"Polarity column found: {p_values is not None}\n"
                f"Columns given: {len(cols)}"
            )

        # Determine which is x and which is y:
        # assumption: x has larger values than y
        LIMIT = min(len(others[0]), len(others[1]), 200_000)
        max1 = max(others[0][:LIMIT])
        max2 = max(others[1][:LIMIT])

        if max1 > max2:
            x_values = others[0]
            y_values = others[1]
        else:
            x_values = others[1]
            y_values = others[0]

        # Normalize time so it starts at 0
        t_values = t_values - t_values[0]

        # Find first two distinct time values
        first = t_values[0]
        second = None

        for v in t_values[1:]:
            if v != first:
                second = v
                break

        # Check time resolution:
        # if time step is very small, assume it's in seconds and convert to microseconds
        if second is not None:
            dt = abs(second - first)
            if 0 < dt < 0.001:
                t_values = t_values * 1e6  # convert to µs

        # Return structured data
        return x_values, y_values, t_values, p_values

    @staticmethod
    def Load_Hdf5Data(filepath):
        """
        Load HDF5 file and classify the four main arrays as x_values, y_values, t_values, p_values.
        Uses largest-shape filtering.
        """

        results = []  # collect all non-empty arrays from file

        # ---------------- Load all arrays ----------------
        with h5py.File(filepath, "r") as f:

            def visit(name, obj):
                if isinstance(obj, h5py.Dataset):

                    # If dataset has multiple fields (compound type), load each field separately
                    if obj.dtype.names:
                        for field in obj.dtype.names:
                            arr = obj[field][:]
                            if arr.size > 0:
                                results.append(arr)

                    # Otherwise load dataset directly
                    else:
                        arr = obj[:]
                        if arr.size > 0:
                            results.append(arr)

            f.visititems(visit)  # recursively visit all datasets in the file

        # ---------------- Find largest arrays ----------------
        # largest arrays correspond to main x/y/t/p data; smaller ones are auxiliary
        if not results:
            raise ValueError("No non-empty arrays found in file.")

        sizes = [arr.size for arr in results]  # compute size of each array
        max_size = max(sizes)

        # keep only arrays with the largest size (likely the main data)
        largest_arrays = [arr for arr in results if arr.size == max_size]

        # ---------------- Classification logic ----------------

        def check_for_time(arr):
            subset = arr[:min(100, len(arr))]
            return pd.Series(subset).is_monotonic_increasing  # time should increase

        def check_for_polarity(arr):
            subset = arr[:min(100, len(arr))]
            return set(subset).issubset({0, 1, 0.0, 1.0, True, False})  # polarity is binary

        t_values = None
        p_values = None
        others = []

        # Identify time, polarity, and remaining (x/y) arrays
        for arr in largest_arrays:
            if t_values is None and check_for_time(arr):
                t_values = arr
            elif p_values is None and check_for_polarity(arr):
                p_values = arr
            else:
                others.append(arr)

        # Ensure exactly two arrays remain for x and y
        if len(others) != 2:
            raise ValueError(
                f"Classification failed: expected 2 x/y arrays but found {len(others)}.\n"
                f"Time column found: {t_values is not None}\n"
                f"Polarity column found: {p_values is not None}\n"
                f"Columns given: {len(largest_arrays)}"
            )

        # Determine x vs y based on larger value range (x assumed larger)
        LIMIT = min(len(others[0]), len(others[1]), 200_000)
        max1 = max(others[0][:LIMIT])
        max2 = max(others[1][:LIMIT])

        if max1 > max2:
            x_values = others[0]
            y_values = others[1]
        else:
            x_values = others[1]
            y_values = others[0]

        # Normalize time so it starts at 0
        t_values = t_values - t_values[0]

        # Find first two distinct time values
        first = t_values[0]
        second = None

        for v in t_values[1:]:
            if v != first:
                second = v
                break

        # Check time resolution:
        # if time step is very small, assume it's in seconds and convert to microseconds
        if second is not None:
            dt = abs(second - first)
            if 0 < dt < 0.001:
                t_values = t_values * 1e6  # convert to µs

        # Return structured data
        return x_values, y_values, t_values, p_values


    @staticmethod
    def Load_BinData(bin_path):    #Load Bin data into x,y,t,p arrays
        """
         Decompress a .bin file into a .txt file using Main.exe.
         Requires the folder containing Main.exe to be on PATH.
         EveViz runs without this converter; only .bin load/export need it.
        """

        # Validate input file
        try:
            bin_path = Path(bin_path).resolve()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid .bin path: {bin_path}") from exc

        if not bin_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {bin_path}")

        main_exe = LoadingData.get_bin_converter_command()
        if main_exe is None:
            raise EnvironmentError(LoadingData.bin_converter_not_found_message())

        txt_path = bin_path.with_suffix(".txt")

        try:
            result = subprocess.run(
                [main_exe, "d", str(bin_path), str(txt_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise EnvironmentError(
                "BIN compression (Main.exe) was not found when decompressing. "
                "EveViz works without it — install Main.exe only for .bin files."
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to run {LoadingData.BIN_CONVERTER_EXE}: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(
                f"{LoadingData.BIN_CONVERTER_EXE} failed while decompressing .bin"
                + (f":\n{stderr}" if stderr else ".")
            )

        if not txt_path.is_file():
            raise RuntimeError("Decompression completed but output .txt was not created.")

        try:
            x, y, t, p = LoadingData.Load_TxtData(txt_path)
        except Exception as exc:
            raise RuntimeError(f"Decompressed .txt could not be loaded: {exc}") from exc

        return x, y, t, p

    @staticmethod
    def bin_converter_not_found_message():
        return (
            "BIN compression (Main.exe) was not found. "
            "EveViz works without it — use CSV, TXT, HDF5, or RAW. "
            "To enable .bin files: add the folder containing Main.exe to your system PATH, "
            "or set EVEVIZ_MAIN_EXE to its full path, then restart EveViz."
        )
                
    @staticmethod
    def Load_TxtData(filepath):     #Load TXT data into x,y,t,p arrays
        # Check if the first row contains strings (header) and skip if so
        with open(filepath, 'r') as f:
            first_line = f.readline().strip()
        
        first_row = first_line.split(',')
        try:
            [int(x.strip()) for x in first_row]
            skiprows = 0
        except ValueError:
            skiprows = 1
        
        # Load data from txt file assuming comma delimiter and int32 data type
        data = np.loadtxt(filepath, delimiter=',', dtype=np.int32, skiprows=skiprows)

        x = data[:, 0]
        y = data[:, 1]
        p = data[:, 2]
        t = data[:, 3]
        t = t - t[0]  # normalize time to start from zero

        if not pd.Series(t).is_monotonic_increasing:
            raise ValueError("Time values are not monotonic increasing (time array not correctly chosen)")

        # return in requested order
        return x, y, t, p 
     
    @staticmethod
    def File_Parameters(x_values, y_values, p_values, t_values=None):
        # Convert inputs once to NumPy arrays for consistent downstream operations.
        x = np.asarray(x_values)
        y = np.asarray(y_values)
        p = np.asarray(p_values)

        # Optional time statistics (min/max) are only computed when time is provided.
        min_t = None
        max_t = None
        if t_values is not None:
            t = np.asarray(t_values)
            if t.size > 0:
                min_t = t.min()
                max_t = t.max()

        total_events = x.size
        # Guard empty inputs to avoid max() on empty arrays.
        if total_events == 0:
            return None, None, 0, 0, 0, None, None

        # Derive spatial bounds and polarity-based event counts.
        max_x = x.max()
        max_y = y.max()
        positive_events = p.sum()
        negative_events = total_events - positive_events

        # Return order is used by the GUI and summary output.
        return max_x, max_y, total_events, positive_events, negative_events, min_t, max_t
       
