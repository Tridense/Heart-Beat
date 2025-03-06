import discord
from discord.ext import commands, tasks
import time
import re
import os
from dotenv import load_dotenv
import json
from collections import defaultdict
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from chartmaker_2_2 import plot_line, plot_histogram, plot_pie, read_json_data, extract_segments, \
    plot_boxplot, plot_density
import pandas as pd
import asyncio
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
# Set up bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True  # Enable the GUILD_MEMBERS intent
bot = commands.Bot(command_prefix="/", intents=intents)

################################################################################
# Configuration Variables
################################################################################
TARGET_USER_ID = 810203371486707732  # Replace with the user's ID
SOURCE_CHANNEL_ID = 984469411815624714  # Replace with the channel to read messages from
DESTINATION_CHANNEL_ID = 1331992584993771551  # Replace with the channel to send messages to
WARNING_CHANNEL_ID = 1331992584993771551  # Replace with the warning channel's ID
MODERATOR_ROLE =  [1131602502576513114, 123, 123]  # Replace with the role ID required to react. Add as many as you need.

# Define the forum channel ID and the tag IDs to exclude for the /mythreads command.
forum_channel_id = 1336665583940407296
exclude_tag_id_1 = 1336668304009330711  # Expired tag ID
exclude_tag_id_2 = 1336665901642158102  # Dead tag ID

YOUR_BOT_TOKEN = os.getenv("YOUR_DISCORD_TOKEN")
SPECIFIC_EMOJI = "🧪"  # Replace with the desired emoji
SUCCESS_EMOJI = "📝"  # Replace with the desired emoji
if not YOUR_BOT_TOKEN:
    raise ValueError("Bot token not found. Please set DISCORD_BOT_TOKEN in .env file.")

# Timing and Limits
EDIT_LOOP_TIMER = 30  # Message update frequency
OFFLINE_TIMER = 60 * 33  # 33 minutes offline threshold
INSTANCE_BOLD_LIMIT = 4  # Min instances per user before warning
PPH_WARNING_LIMIT = 100 # Min packs per hour limit
WARNING_COOLDOWN = 2 * 60 * 60  # 2-hour cooldown for warnings

################################################################################
# Data Storage
################################################################################
user_messages = {}
allowed_mentions = discord.AllowedMentions(users=True)
latest_sent_message = None
last_warning_timestamps = {}
message_reactions = {} # Dictionary to track reactions per message
user_fourth_line_data = defaultdict(list) # Dictionary to store user data as a matrix
user_fourth_line_data = {} # Dictionary to store user data as numpy arrays
DATA_FOLDER = Path("userdata")
DATA_FOLDER.mkdir(parents=True, exist_ok=True)  # Creates the folder if missing
TESTERS_FOLDER = Path("testers")
TESTERS_FOLDER.mkdir(parents=True, exist_ok=True)  # Creates the folder if missing
DELETE_USERDATA_FOLDER = Path("deleted_userdata")
DELETE_USERDATA_FOLDER.mkdir(parents=True, exist_ok=True) # Creates the folder if missing
DELETED_TESTERS_FOLDER = Path("deleted_testers")
DELETED_TESTERS_FOLDER.mkdir(parents=True, exist_ok=True) # Creates the folder if missing
USERNAMES_DIRECTORY = "C:/Path/To/users.csv" # Where usernames are stored for the chart generation.
# Stored in a CSV as "IGN","Friend_ID","Discord_ID","Godpacks","Livepacks","Timezone","Usernames","Last_Online"
# Only need to store IGN and Discord_ID for this command. Example line in CSV: "Ingame name","","Discord_ID","","","","",""

