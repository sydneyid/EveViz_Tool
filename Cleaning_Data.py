import numpy as np
import numba
from scipy.spatial import cKDTree

class CleaningData:

    @staticmethod

    def Hot_Pixel_Filter(x_values, y_values, t_values, p_values, x_max, y_max, percentile = 99.999):
            H, W = y_max, x_max  # camera resolution
            percentile = 99.999 # hot pixel treshold
            n_time_bins = 50
            cv_max = 0.5  # coefficient of variation threshold (std/mean)
            min_events = 100  # ignore candidates with too few events (unstable stats)


            """
            Detect hot pixels and remove all events from them, keeping timestamps and polarities.

            Args:
                x_values (np.ndarray): x coordinates of events
                y_values (np.ndarray): y coordinates of events
                t_values (np.ndarray): timestamps of events
                p_values (np.ndarray): polarities of events
                percentile (float): percentile to classify hot pixels, treshold at 99.999 for hot pixel

            Returns:
                x_clean, y_clean, t_clean, p_clean: filtered arrays
                threshold: threshold value used for hot pixel detection
                accepted: number of validated hot pixels detected
            """

            # Build event count image
            rate_img = np.zeros((H+1, W+1), dtype=np.uint32)
            np.add.at(rate_img, (y_values, x_values), 1)

            # Detect hot candidates by global percentile
            threshold = np.percentile(rate_img, percentile)
            hot_mask = rate_img > threshold
            candidate_coords = np.argwhere(hot_mask)  # (y, x)
            num_candidates = candidate_coords.shape[0]

            # Already clean?
            if num_candidates == 0:
                print("Hot pixel filter skipped — data already clean.")
                return x_values, y_values, t_values, p_values, None, 0

            # --- Second-stage validation: temporal consistency ---
            # Bin edges across the dataset time span
            t_min = t_values.min()
            t_max = t_values.max()

            # Avoid degenerate case (all times equal)
            if t_max == t_min:
                # fall back to original behavior
                keep_mask = ~hot_mask[y_values, x_values]
                return x_values[keep_mask], y_values[keep_mask], t_values[keep_mask], p_values[keep_mask], threshold, 0

            bin_edges = np.linspace(t_min, t_max, n_time_bins + 1)

            true_hot_mask = np.zeros_like(hot_mask, dtype=bool)
            accepted = 0
            # For faster lookup: indices of events per candidate pixel
            # (simple approach; OK if candidate count is small)
            for (yy, xx) in candidate_coords:
                pix_sel = (x_values == xx) & (y_values == yy)
                n = int(pix_sel.sum())
                if n < min_events:
                    continue

                # counts per time bin
                counts, _ = np.histogram(t_values[pix_sel], bins=bin_edges)

                mean = counts.mean()
                std = counts.std(ddof=0)

                # coefficient of variation (guard against mean=0)
                cv = std / (mean + 1e-12)

                # Hot pixel = consistently high rate -> low CV
                if cv <= cv_max:
                    true_hot_mask[yy, xx] = True
                    accepted += 1

            if accepted == 0:
                print("No candidates passed temporal-consistency check; skipping removal.")
                return x_values, y_values, t_values, p_values, threshold, 0

            # Filter events: remove only validated hot pixels
            remove_mask = true_hot_mask[y_values, x_values]
            keep_mask = ~remove_mask

            x_clean = x_values[keep_mask]
            y_clean = y_values[keep_mask]
            t_clean = t_values[keep_mask]
            p_clean = p_values[keep_mask]

            print("hot pixel filter start")
            print(f"Candidate threshold (percentile {percentile}): {threshold:.1f}")
            print(f"Candidates: {num_candidates}, validated hot pixels: {accepted}")
            print(f"Events before: {len(x_values)}, after cleaning: {len(x_clean)}")
            print("hot pixel filter end")

            return x_clean, y_clean, t_clean, p_clean, threshold, accepted

    @staticmethod
    def Voxel_Activity_Filter(x, y, t, p, spatial_window=20, time_window=500):

        print("Activity filter executed")
        print(f"Initial events: {len(t)}")

        # Quantize coordinates into coarse voxels
        xq = x // spatial_window  # group x into bins
        yq = y // spatial_window  # group y into bins
        tq = t // time_window  # group time into bins

        # Encode each voxel as a single 64-bit integer
        # Layout: [t bits | y bits | x bits], allows fast sorting and grouping
        voxel_id = (
                (tq.astype(np.uint64) << 42) |  # time in high bits
                (yq.astype(np.uint64) << 21) |  # y in middle bits
                xq.astype(np.uint64)  # x in low bits
        )

        # Sort voxel IDs
        # identical voxel IDs are adjacent, which simplifies counting events per voxel
        order = np.argsort(voxel_id)
        voxel_sorted = voxel_id[order]

        # Count number of events in each voxel
        diff = np.diff(voxel_sorted)  # differences between consecutive voxel IDs
        boundaries = np.concatenate(([True], diff != 0))  # True at start of each new voxel
        counts = np.diff(
            np.append(np.where(boundaries)[0], len(voxel_sorted)))  # run lengths = number of events per voxel

        # Map counts back to each event
        counts_per_event = np.repeat(counts, counts)  # each event gets the count of its voxel
        keep_sorted = counts_per_event > 1  # keep only events in voxels with >1 event

        # Restore original event order
        keep = np.zeros(len(t), dtype=bool)
        keep[order] = keep_sorted


        print(f"Filtered events: {keep.sum()}")
        print(f"Percentage of filtered out events: {round((len(t) - keep.sum()) / len(t) * 100, 3)}")
        print(f"Spatial window: {spatial_window}")
        print(f"Time window: {time_window}")

        # Return filtered events
        return x[keep], y[keep], t[keep], p[keep]

    @staticmethod
    def Neighbor_Activity_Filter(x, y, t, p, spatial_window=10, time_window=500): 
        
        """Not featured in the GUI due to its computational intensity, but can be used for aggressive noise reduction when needed."""
        
        """
        Activity filter that removes events without nearby neighbors in space and time.
        Uses KDTree for efficient neighbor search - much faster than naive approach.

        Args:
            t: Event timestamps (microseconds)
            x: Event x coordinates
            y: Event y coordinates
            p: Event polarities
            spatial_window: Size of spatial neighborhood (pixels)
            time_window: Time window for neighborhood search (microseconds)

        Returns:
            Filtered arrays (t, x, y, p)
        """
        print(f'Initial events: {len(t)}')
        print(f'Activity filter: {spatial_window}x{spatial_window} spatial window, {time_window}µs time window')

        # Convert to numpy arrays with appropriate dtypes
        t = np.array(t, dtype=np.float64)
        x = np.array(x, dtype=np.int32)
        y = np.array(y, dtype=np.int32)
        p = np.array(p)

        # Scale time to spatial units (1 pixel = time_window/spatial_window microseconds)
        # This allows using a single radius for both spatial and temporal distance
        time_scale = spatial_window / time_window
        t_scaled = t * time_scale

        # Create 3D points: (x, y, t_scaled)
        points = np.column_stack((x, y, t_scaled))

        # Build KDTree for fast neighbor queries
        print("Building KDTree...")
        tree = cKDTree(points)

        # Query radius: half the spatial window in each dimension
        # Using Chebyshev distance (max of absolute differences) for box-shaped neighborhood
        radius = spatial_window / 2.0

        # For each point, count neighbors within radius (including itself)
        print("Querying neighbors...")
        neighbor_counts = tree.query_ball_point(points, r=radius, p=np.inf, return_length=True)

        # Keep events that have at least 2 points in neighborhood (itself + 1 neighbor)
        keep_mask = neighbor_counts >= 2

        # Apply filter
        filtered_t = t[keep_mask]
        filtered_x = x[keep_mask]
        filtered_y = y[keep_mask]
        filtered_p = p[keep_mask]

        print(f'Filtered events: {len(filtered_t)} ({100 * len(filtered_t) / len(t):.1f}% kept)')

        # Return filtered events
        return filtered_x, filtered_y, filtered_t, filtered_p

    @staticmethod
    def Voxel_Density_Filter(x, y, t, p, spatial_window=20, time_window=500, percentile=40, seed=None, alpha=0.0001):
        """
        Adaptive voxel density filter that reduces event clutter by thinning densely populated regions.

        Not all dense regions are fully removed — instead, events in dense voxels are probabilistically
        kept based on a threshold, preserving sparse voxels entirely.

        Args:
            x: Event x coordinates
            y: Event y coordinates
            t: Event timestamps
            p: Event polarities
            spatial_window: Size of each voxel in spatial units (pixels)
            time_window: Size of each voxel in temporal units (microseconds)
            percentile: Percentile to determine dense voxels (adaptive threshold)
            seed: Random seed for reproducibility
            alpha: Retention factor for events in dense voxels

        Returns:
            Filtered arrays: x, y, t, p
        """
        print("Adaptive voxel density filter executed")
        print(f"Initial events: {len(t)}")

        # Initialize random number generator for reproducible thinning
        # seed=None, filtering not reproducible
        rng = np.random.default_rng(seed)

        # Quantize into voxels
        # Divide space and time into discrete bins
        xq = x // spatial_window
        yq = y // spatial_window
        tq = t // time_window

        # Encode voxel coordinates into a single uint64 integer for fast grouping (t | y | x)
        voxel_id = (
                (tq.astype(np.uint64) << 42) |
                (yq.astype(np.uint64) << 21) |
                xq.astype(np.uint64)
        )

        # Count events per voxel
        # Sort voxel IDs to group identical voxels together
        order = np.argsort(voxel_id)
        voxel_sorted = voxel_id[order]

        # Detect where voxel IDs change to identify voxel boundaries
        diff = np.diff(voxel_sorted)
        boundaries = np.concatenate(([True], diff != 0))
        voxel_starts = np.where(boundaries)[0]
        voxel_starts = np.append(voxel_starts, len(voxel_sorted))

        # Count number of events in each voxel
        counts = np.diff(voxel_starts)

        # Expand counts to match the original event array for per-event calculations
        counts_per_event = np.repeat(counts, counts)

        # Compute adaptive threshold
        # Determine the voxel density threshold Cmax based on the specified percentile
        Cmax = np.percentile(counts, percentile)
        print(f"Adaptive voxel threshold (Cmax) = {Cmax}")

        # Probabilistic thinning
        # Start with all events fully retained
        prob = np.ones_like(counts_per_event, dtype=float)

        # Identify dense voxels where counts exceed the threshold
        dense_mask = counts_per_event > Cmax

        # Assign retention probability for events in dense voxels:
        # P_keep = alpha * (Cmax / voxel_count)
        # Very dense voxels retain fewer events, voxels just above threshold retain more
        prob[dense_mask] = alpha * (Cmax / counts_per_event[dense_mask])

        # Randomly decide which events to keep based on their probability
        keep_sorted = rng.random(len(prob)) < prob

        # Map back to original event order
        # Create boolean mask for the original input order
        keep = np.zeros(len(t), dtype=bool)
        keep[order] = keep_sorted


        print("Voxel density stats:", np.min(counts), np.median(counts), np.max(counts))
        print(f"Filtered events: {keep.sum()}")
        print(f"Percentage of filtered out events: {round((len(t) - keep.sum()) / len(t) * 100, 3)}")
        print(f"Spatial window: {spatial_window}")
        print(f"Time window: {time_window}")

        # Return filtered events
        return x[keep], y[keep], t[keep], p[keep]


    @staticmethod
    def Subsampling_Filter(x, y, t, p, H, W, tau_us=40000.0, filter_size=7, sampling_threshold=0.3, seed=None):
        """
        Apply spatiotemporal density filter to event data using ultra-fast numba-optimized processing. Not featured in the GUI due to its aggressive nature and potential for over-filtering, but serves as a powerful tool for extreme noise reduction when needed.
        """
        assert filter_size % 2 == 1, "filter_size must be odd"
        print(f"Initial events: {len(t)}")
        print(f"Density filter: {filter_size}x{filter_size}, tau={tau_us}us, threshold={sampling_threshold}")

        # Convert to numpy arrays with efficient dtypes
        x = np.asarray(x, dtype=np.int32)
        y = np.asarray(y, dtype=np.int32)
        t = np.asarray(t, dtype=np.float32)
        p = np.asarray(p) 
        H = H + 1
        W = W + 1

        if seed is None:
            seed = 0

        # Sort by time
        print("Sorting events by time...")
        s = np.argsort(t, kind="quicksort")
        p01 = (p[s] > 0).astype(np.int8) if np.min(p) < 0 else (p[s] > 0.5).astype(np.int8)

        K = filter_size // 2
        sigma = filter_size / 5.0
        ax = np.arange(-K, K + 1, dtype=np.float32)
        xx, yy = np.meshgrid(ax, ax, indexing="xy")
        g = np.exp(-(xx * xx + yy * yy) / (2.0 * sigma * sigma)).astype(np.float32)
        g /= (g.sum() + 1e-12)

        ###-----------------------------------------------------------------------------------------------
        ### NUMBAJIT 
        ### ----------------------------------------------------------------------------------------------

        @numba.jit(nopython=True, parallel=False)
        def _density_filter_kernel_fast(x, y, t, p01, s, H, W, K, g, tau_us, sampling_threshold, seed):
            np.random.seed(seed)
            acc = np.zeros((2, H, W), dtype=np.float32)
            last_time = np.full((2, H, W), -1.0e10, dtype=np.float32)
            keep_s = np.zeros(len(s), dtype=np.bool_)

            g_flat = g.ravel()

            for i in range(len(s)):
                idx = s[i]
                pp = int(p01[i])
                xi, yi = int(x[idx]), int(y[idx])
                ti = t[idx]

                if xi < 0 or xi >= W or yi < 0 or yi >= H:
                    continue

                y0 = max(yi - K, 0)
                y1 = min(yi + K, H - 1)
                x0 = max(xi - K, 0)
                x1 = min(xi + K, W - 1)

                # Vectorized decay: compute decay factor once for this time
                dt_inv = 1.0 / tau_us if tau_us > 0 else 1.0

                # Decay and accumulate in one pass
                fv = 0.0
                patch_idx = 0
                for yy in range(y0, y1 + 1):
                    for xx in range(x0, x1 + 1):
                        # Compute decay for this pixel
                        time_diff = ti - last_time[pp, yy, xx]
                        lag = np.exp(-time_diff * dt_inv)
                        acc[pp, yy, xx] *= lag

                        # Accumulate with Gaussian weight
                        if xx == xi and yy == yi:
                            acc[pp, yy, xx] += 1.0
                            last_time[pp, yy, xx] = ti

                        # Add to density
                        gy = yy - y0 + (y0 - (yi - K))
                        gx = xx - x0 + (x0 - (xi - K))
                        if 0 <= gy < g.shape[0] and 0 <= gx < g.shape[1]:
                            fv += acc[pp, yy, xx] * g_flat[gy * g.shape[1] + gx]
                        patch_idx += 1

                # Update center pixel after density calculation
                if acc[pp, yi, xi] == 0:
                    acc[pp, yi, xi] = 1.0
                    last_time[pp, yi, xi] = ti

                # Probabilistic sampling
                prob = min(1.0,
                        max(0.0,
                            sampling_threshold * fv))
                keep_s[i] = np.random.rand() < prob

            return keep_s
        
        
        ###-----------------------------------------------------------------------------------------------
        
        # Run ultra-optimized kernel
        print("Processing events with fast numba kernel...")
        keep_s = _density_filter_kernel_fast(x, y, t, p01, s, H, W, K, g, tau_us, sampling_threshold, seed)

        keep = np.zeros(len(t), dtype=bool)
        keep[s] = keep_s

        xf, yf, tf, pf = x[keep], y[keep], t[keep], p[keep]

        n0, n1 = len(t), len(tf)
        removed = n0 - n1
        print(f"Events before:  {n0}")
        print(f"Events removed: {removed}")
        print(f"Events after:   {n1}")
        print(f"Filtered out:   {100*removed/max(1,n0):.2f}%")

        return xf, yf, tf, pf

    @staticmethod
    def Median_Filter(x, y, t, p, spatial_window=100, time_window=100):
        """
        Median-based activity filter that removes events in sparsely populated voxels.
        Uses voxel quantization and adaptive median thresholding to filter out isolated events.

        Args:
            x: Event x coordinates
            y: Event y coordinates
            t: Event timestamps (microseconds)
            p: Event polarities
            spatial_window: Size of spatial voxel (pixels, default 100)
            time_window: Size of temporal voxel (microseconds, default 100)

        Returns:
            Filtered event arrays (x, y, t, p)
        """
        print("Median filter executed")
        print(f"Initial events: {len(t)}")

        # Quantize coordinates into voxels
        xq = x // spatial_window  # group x into bins
        yq = y // spatial_window  # group y into bins
        tq = t // time_window  # group time into bins

        # Encode each voxel as a single 64-bit integer
        # Layout: [t bits | y bits | x bits]
        voxel_id = (
                (tq.astype(np.uint64) << 42) |  # time in high bits
                (yq.astype(np.uint64) << 21) |  # y in middle bits
                xq.astype(np.uint64)  # x in low bits
        )

        # Sort voxel IDs
        # identical voxel IDs are adjacent for efficient counting
        order = np.argsort(voxel_id)
        voxel_sorted = voxel_id[order]

        # Count number of events per voxel
        diff = np.diff(voxel_sorted)  # differences between consecutive voxel IDs
        boundaries = np.concatenate(([True], diff != 0))  # True at start of each new voxel
        counts = np.diff(
            np.append(np.where(boundaries)[0], len(voxel_sorted)))  # run lengths = number of events per voxel

        # Map counts back to each event
        counts_per_event = np.repeat(counts, counts)  # each event gets the count of its voxel

        # Adaptive Median Threshold
        median_count = np.median(counts)  # median voxel occupancy
        threshold = max(2, median_count)  # remove isolated singletons or sparse voxels
        keep_sorted = counts_per_event >= threshold  # mark events to keep

        # Restore original event order
        keep = np.zeros(len(t), dtype=bool)
        keep[order] = keep_sorted


        print(f"Filtered events: {keep.sum()}")
        print(f"Percentage of filtered out events: {round((len(t) - keep.sum()) / len(t) * 100, 3)}")
        print(f"Spatial window: {spatial_window}")
        print(f"Time window: {time_window}")
        print(f"Median voxel occupancy: {median_count}")
        print(f"Threshold used: {threshold}")

        # Return filtered events
        return x[keep], y[keep], t[keep], p[keep]





