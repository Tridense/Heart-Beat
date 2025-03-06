import json
import matplotlib.pyplot as plt
import os
import numpy as np
import seaborn as sns
from datetime import datetime, timedelta

time_back = 7 # Days back to show on plots.

def read_json_data(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def filter_recent_entries(json_directory):
    """
    Filters all JSON files in a directory to only include data from the last 7 days.
    Returns a dictionary where keys are user IDs (from filenames) and values are lists of filtered entries.
    """
    seven_days_ago = datetime.utcnow().timestamp() - (time_back * 24 * 60 * 60)
    filtered_data = {}

    for file in os.listdir(json_directory):
        if file.endswith(".json"):
            user_id = os.path.splitext(file)[0]  # Extract user ID from filename
            file_path = os.path.join(json_directory, file)

            with open(file_path, "r") as f:
                data = json.load(f)

            # Keep only entries from the last 7 days
            recent_entries = [entry for entry in data if entry[-1] >= seven_days_ago]

            if recent_entries:
                filtered_data[user_id] = recent_entries

    return filtered_data

def extract_segments(data):
    segments = []
    current_segment = []
    start_new_segment = True

    for row in data:
        if row[0] == 0.0 and row[1] == 0.0:
            if start_new_segment:
                current_segment = [(0.0, 0.0)]
                start_new_segment = False
            else:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
                start_new_segment = True
        else:
            current_segment.append((row[0], row[1]))

    if current_segment:
        segments.append(current_segment)

    return segments

def calculate_derivative(segment):
    return [(segment[i][1] - segment[i - 1][1]) / (segment[i][0] - segment[i - 1][0])
            for i in range(1, len(segment)) if segment[i][0] - segment[i - 1][0] != 0]

################################################################################
# Plot Functions
################################################################################

def plot_line(json_directory, file_name, users_dict):
    """Plots rerolling runs as a line graph with only recent data."""
    recent_data = filter_recent_entries(json_directory).get(file_name, [])

    if not recent_data:
        print(f"No recent data for {file_name}.")
        return

    segments = extract_segments(recent_data)

    plt.figure(figsize=(10, 6))
    for i, segment in enumerate(segments):
        x_values = [point[0] for point in segment]
        y_values = [point[1] for point in segment]
        ign = users_dict.get(file_name, f"Unknown ({file_name})")
        plt.plot(x_values, y_values, marker='.', label=f'Segment {i + 1} - {ign}')

    plt.xlabel('Time [min.]')
    plt.ylabel('Packs')
    plt.title(f'Rerolling runs from: {users_dict.get(file_name, file_name)} (Last {time_back} Days)')
    plt.grid(True)

def plot_histogram(json_directory, file_name, users_dict):
    """Plots a histogram of packs per hour with only recent data."""
    recent_data = filter_recent_entries(json_directory).get(file_name, [])

    if not recent_data:
        print(f"No recent data for {file_name}.")
        return

    segments = extract_segments(recent_data)

    # Compute derivatives and filter out negatives
    all_derivatives = np.array([d for segment in segments for d in calculate_derivative(segment)]) * 60
    all_derivatives = all_derivatives[all_derivatives > 0]  # Keep only positive values

    if all_derivatives.size == 0:
        print(f"No valid data for histogram: {file_name}.")
        return

    plt.figure(figsize=(10, 6))
    plt.hist(all_derivatives, bins=20, edgecolor='black', alpha=0.5)
    plt.xlabel('Packs per Hour')
    plt.ylabel('Frequency')
    plt.title(f'Rate of packs from: {users_dict.get(file_name, file_name)} (Last {time_back} Days)')
    plt.grid(True)

def plot_pie(json_directory, users_dict):
    """Plots a sorted pie chart of total valid packs acquired by players in the last 7 days."""
    recent_data = filter_recent_entries(json_directory)

    if not recent_data:
        print("No recent data found.")
        return

    player_packs = {user_id: sum(row[3] for row in data if row[3] > 0) for user_id, data in recent_data.items()}
    player_packs = {users_dict.get(pid, f"Unknown ({pid})"): packs for pid, packs in player_packs.items() if packs > 0}

    if not player_packs:
        print("No valid pack data after filtering.")
        return

    sorted_players = sorted(player_packs.items(), key=lambda x: x[1], reverse=True)
    total_packs = sum(packs for _, packs in sorted_players)
    threshold = total_packs * 0.02

    main_players = [(name, packs) for name, packs in sorted_players if packs >= threshold]
    other_packs = sum(packs for name, packs in sorted_players if packs < threshold)

    if other_packs > 0:
        main_players.append(("Other", other_packs))

    labels, values = zip(*main_players)

    plt.figure(figsize=(8, 6))
    plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    pie_title = f'Share of Packs Acquired by Re-rollers (Last {time_back} Days)'
    plt.title(pie_title)

def plot_boxplot(json_directory, users_dict):
    """Plots a boxplot of valid, recent data for top users."""
    recent_data = filter_recent_entries(json_directory)

    if not recent_data:
        print("No recent data found.")
        return

    user_derivatives = {}

    for user_id, data in recent_data.items():
        segments = extract_segments(data)

        # Calculate derivatives for all segments
        derivatives = np.concatenate(
            [np.array(calculate_derivative(segment)) * 60 for segment in segments]
        )

        # Filter out invalid values (≤0) and outliers above 500
        derivatives = derivatives[(derivatives > 0) & (derivatives <= 500)]

        if len(derivatives) > 0:
            user_derivatives[user_id] = derivatives

    if not user_derivatives:
        print("No valid data after filtering.")
        return

    # Rank users by median packs per hour
    user_ranking = [(user_id, np.median(derivatives)) for user_id, derivatives in user_derivatives.items()]
    user_ranking.sort(key=lambda x: x[1], reverse=True)

    # Select the top users
    top_users = user_ranking[:]

    # Prepare data for the boxplot
    boxplot_data = []
    labels = []
    for user_id, _ in top_users:
        ign = users_dict.get(user_id, f"({user_id})")
        labels.append(ign)
        boxplot_data.append(user_derivatives[user_id])

    # Plot the boxplot
    plt.figure(figsize=(16, 9))
    sns.boxplot(data=boxplot_data, palette="turbo", showfliers=False)
    plt.xticks(ticks=range(len(labels)), labels=labels, rotation=45, ha='right')
    plt.xlabel('Re-roller')
    plt.ylabel('Packs per Hour')
    boxplot_title = f'Top Re-rollers: Distribution of Packs per Hour (Last {time_back} Days)'
    plt.title(boxplot_title)
    plt.grid(True)
    plt.tight_layout()

def plot_density(json_directory):
    """Plots the density of valid, recent entries."""
    recent_data = filter_recent_entries(json_directory)

    if not recent_data:
        print("No recent data found.")
        return

    all_derivatives = np.concatenate(
        [np.array([d for segment in extract_segments(entries)
                   for d in calculate_derivative(segment)]) * 60
         for entries in recent_data.values()]
    )

    # Filter out false values
    all_derivatives = all_derivatives[(all_derivatives > 0) & (all_derivatives <= 500)]

    if all_derivatives.size == 0:
        print("No valid positive data found.")
        return

    plt.figure(figsize=(10, 6))
    sns.kdeplot(all_derivatives, fill=True, color='blue', alpha=0.5)
    plt.xlabel('Packs per Hour')
    plt.ylabel('Density')
    density_title = f'Density Plot of Packs per Hour (Last {time_back} Days)'
    plt.title(density_title)
    plt.grid(True)