################################################################################
# Helper Functions
################################################################################
def increment_reaction_count(user_id, reactor_id):
    """Adds a new reaction entry to the user's JSON file."""
    file_path = TESTERS_FOLDER / f"{user_id}.json"

    # Load existing data or initialize an empty list
    if file_path.exists():
        with open(file_path, "r") as f:
            data = json.load(f)
    else:
        data = []

    # Create a new reaction entry
    reaction_number = len(data) + 1  # Increment reaction number
    timestamp = int(time.time())  # Current Unix timestamp
    new_entry = [reaction_number, timestamp, str(reactor_id)]  # New row

    # Append the new entry to the list
    data.append(new_entry)

    # Save the updated data back to the JSON file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

async def get_channel(channel_id):
    return discord.utils.get(bot.get_all_channels(), id=channel_id)

async def send_pph_warning(user_id, pph):
    current_time = int(time.time())
    last_warning_time_2 = last_warning_timestamps.get(user_id, 0)
    display_id = user_id.split('-')[0]
    alt_text = " alt's" if "-" in user_id else ""  # Add ALT if user_id ends with -1

    if current_time - last_warning_time_2 >= WARNING_COOLDOWN:
        warning_channel = await get_channel(WARNING_CHANNEL_ID)
        if warning_channel:
            warning_message = (f"<@{display_id}> Alert: Your{alt_text} packs per hour is {round(pph)} (Less than {PPH_WARNING_LIMIT}). "
                               "Please check your setup.")
            await warning_channel.send(warning_message, allowed_mentions=allowed_mentions)
            last_warning_timestamps[user_id] = current_time
            print(f"PPH Warning sent to <@{user_id}>")

async def send_message_list():
    global latest_sent_message
    channel = await get_channel(DESTINATION_CHANNEL_ID)
    if not channel:
        return

    message_list, total_instances, total_pph = [], 0, 0
    current_time = int(time.time())

    active_messages = {msg_id: data for msg_id, data in user_messages.items()
                       if current_time - int(data["timestamp"].split(":")[1]) <= OFFLINE_TIMER}
    sorted_messages = sorted(active_messages.values(), key=lambda x: x["timestamp"], reverse=True)

    for data in sorted_messages:
        total_instances += data["second_line_numbers"]
        total_pph += data.get("pph", 0)

        # Extract the timestamp from the Discord format
        discord_timestamp = data["timestamp"]
        timestamp_value = int(discord_timestamp.split(":")[1])

        # Calculate the time difference in minutes
        time_diff_minutes = (current_time - timestamp_value) // 60

        # Format the relative time (e.g., "10m ago")
        relative_time = f"{time_diff_minutes}m"

        # Extract numeric user ID and check for ALT status
        user_id_full = data['content']  # Full ID from backend
        user_id_display = user_id_full.split('-')[0]  # Main numeric ID
        alt_text = " ALT" if "-" in user_id_full else ""  # Add ALT if user_id ends with -1
        new_text = " NEW" if data['time_user'] == 0 else ""  # Add NEW if second_line_numbers is 0

        # Build the message line
        line = f"<@{user_id_display}>{alt_text} {relative_time} {data['second_line_numbers']}/{data['tot_instances']} in. {round(data['pph'])} pph{new_text}"
        message_list.append(f"**{line}**" if data["second_line_numbers"] < INSTANCE_BOLD_LIMIT or data[
            "pph"] < PPH_WARNING_LIMIT else line)

    message_content = (f"## Latest heart beats:\n"
                       f"**{len(sorted_messages)} rollers | {total_instances} instances | {round(total_pph)} pph** \n" + "\n".join(
        message_list))

    try:
        if latest_sent_message:
            await latest_sent_message.edit(content=message_content)
        else:
            latest_sent_message = await channel.send(message_content, allowed_mentions=allowed_mentions)
    except discord.errors.HTTPException as e:
        print(f"Error sending/editing message: {e}")

def save_data_to_file(user_id):
    """Saves the user data to a JSON file."""
    file_path = os.path.join(DATA_FOLDER, f"{user_id}.json")

    # Convert NumPy arrays to lists for JSON compatibility
    data_list = user_fourth_line_data[user_id].tolist()

    with open(file_path, "w") as f:
        json.dump(data_list, f)

