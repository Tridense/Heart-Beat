import discord
from discord.ext import commands, tasks
import re
import time

intents = discord.Intents.default()
intents.message_content = True  # Enable access to message content
bot = commands.Bot(command_prefix="!", intents=intents)

TARGET_USER_ID = WEBHOOK_ID  # Replace with the webhook's user-ID. (This should be a number, not a link)
SOURCE_CHANNEL_ID = SOURCE_ID  # Replace with the channel to read messages from. (This should be a number, not a link)
DESTINATION_CHANNEL_ID = DESTINATION_ID  # Replace with the channel to send messages to. (This should be a number, not a link)
YOUR_BOT_TOKEN = "DISCORD_TOKEN"  # Replace with your discord bot's token

user_messages = {}
allowed_mentions = discord.AllowedMentions(users=False)
latest_sent_message = None
edit_loop_timer = 1 # One minute


async def send_new_message(channel_id, user_id, timestamp):
    channel = bot.get_channel(channel_id)
    # Additional actions here if needed

async def send_message_list(channel_id):
    global latest_sent_message
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    message_list = []
    total_lines, non_offline_count = 0, 0

    if user_messages:
        sorted_messages = sorted(user_messages.values(), key=lambda x: x["timestamp"], reverse=True)
        current_time = int(time.time())

        for data in sorted_messages:
            total_lines += 1
            timestamp = data["timestamp"]
            timestamp_unix = int(timestamp.split(":")[1])

            # Determine whether the message is offline or not
            is_offline = current_time - timestamp_unix > 1890 # 33 minutes offline timer, allows for some delay from webhook and update loop timer.
            status = "OFFLINE" if is_offline else ""
            message_list.append(
                f"• {status} <@{data['content']}> {timestamp} **({data['second_line_numbers']} instances)**"
            )
            if not is_offline:
                non_offline_count += 1

        # Join the messages and update the latest sent message
        message_content = f"## __Latest heart beats:__ {non_offline_count} active roller(s)\n" + "\n".join(message_list)

        if latest_sent_message:
            await latest_sent_message.edit(content=message_content)
            print(time.ctime())
            print(message_content)
        else:
            latest_sent_message = await channel.send(message_content, allowed_mentions=allowed_mentions)
            print(time.ctime())
            print(message_content)
    else:
        # If no valid messages, update the message to show no valid messages
        if latest_sent_message:
            await latest_sent_message.edit(content="No valid messages stored yet.")
            print(time.ctime())
            print("No valid messages stored yet.")
        else:
            latest_sent_message = await channel.send("No valid messages stored yet.")
            print(time.ctime())
            print("No valid messages stored yet.")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    if not send_message_list_task.is_running():
        send_message_list_task.start()


@bot.event
async def on_message(message):
    if message.author.id == TARGET_USER_ID and message.channel.id == SOURCE_CHANNEL_ID:
        if message.content.startswith("<") and "\n" in message.content:
            lines = message.content.split("\n")
            first_line = lines[0].strip()
            second_line = lines[1].strip() if len(lines) > 1 else ""  # Get the second line

            if "@" in first_line:
                return  # Ignore the message if it contains '@' after '<'

            if ">" in first_line:
                user_id = first_line.split("<")[1].split(">")[0].strip()
                unix_timestamp = int(message.created_at.timestamp())
                timestamp_formatted = f"<t:{unix_timestamp}:R>"

                # Count the number of separate numbers in the second line
                second_line_numbers = len(re.findall(r'\d+', second_line))

                # Extract digits from the first line (Online line) and format with commas
                online_line_match = re.search(r'.*Online.*', message.content, re.MULTILINE)
                digit_list = f"{int(''.join(re.findall(r'\d+', online_line_match.group()))):,}" if online_line_match else "0"

                # Store or update message data with digits and the count of numbers in the second line
                for msg_id, data in user_messages.items():
                    if data["content"] == user_id:
                        data.update({"timestamp": timestamp_formatted, "digits": digit_list, "second_line_numbers": second_line_numbers})
                        break
                else:
                    user_messages[message.id] = {
                        "content": user_id,
                        "digits": digit_list,
                        "timestamp": timestamp_formatted,
                        "second_line_numbers": second_line_numbers
                    }

                await send_new_message(DESTINATION_CHANNEL_ID, user_id, timestamp_formatted)

    await bot.process_commands(message)


@tasks.loop(minutes=edit_loop_timer)
async def send_message_list_task():
    await send_message_list(DESTINATION_CHANNEL_ID)


bot.run(YOUR_BOT_TOKEN)
