'''
First Draft for 3D Visualization:
    Input:
        from Loading_Data: x, y, t, and p values
        from User: start time and time duration
    Output:
        3D plot
'''

import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from matplotlib.colors import ListedColormap
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.lines import Line2D


class Event3DVisualization:

    @staticmethod
    def plot_positive_event_3d(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot of positive events (p=1) in a time window."""
        mask = (t_values >= t_start) & (t_values <= t_start + t_duration) & (p_values == 1)

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")

        ax.clear()
        ax.scatter(x_values[mask], t_values[mask], y_values[mask], color="red",s=1)
        ax.set_title("Positive 3D Visualization (p = 1)")
        ax.set_xlabel("X", labelpad=10)
        ax.set_ylabel("Time", labelpad=10)
        ax.set_zlabel("Y", labelpad=10)
        ax.invert_zaxis()  # Invert z-axis to match typical image coordinates

        if ax is None:
            plt.show()

    @staticmethod
    def plot_negative_event_3d(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot of negative events (p=0) in a time window."""
        mask = (t_values >= t_start) & (t_values <= t_start + t_duration) & (p_values == 0)
    
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")

        ax.clear()
        ax.scatter(x_values[mask], t_values[mask], y_values[mask] , color="blue",s=1)
        ax.set_title("Negative 3D Visualization (p = 0)")
        ax.set_xlabel("X", labelpad=10)
        ax.set_ylabel("Time", labelpad=10)
        ax.set_zlabel("Y", labelpad=10)
        ax.invert_zaxis()  # Invert z-axis to match typical image coordinates
       
        if ax is None:
            plt.show()

    @staticmethod
    def plot_total_event_3d(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot of all events in a time window (no p distinction)."""
        mask = (t_values >= t_start) & (t_values <= t_start + t_duration)

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")

        ax.clear()
        ax.scatter(x_values[mask], t_values[mask], y_values[mask], color="grey",s=1)
        ax.set_title("Total 3D Visualization (no differentiation)")
        ax.set_xlabel("X", labelpad=10)
        ax.set_ylabel("Time", labelpad=10)
        ax.set_zlabel("Y", labelpad=10)
        ax.invert_zaxis()  # Invert z-axis to match typical image coordinates

        if ax is None:
            plt.show()

    @staticmethod
    def plot_both_events_3d(x_values, y_values, t_values, p_values, t_start, t_duration, ax=None):
        """3D plot showing positive (red) and negative (blue) events."""
        mask = (t_values >= t_start) & (t_values <= t_start + t_duration)
        cmap = ListedColormap(["blue", "red"])  # 0 = blue, 1 = red

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")

        ax.clear()
        ax.scatter(x_values[mask], t_values[mask], y_values[mask], c=p_values[mask], cmap=cmap,s=1)
        ax.set_title("Positive & Negative 3D Visualization")
        ax.set_xlabel("X", labelpad=10)
        ax.set_ylabel("Time", labelpad=10)
        ax.set_zlabel("Y", labelpad=10)
        ax.invert_zaxis()  # Invert z-axis to match typical image coordinates

        # --- Add legend using proxy artists ---
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='Negative',
                   markerfacecolor='blue', markersize=8),
            Line2D([0], [0], marker='o', color='w', label='Positive',
                   markerfacecolor='red', markersize=8)
        ]
        ax.legend(handles=legend_elements,
          loc="upper right",
          bbox_to_anchor=(1, 0.95))  # move slightly down

        if ax is None:
            plt.show()