def load_data_from_file(user_id):
    """Loads user data from a JSON file."""
    file_path = os.path.join(DATA_FOLDER, f"{user_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            data_list = json.load(f)
        return np.array(data_list)  # Convert back to NumPy array
    return np.zeros((0, 4))  # Return an empty array if no file exists

def save_fourth_line_numbers(user_id, fourth_line_numbers):
    fln_int = [int(x) for x in fourth_line_numbers]  # Convert to integers
    fln_matrix = np.array(fln_int)  # Convert to NumPy array

    if user_id not in user_fourth_line_data:
        user_fourth_line_data[user_id] = load_data_from_file(user_id)  # Load previous data

    if user_fourth_line_data[user_id].size == 0:
        user_fourth_line_data[user_id] = np.zeros((1, len(fln_int) + 3))  # Increase size to accommodate timestamp
        user_fourth_line_data[user_id][0, :-3] = fln_int
        user_fourth_line_data[user_id][0, -1] = int(time.time())  # Add Unix timestamp
    else:
        previous_row = user_fourth_line_data[user_id][-1]
        if np.sum(fln_matrix) != 0:
            time_total = (fln_matrix[0] - previous_row[0]) + previous_row[2]
            pack_total = (fln_matrix[1] - previous_row[1]) + previous_row[3]
        else:
            last_col2, last_col3 = find_last_nonzero(user_id)
            time_total = last_col2 if last_col2 is not None else previous_row[0]
            pack_total = last_col3 if last_col3 is not None else previous_row[1]

        new_matrix = np.concatenate((fln_matrix, [time_total, pack_total, int(time.time())]), axis=0)  # Add Unix timestamp
        user_fourth_line_data[user_id] = np.vstack((user_fourth_line_data[user_id], new_matrix))

    save_data_to_file(user_id)  # Save data after every update

def find_last_nonzero(user_id):
    """Finds the last nonzero elements in column 3 (index 2) and column 4 (index 3)"""
    data = user_fourth_line_data[user_id]

    # Find the last nonzero element in column 2 (index 1) and column 3 (index 2)
    col_2_nonzero = np.where(data[:, 2] != 0)[0]  # Indices where column 2 is nonzero
    col_3_nonzero = np.where(data[:, 3] != 0)[0]  # Indices where column 3 is nonzero

    last_nonzero_col_2 = data[col_2_nonzero[-1], 2] if col_2_nonzero.size > 0 else None
    last_nonzero_col_3 = data[col_3_nonzero[-1], 3] if col_3_nonzero.size > 0 else None

    return last_nonzero_col_2, last_nonzero_col_3

def get_max_column_1(user_id):
    if user_id in user_fourth_line_data:
        data = user_fourth_line_data[user_id]
        if data.size > 0:  # Ensure data exists
            max_value = np.max(data[:, 0])  # Get the max value from column 1 (index 0)
            return max_value
    return None  # Return None if no data is found

def get_max_column_2(user_id):
    if user_id in user_fourth_line_data:
        data = user_fourth_line_data[user_id]
        if data.size > 0:  # Ensure data exists
            max_value = np.max(data[:, 1])  # Get the max value from column 2 (index 1)
            return max_value
    return None  # Return None if no data is found

def load_all_user_data():
    """Loads all user data from JSON files in the user_data directory."""
    global user_fourth_line_data
    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".json"):
            user_id = filename.replace(".json", "")
            user_fourth_line_data[user_id] = load_data_from_file(user_id)

