import discord
from discord.ext import commands, tasks
import time
import re
import os
from dotenv import load_dotenv

# Set up bot intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

################################################################################
# Configuration Variables
################################################################################
TARGET_USER_ID = 1328364790904782991  # Replace with the user's ID
SOURCE_CHANNEL_ID = 1336258658656452608  # Replace with the channel to read messages from
DESTINATION_CHANNEL_ID = 1335907684679028788  # Replace with the channel to send messages to
WARNING_CHANNEL_ID = 1335644343029076029  # Replace with the warning channel's ID
YOUR_BOT_TOKEN = "DISCORD_TOKEN"  # Replace with your bot's token

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
        line = f"<@{data['content']}> {data['timestamp']} {data['second_line_numbers']} in. {round(data["pph"])} pph"
        message_list.append(f"**{line}**" if data["second_line_numbers"] <= 2 else line)

    message_content = (f"## Latest heart beats:\n"
                       f"**{len(sorted_messages)} rollers | {total_instances} instances | {round(total_pph)} pph** \n" + "\n".join(message_list))

    try:
        if latest_sent_message:
            await latest_sent_message.edit(content=message_content)
        else:
            latest_sent_message = await channel.send(message_content, allowed_mentions=allowed_mentions)
    except discord.errors.HTTPException as e:
        print(f"Error sending/editing message: {e}")

################################################################################
# Bot Events
################################################################################
@bot.event
async def on_ready():
    global latest_sent_message
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    await bot.wait_until_ready()

    # Ensure a message is sent on startup
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
