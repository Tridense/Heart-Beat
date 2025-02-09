import discord
from discord.ext import commands, tasks
import re
import time

intents = discord.Intents.default()
intents.message_content = True  # Enable access to message content
bot = commands.Bot(command_prefix="!", intents=intents)


###############################################################################################
# Variables
###############################################################################################


TARGET_USER_ID = 1328364790904782991  # Replace with the user's ID
SOURCE_CHANNEL_ID = 1336258658656452608  # Replace with the channel to read messages from
DESTINATION_CHANNEL_ID = 1335907684679028788  # Replace with the channel to send messages to
WARNING_CHANNEL_ID = 1336258658656452608  # Replace with the warning channel's ID
YOUR_BOT_TOKEN = "DISCORD_TOKEN"  # Replace with your bot's token

edit_loop_timer = 60  # In seconds, how often the status message should update itself.
offline_timer = 60 * 33  # In seconds, default 33 min given that each heart beats comes every 30 min.
instance_warning_limit = 3  # What is the minimum amount of instances every user should be running.
warning_cooldown = 2 * 60 * 60  # 2 hours in seconds


###############################################################################################
# Main code
###############################################################################################


user_messages = {}
allowed_mentions = discord.AllowedMentions(users=True)  # Allow user mentions
latest_sent_message = None
last_warning_timestamps = {}  # Track the last warning timestamp for each user


async def send_new_message(channel_id, user_id, timestamp):
    channel = bot.get_channel(channel_id)
    # Additional actions here if needed


async def send_warning(user_id, second_line_numbers):
    current_time = int(time.time())
    last_warning_time = last_warning_timestamps.get(user_id, 0)

    # Check if the cooldown period has passed
    if current_time - last_warning_time >= warning_cooldown:
        warning_channel = bot.get_channel(WARNING_CHANNEL_ID)
        if warning_channel:
            warning_message = f"<@{user_id}> Alert: You have {second_line_numbers} instance(s) running (Less than {instance_warning_limit}). Please check your setup if instances have failed. (Ignore this message if you're checking god packs)"
            await warning_channel.send(warning_message, allowed_mentions=allowed_mentions)
            print(f"Warning sent to <@{user_id}> in warning channel.")
            # Update the last warning timestamp
            last_warning_timestamps[user_id] = current_time


async def send_message_list(channel_id):
    global latest_sent_message
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    message_list = []
    non_offline_count = 0
    total_instances = 0  # Variable to store the total amount of second_line_numbers
    total_pph = 0  # Variable to store the sum of pph for all active users

    if user_messages:
        current_time = int(time.time())

        # Filter out entries that exceed the offline timer
        active_messages = {
            msg_id: data for msg_id, data in user_messages.items()
            if current_time - int(data["timestamp"].split(":")[1]) <= offline_timer
        }

        # Sort the remaining messages by timestamp
        sorted_messages = sorted(active_messages.values(), key=lambda x: x["timestamp"], reverse=True)

        for data in sorted_messages:
            non_offline_count += 1
            total_instances += data["second_line_numbers"]  # Add to the total instances
            total_pph += data.get("pph", 0)  # Add to the total pph

            # Format the line in bold if second_line_numbers is 2 or fewer
            line = f"• <@{data['content']}> {data['timestamp']} {data['second_line_numbers']} inst."
            if data["second_line_numbers"] <= 2:
                line = f"**{line}**"

            message_list.append(line)

        # Join the messages and update the latest sent message
        message_content = (
            f"## __Latest heart beats:__ {non_offline_count} active rollers | {total_instances} total instances\n"
            f"**Total packs per hour:** {total_pph:.2f}\n"  # Add total pph on the second line
            + "\n".join(message_list)
        )

        # Ensure the message content does not exceed 2000 characters
        if len(message_content) > 2000:
            # Truncate the message and add a note
            message_content = (
                f"## __Latest heart beats:__ {non_offline_count} active rollers | {total_instances} total instances\n"
                f"**Total packs per hour:** {total_pph:.2f}\n"  # Add total pph on the second line
                + "\n".join(message_list[:50])  # Adjust the slice as needed
                + "\n\n**Note:** Message truncated due to length."
            )

        try:
            if latest_sent_message:
                await latest_sent_message.edit(content=message_content)
                print(time.ctime())
                print(message_content)
            else:
                latest_sent_message = await channel.send(message_content, allowed_mentions=allowed_mentions)
                print(time.ctime())
                print(message_content)
        except discord.errors.HTTPException as e:
            print(f"Failed to send/edit message: {e}")
    else:
        # If no valid messages, update the message to show no valid messages
        try:
            if latest_sent_message:
                await latest_sent_message.edit(content="No valid messages stored yet.")
                print(time.ctime())
                print("No valid messages stored yet.")
            else:
                latest_sent_message = await channel.send("No valid messages stored yet.")
                print(time.ctime())
                print("No valid messages stored yet.")
        except discord.errors.HTTPException as e:
            print(f"Failed to send/edit message: {e}")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    if not send_message_list_task.is_running():
        send_message_list_task.start()


@bot.event
async def on_message(message):
    if message.author.id == TARGET_USER_ID and message.channel.id == SOURCE_CHANNEL_ID:
        if "\n" in message.content:  # Check if the message has multiple lines
            lines = message.content.split("\n")
            first_line = lines[0].strip()  # Get the first line

            # Extract the number from the first line
            numbers = re.findall(r'\d+', first_line)
            if numbers:
                user_id = numbers[0]  # Take the first number found in the first line
                unix_timestamp = int(message.created_at.timestamp())
                timestamp_formatted = f"<t:{unix_timestamp}:R>"

                # Count the number of separate numbers in the second line
                second_line = lines[1].strip() if len(lines) > 1 else ""
                second_line_numbers = len(re.findall(r'\d+', second_line))

                # Extract numbers from the 4th line and calculate ppm and pph
                if len(lines) >= 4:  # Ensure there is a 4th line
                    fourth_line = lines[3].strip()
                    fourth_line_numbers = re.findall(r'\d+', fourth_line)
                    if len(fourth_line_numbers) >= 2:  # Ensure there are at least 2 numbers
                        num1 = int(fourth_line_numbers[0])
                        num2 = int(fourth_line_numbers[1])
                        if num1 != 0:  # Avoid division by zero
                            ppm = num2 / num1  # Packs per minute
                            pph = ppm * 60  # Packs per hour
                        else:
                            pph = 0  # Default value if num1 is zero
                    else:
                        pph = 0  # Default value if there are not enough numbers
                else:
                    pph = 0  # Default value if there is no 4th line

                # Store or update message data
                for msg_id, data in user_messages.items():
                    if data["content"] == user_id:
                        data.update({
                            "timestamp": timestamp_formatted,
                            "second_line_numbers": second_line_numbers,
                            "pph": pph  # Store pph in the data
                        })
                        break
                else:
                    user_messages[message.id] = {
                        "content": user_id,
                        "timestamp": timestamp_formatted,
                        "second_line_numbers": second_line_numbers,
                        "pph": pph  # Store pph in the data
                    }

                # Send a warning if second_line_numbers is below the warning limit
                if second_line_numbers < instance_warning_limit:
                    await send_warning(user_id, second_line_numbers)

                await send_new_message(DESTINATION_CHANNEL_ID, user_id, timestamp_formatted)

    await bot.process_commands(message)


@tasks.loop(seconds=edit_loop_timer)
async def send_message_list_task():
    await send_message_list(DESTINATION_CHANNEL_ID)


bot.run(YOUR_BOT_TOKEN)