################################################################################
# Bot Events
################################################################################
@bot.command(name="check")
async def check(ctx, user_id: str = None):
    if user_id is None:
        user_id = str(ctx.author.id)

    elif user_id.lower() == "inactive":
        current_time = int(time.time())
        inactive_users = []
        seven_days_ago = current_time - (7 * 24 * 60 * 60)

        # Get all users from userdata folder
        all_users = {file.stem for file in DATA_FOLDER.glob("*.json")}

        # Check their last test timestamp in testers folder
        for user_file in TESTERS_FOLDER.glob("*.json"):
            user_id = user_file.stem

            # Skip user IDs that contain a hyphen
            if "-" in user_id:
                continue

            if user_id in all_users:  # Ensure the user exists in userdata folder
                with open(user_file, "r") as f:
                    data = json.load(f)
                    if data and isinstance(data, list):
                        last_entry = data[-1]
                        if last_entry and len(last_entry) > 1:
                            last_timestamp = last_entry[1]
                            if last_timestamp < seven_days_ago:
                                inactive_users.append(f"<@{user_id}>")
                        else:
                            inactive_users.append(f"<@{user_id}>")
                    else:
                        inactive_users.append(f"<@{user_id}>")

        # Add users who are in userdata but not in testers
        for user_file in DATA_FOLDER.glob("*.json"):
            user_id = user_file.stem

            # Skip user IDs that contain a hyphen
            if "-" in user_id:
                continue

            tester_file = TESTERS_FOLDER / f"{user_id}.json"
            if not tester_file.exists():
                inactive_users.append(f"<@{user_id}>")

        if inactive_users:
            response = "**Users not testing for 7+ days or missing tester data:**\n" + "\n".join(inactive_users)
        else:
            response = "No inactive users found."

        await ctx.send(response, allowed_mentions=discord.AllowedMentions(users=False))
        return

    elif user_id.lower() == "testers":  # New command to list all tester data
        tester_files = list(TESTERS_FOLDER.glob("*.json"))
        if not tester_files:
            await ctx.send("No tester data available.")
            return

        testers_data = []
        for file in tester_files:
            tester_id = file.stem  # Extract user ID from filename
            with open(file, "r") as f:
                data = json.load(f)
                # Get the first number in the last entry (reaction_count)
                reaction_count = data[-1][0] if data else 0
                testers_data.append((tester_id, reaction_count))

        # Define grouping ranges
        grouping_ranges = {
            "0-10 tests": (0, 10),
            "11-50 tests": (11, 50),
            "51-100 tests": (51, 100),
            "101-200 tests": (101, 200),
            "201+ tests": (201, float('inf'))
        }

        # Group testers by their pack test counts
        grouped_testers = {group: [] for group in grouping_ranges.keys()}
        for tester_id, reaction_count in testers_data:
            for group, (min_tests, max_tests) in grouping_ranges.items():
                if min_tests <= reaction_count <= max_tests:
                    grouped_testers[group].append((tester_id, reaction_count))
                    break

        # Build the response message
        response = "**Tester Data (Grouped by Pack Tests):**\n"
        for group, testers in grouped_testers.items():
            if testers:
                response += f"\n**{group}:**\n"
                for tester_id, reaction_count in testers:
                    response += f"<@{tester_id}> {reaction_count} packs\n"

        await ctx.send(response, allowed_mentions=discord.AllowedMentions(users=False))
        return

    elif user_id.lower() == "all":  # Handle "all" case first
        total_time = 0
        total_packs = 0

        if not user_fourth_line_data:  # Ensure there is data
            await ctx.send("No data available for the server.")
            return

        for user_data in user_fourth_line_data.values():
            if user_data.size > 0:
                last_entry = user_data[-1]  # Get the last row
                total_time += last_entry[2] if len(last_entry) > 2 else 0
                total_packs += last_entry[3] if len(last_entry) > 3 else 0

        response = (f"**Server total:**\n"
                    f"**Total time:** {round(total_time)}\n"
                    f"**Total packs:** {round(total_packs)}")
        await ctx.send(response)
        return

    elif user_id.lower() == "top":  # Handle "top" case

        top_users = []

        # Read from stored files instead of cached data

        for file in DATA_FOLDER.glob("*.json"):

            uid = file.stem

            with open(file, "r") as f:

                try:

                    data = json.load(f)

                    if data and isinstance(data, list) and len(data[-1]) > 3:
                        last_packs = data[-1][3]  # Get total packs from last entry

                        top_users.append((uid, last_packs))

                except json.JSONDecodeError:

                    continue  # Skip corrupted JSON files

        # Sort by total packs and get top 20

        top_users = sorted(top_users, key=lambda x: x[1], reverse=True)[:20]

        if not top_users:

            response = "No data available for top users."

        else:

            response = "**Top 20 users by total packs:**\n"

            for rank, (uid, packs) in enumerate(top_users, start=1):
                response += f"**{rank}.** <@{uid}> - {round(packs)} packs\n"

        await ctx.send(response, allowed_mentions=discord.AllowedMentions(users=False))

        return

    else:
        # Preserve hyphens in user_id
        user_id = re.sub(r'[^\d-]', '', user_id)  # Strip non-digit and non-hyphen characters

    # Check for normal user data
    if user_id in user_fourth_line_data:
        data = user_fourth_line_data[user_id]
        last_entry = data[-1] if data.size > 0 else []
        last_col_1 = last_entry[0] if len(last_entry) > 0 else 0
        last_col_2 = last_entry[1] if len(last_entry) > 1 else 0
        last_col_3 = last_entry[2] if len(last_entry) > 2 else 0
        last_col_4 = last_entry[3] if len(last_entry) > 3 else 0
        max_value_1 = get_max_column_1(user_id)
        max_value_2 = get_max_column_2(user_id)

        response = (f"**User ID:** {user_id}\n"
                    f"**Current session:**\nTime: {round(last_col_1)} Packs: {round(last_col_2)}\n"
                    f"**Total:**\nTime: {round(last_col_3)} Packs: {round(last_col_4)}\n"
                    f"**Record session:**\nTime: {round(max_value_1)} Packs: {round(max_value_2)}\n")
    else:
        response = f"No data found for User ID: {user_id}\n"

    # Check for tester data
    tester_file = TESTERS_FOLDER / f"{user_id}.json"
    if tester_file.exists():
        with open(tester_file, "r") as f:
            tester_data = json.load(f)
            # Get the first number in the last entry (reaction_count)
            reaction_count = tester_data[-1][0] if tester_data else 0
            response += f"**Tester data:**\nPack tests: {reaction_count}"

    await ctx.send(response, allowed_mentions=discord.AllowedMentions(users=False))

