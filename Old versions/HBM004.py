import discord
from discord.ext import commands, tasks
import time
import re
import os
import json
from collections import defaultdict
import numpy as np
from pathlib import Path

# Set up bot intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

################################################################################
# Configuration Variables
################################################################################
TARGET_USER_ID = 1234567890123456789    # Replace with the user's ID
SOURCE_CHANNEL_ID = 1234567890123456789    # Replace with the channel to read messages from
DESTINATION_CHANNEL_ID = 1234567890123456789    # Replace with the channel to send messages to
WARNING_CHANNEL_ID = 1234567890123456789    # Replace with the warning channel's ID
YOUR_BOT_TOKEN = "bot_token"

# Timing and Limits
EDIT_LOOP_TIMER = 30  # Message update frequency
OFFLINE_TIMER = 60 * 33  # 33 minutes offline threshold
INSTANCE_WARNING_LIMIT = 3  # Min instances per user before warning
WARNING_COOLDOWN = 2 * 60 * 60  # 2-hour cooldown for warnings

################################################################################
# Data Storage
################################################################################
user_messages = {}
allowed_mentions = discord.AllowedMentions(users=True)
latest_sent_message = None
last_warning_timestamps = {}

################################################################################
# Helper Functions
################################################################################
DATA_FOLDER = Path("userdata")
DATA_FOLDER.mkdir(parents=True, exist_ok=True)  # Creates the folder if missing

async def get_channel(channel_id):
    return discord.utils.get(bot.get_all_channels(), id=channel_id)

async def send_warning(user_id, second_line_numbers):
    current_time = int(time.time())
    last_warning_time = last_warning_timestamps.get(user_id, 0)

    if current_time - last_warning_time >= WARNING_COOLDOWN:
        warning_channel = await get_channel(WARNING_CHANNEL_ID)
        if warning_channel:
            warning_message = (f"<@{user_id}> Alert: You have {second_line_numbers} instance(s) running (Less than {INSTANCE_WARNING_LIMIT}). "
                               "Please check your setup.")
            await warning_channel.send(warning_message, allowed_mentions=allowed_mentions)
            last_warning_timestamps[user_id] = current_time
            print(f"Warning sent to <@{user_id}>")

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
        line = f"<@{data['content']}> {data['timestamp']} {data['second_line_numbers']} in. {round(data['pph'])} pph"
        message_list.append(f"**{line}**" if data["second_line_numbers"] <= INSTANCE_WARNING_LIMIT else line)

    message_content = (f"## Latest heart beats:\n"
                       f"**{len(sorted_messages)} rollers | {total_instances} instances | {round(total_pph)} pph** \n" + "\n".join(message_list))

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

# Dictionary to store user data as a matrix
user_fourth_line_data = defaultdict(list)

# Dictionary to store user data as numpy arrays
user_fourth_line_data = {}


def save_fourth_line_numbers(user_id, fourth_line_numbers):
    fln_int = [int(x) for x in fourth_line_numbers]  # Convert to integers
    fln_matrix = np.array(fln_int)  # Convert to NumPy array

    if user_id not in user_fourth_line_data:
        user_fourth_line_data[user_id] = load_data_from_file(user_id)  # Load previous data

    if user_fourth_line_data[user_id].size == 0:
        user_fourth_line_data[user_id] = np.zeros((1, len(fln_int) + 2))
        user_fourth_line_data[user_id][0, :-2] = fln_int
    else:
        previous_row = user_fourth_line_data[user_id][-1]
        if np.sum(fln_matrix) != 0:
            time_total = (fln_matrix[0] - previous_row[0]) + previous_row[2]
            pack_total = (fln_matrix[1] - previous_row[1]) + previous_row[3]
        else:
            last_col2, last_col3 = find_last_nonzero(user_id)
            time_total = last_col2 if last_col2 is not None else previous_row[0]
            pack_total = last_col3 if last_col3 is not None else previous_row[1]

        new_matrix = np.concatenate((fln_matrix, [time_total, pack_total]), axis=0)
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
async def check(ctx, user_id: str):
    # Strip any non-digit characters from user_id
    user_id = re.sub(r'\D', '', user_id)

    if user_id in user_fourth_line_data:
        data = user_fourth_line_data[user_id]
        last_entry = data[-1]  # Get the last row
        last_col_1 = last_entry[0] if len(last_entry) > 0 else None
        last_col_2 = last_entry[1] if len(last_entry) > 1 else None
        last_col_3 = last_entry[2] if len(last_entry) > 2 else None
        last_col_4 = last_entry[3] if len(last_entry) > 3 else None
        max_value_1 = get_max_column_1(user_id)
        max_value_2 = get_max_column_2(user_id)

        response = (f"**User ID:** {user_id}\n"
                    f"**Current session:**\nTime: {round(last_col_1)} Packs: {round(last_col_2)}\n"                    
                    f"**Total:**\nTime: {round(last_col_3)} Packs: {round(last_col_4)}\n"
                    f"**Record session:**\nTime: {round(max_value_1)} Packs: {round(max_value_2)}\n")
    else:
        response = f"No data found for User ID: {user_id}"

    await ctx.send(response)

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

        user_id = re.findall(r'\d+', lines[0].strip())[0]
        timestamp_formatted = f"<t:{int(message.created_at.timestamp())}:R>"
        second_line_numbers = len(re.findall(r'\d+', lines[1].strip()))
        fourth_line_numbers = re.findall(r'\d+', lines[3].strip())

        pph = (int(fourth_line_numbers[1]) / int(fourth_line_numbers[0]) * 60) if len(fourth_line_numbers) >= 2 and int(fourth_line_numbers[0]) != 0 else 0

        # Save the fourth line numbers for the user
        save_fourth_line_numbers(user_id, fourth_line_numbers)

        if user_id in [data["content"] for data in user_messages.values()]:
            for key, data in user_messages.items():
                if data["content"] == user_id:
                    user_messages[key] = {"content": user_id, "timestamp": timestamp_formatted, "second_line_numbers": second_line_numbers, "pph": pph}
                    break
        else:
            user_messages[message.id] = {"content": user_id, "timestamp": timestamp_formatted, "second_line_numbers": second_line_numbers, "pph": pph}

        if second_line_numbers < INSTANCE_WARNING_LIMIT:
            await send_warning(user_id, second_line_numbers)

    await bot.process_commands(message)


@tasks.loop(seconds=EDIT_LOOP_TIMER)
async def send_message_list_task():
    await send_message_list()

bot.run(YOUR_BOT_TOKEN)