@bot.command(name="pokechart")
async def pokechart(ctx, chart_type: str = "line", user_id: str = None):

    # Load user data
    users_df = pd.read_csv(USERNAMES_DIRECTORY)
    users_dict = dict(zip(users_df["Discord_ID"].astype(str), users_df["IGN"]))

    # Determine user ID
    user_id_base = str(ctx.author.id) if user_id is None else "".join(filter(str.isdigit, user_id))

    # Find all related IDs (main + alts)
    related_ids = [file.stem for file in Path(DATA_FOLDER).glob("*.json") if file.stem.startswith(user_id_base)]

    # Combine all related user data into a single dataset
    combined_data = []
    for uid in related_ids:
        file_path = os.path.join(DATA_FOLDER, f"{uid}.json")
        if os.path.exists(file_path):
            combined_data.extend(read_json_data(file_path))

    if not combined_data:
        await ctx.send(f"No data found for User ID `{user_id_base}`.")
        return

    segments = extract_segments(combined_data)
    plt.switch_backend('Agg')

    # Generate the specified chart
    chart_name = "chart.png"
    if chart_type.lower() == "line":
        plot_line(DATA_FOLDER, user_id_base, users_dict)  # Pass DATA_FOLDER instead of segments
    elif chart_type.lower() == "histogram":
        plot_histogram(DATA_FOLDER, user_id_base, users_dict)
    elif chart_type.lower() == "pie":
        plot_pie(DATA_FOLDER, users_dict)
    elif chart_type.lower() == "boxplot":
        plot_boxplot(DATA_FOLDER, users_dict)
    elif chart_type.lower() == "density":
        plot_density(DATA_FOLDER)
    else:
        await ctx.send("Invalid chart type. Available types: line, histogram, pie, boxplot, density.")
        return

    plt.savefig(chart_name)
    plt.close()

    with open(chart_name, "rb") as f:
        picture = discord.File(f)
        await ctx.send(file=picture)

    os.remove(chart_name)

@bot.command(name="mythreads")
async def my_threads(ctx):
    """
    Lists all threads in the specified forum channel where the user is currently following,
    excluding threads with specific tags, closed threads, and threads older than 48 hours.
    Threads are sorted by creation time (newest to oldest).
    """
    # Send an immediate response to indicate the bot is working
    fetch_message = await ctx.send("Fetching posts...")

    # Fetch the forum channel
    forum_channel = bot.get_channel(forum_channel_id)
    if not isinstance(forum_channel, discord.ForumChannel):
        await fetch_message.edit(content="The specified channel is not a forum channel.")
        return

    # Fetch all threads in the forum channel
    threads = forum_channel.threads

    if not threads:
        await fetch_message.edit(content="No threads found in the specified forum channel.")
        return

    # Get the current time and calculate the cutoff time (48 hours ago)
    current_time = discord.utils.utcnow()
    cutoff_time = current_time - timedelta(hours=48)

    # Filter threads where the user is currently a member (following), do not have the excluded tags,
    # are not older than 48 hours, and are not closed
    user_threads = []
    for thread in threads:
        # Skip threads older than 48 hours
        if thread.created_at < cutoff_time:
            continue

        # Skip threads that have the excluded tags
        if any(tag.id == exclude_tag_id_1 for tag in thread.applied_tags):
            continue
        if any(tag.id == exclude_tag_id_2 for tag in thread.applied_tags):
            continue

        # Skip closed threads
        if thread.archived or thread.locked:
            continue

        # Fetch the thread's members to check if the user is in the thread
        try:
            # Add a small delay to avoid rate limits
            await asyncio.sleep(0.5)  # 0.5-second delay between API calls

            thread_members = await thread.fetch_members()
            # Check if the user is in the thread's members
            if any(member.id == ctx.author.id for member in thread_members):
                user_threads.append(thread)
        except discord.Forbidden:
            continue  # Skip threads the bot cannot access
        except discord.HTTPException as e:
            print(f"HTTPException while fetching thread members: {e}")
            continue  # Skip threads that cause errors

    if not user_threads:
        await fetch_message.edit(content=f"You are not currently following any threads in <#{forum_channel_id}> (excluding threads with the specified tags, closed threads, and older than 48 hours).")
        return

    # Sort threads by creation time (newest to oldest)
    user_threads.sort(key=lambda thread: thread.created_at, reverse=True)

    # Extract the numeric part of the thread titles
    numeric_titles = []
    for thread in user_threads:
        # Extract the numeric part from the thread title using regex
        match = re.search(r"\((\d+)\)", thread.name)
        if match:
            numeric_titles.append(match.group(1))  # Extract the numeric part
        else:
            numeric_titles.append(thread.name)  # Fallback to the full title if no numeric part is found

    # Create a list of numeric titles
    thread_list = [f"{i+1}. {title}" for i, title in enumerate(numeric_titles)]

    # Edit the "Fetching posts" message to show the final result
    await fetch_message.edit(
        content=(
            f"**Threads in <#{forum_channel_id}> you are currently following (excluding threads with the \"Expired\" and \"Dead\" tags, closed threads, and older than 48 hours):**\n"
            + "\n".join(thread_list)
        )
    )

@bot.command(name="retire_user")
@commands.has_any_role(*MODERATOR_ROLE)  # Restrict command to users with the specified roles
async def retire_user(ctx, user_id: str):
    """
    Moves a user's JSON file from the userdata folder to the delete_userdata folder,
    and moves the corresponding file from the testers folder to the deleted_testers folder.
    If a file already exists in the destination folders, it will be replaced.
    Only users with specific roles can use this command.
    """
    # Ensure the user_id is a valid numeric string
    user_id = re.sub(r'\D', '', user_id)
    if not user_id:
        await ctx.send("Invalid user ID. Please provide a valid numeric user ID.")
        return

    # Define the source and destination paths for userdata
    source_userdata_path = DATA_FOLDER / f"{user_id}.json"
    destination_userdata_path = DELETE_USERDATA_FOLDER / f"{user_id}.json"

    # Define the source and destination paths for testers
    source_testers_path = TESTERS_FOLDER / f"{user_id}.json"
    destination_testers_path = DELETED_TESTERS_FOLDER / f"{user_id}.json"

    # Check if the file exists in the userdata folder
    if not source_userdata_path.exists():
        await ctx.send(f"No data found for User ID: {user_id} in the userdata folder.")

    # If the file already exists in the delete_userdata folder, remove it
    if destination_userdata_path.exists():
        try:
            destination_userdata_path.unlink()  # Delete the existing file
        except Exception as e:
            await ctx.send(f"Failed to remove existing file in deleted_userdata folder: {e}")


    # Move the userdata file
    try:
        source_userdata_path.rename(destination_userdata_path)
        await ctx.send(f"User data for <@{user_id}> has been retired and moved to the deleted_userdata folder.")
    except Exception as e:
        await ctx.send(f"An error occurred while moving the userdata file: {e}")


    # Check if the file exists in the testers folder
    if source_testers_path.exists():
        # If the file already exists in the deleted_testers folder, remove it
        if destination_testers_path.exists():
            try:
                destination_testers_path.unlink()  # Delete the existing file
            except Exception as e:
                await ctx.send(f"Failed to remove existing file in deleted_testers folder: {e}")

        # Move the testers file
        try:
            source_testers_path.rename(destination_testers_path)
            await ctx.send(f"Tester data for <@{user_id}> has been retired and moved to the deleted_testers folder.")
        except Exception as e:
            await ctx.send(f"An error occurred while moving the testers file: {e}")
    else:
        await ctx.send(f"No tester data found for User ID: {user_id} in the testers folder.")

@bot.event
async def on_ready():
    global latest_sent_message
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

    load_all_user_data()  # Load saved data at startup
    print("User data loaded successfully.")

    await bot.wait_until_ready()

    channel = await get_channel(DESTINATION_CHANNEL_ID)
    if channel and latest_sent_message is None:
        latest_sent_message = await channel.send("Initializing...", allowed_mentions=allowed_mentions)

    if not send_message_list_task.is_running():
        send_message_list_task.start()

@bot.event
async def on_message(message):
    if message.author.id == TARGET_USER_ID and message.channel.id == SOURCE_CHANNEL_ID:
        lines = message.content.split("\n")
        if len(lines) < 4:
            return

        match = re.search(r'<(\d+(?:-\d+)?)>', lines[0].strip())
        user_id = match.group(1) if match else None
        user_id_display = user_id.split('-')[0] if user_id else None
        timestamp_formatted = f"<t:{int(message.created_at.timestamp())}:R>"
        second_line_numbers = len(re.findall(r'\d+', lines[1].strip()))
        third_line_numbers = len(re.findall(r'\d+', lines[2].strip()))
        fourth_line_numbers = re.findall(r'\d+', lines[3].strip())
        pph = (int(fourth_line_numbers[1]) / int(fourth_line_numbers[0]) * 60 if len(fourth_line_numbers) >= 2 and int(fourth_line_numbers[0]) != 0 else 0)
        time_user = int(fourth_line_numbers[0])
        # Save the fourth line numbers for the user
        save_fourth_line_numbers(user_id, fourth_line_numbers)
        tot_instances = third_line_numbers + second_line_numbers

        if user_id in [data["content"] for data in user_messages.values()]:
            for key, data in user_messages.items():
                if data["content"] == user_id:
                    user_messages[key] = {"content": user_id, "timestamp": timestamp_formatted, "second_line_numbers": second_line_numbers, "pph": pph, "time_user": time_user, "tot_instances": tot_instances}
                    break
        else:
            user_messages[message.id] = {"content": user_id, "timestamp": timestamp_formatted, "second_line_numbers": second_line_numbers, "pph": pph, "time_user": time_user, "tot_instances": tot_instances}

        # Send PPH warning only if second_line_numbers is 40 or more
        if int(fourth_line_numbers[0]) >= 40 and pph < PPH_WARNING_LIMIT:
            await send_pph_warning(user_id, pph)

    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:  # Skip reactions from bots
        return

    # Check if the reaction is the specific emoji
    if str(reaction.emoji) != SPECIFIC_EMOJI:
        return

    # Fetch the member object to check roles
    try:
        member = await reaction.message.guild.fetch_member(user.id)
    except discord.NotFound:
        return
    except discord.Forbidden:
        return
    except discord.HTTPException:
        return

    # Check if the user has any of the specified roles
    if not any(role.id in MODERATOR_ROLE for role in member.roles):
        return

    # Initialize message reactions tracking if not already done
    if reaction.message.id not in message_reactions:
        message_reactions[reaction.message.id] = set()

    # Add the user to the tracked reactions for this message
    message_reactions[reaction.message.id].add(user.id)

    # Load existing reactions for the message author
    message_author_id = str(reaction.message.author.id)
    file_path = TESTERS_FOLDER / f"{message_author_id}.json"
    if file_path.exists():
        with open(file_path, "r") as f:
            data = json.load(f)
    else:
        data = []

    # If the reaction doesn't exist, add it to the JSON file
    reaction_number = len(data) + 1  # Increment reaction number
    timestamp = int(time.time())  # Current Unix timestamp
    new_entry = [reaction_number, timestamp, str(user.id)]  # New row

    data.append(new_entry)

    # Save the updated data back to the JSON file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

    # Add a success reaction to the message
    try:
        await reaction.message.add_reaction(SUCCESS_EMOJI)
    except discord.HTTPException as e:
        print(f"Failed to add success reaction: {e}")

@bot.event
async def on_reaction_remove(reaction, user):
    # Check if the reaction is the specific emoji
    if str(reaction.emoji) != SPECIFIC_EMOJI:
        return

    # Fetch the member object to check roles
    try:
        member = await reaction.message.guild.fetch_member(user.id)
    except discord.NotFound:
        return
    except discord.Forbidden:
        return

    # Check if the user has any of the specified roles
    if not any(role.id in MODERATOR_ROLE for role in member.roles):
        return

    # Load existing reactions for the message author
    message_author_id = str(reaction.message.author.id)
    file_path = TESTERS_FOLDER / f"{message_author_id}.json"
    if not file_path.exists():
        return

    with open(file_path, "r") as f:
        data = json.load(f)

    # Find the last entry for the user who removed the reaction
    entry_to_remove = None
    for entry in reversed(data):  # Iterate in reverse to find the most recent entry
        if entry[2] == str(user.id):  # Check if the reactor ID matches
            entry_to_remove = entry
            break

    if entry_to_remove:
        data.remove(entry_to_remove)
    else:
        return

    # Save the updated data back to the JSON file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


    # Remove the SUCCESS_EMOJI from the message
    try:
        await reaction.message.remove_reaction(SUCCESS_EMOJI, bot.user)
    except discord.HTTPException as e:
        print(f"Failed to remove success reaction: {e}")

# Error handling for missing roles
@retire_user.error
async def retire_user_error(ctx, error):
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send("You do not have permission to use this command.")
    else:
        await ctx.send(f"An error occurred: {error}")

@tasks.loop(seconds=EDIT_LOOP_TIMER)
async def send_message_list_task():
    await send_message_list()

bot.run(YOUR_BOT_TOKEN)