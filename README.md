# Heart-Beat

The bot reads the heart beat messages and converts the IDs and additional information into a list of active contributors. It also sets inactive users as offline.


Heart beat status for Arturo's PTCGP bot (His version 6.2.6beta)

![image](https://github.com/user-attachments/assets/3b74c83a-f3c4-41a8-8cb4-6d4c2c5fa84a)

![image](https://github.com/user-attachments/assets/42bcc247-f1eb-46fe-af94-22ee73cca606)


Guide for HBM004.py:

1. Make a bot on discord: Go to discord developer portal website
    1. Click New Application
    2. Go to OAuth2 page, check off the Bot square
    3. In the new checkboxes that appear, you want to check off "View Channels", "Send Messages", and "Read Message History".
    4. Click copy, and then paste the link in to your browser. Invite the bot to your server.
    5. Go to the Bot tab on the left, click reset token and save the string of symbols in a safe place like a .txt file.
    6. Scroll down and enable "Message Content Intent".

3. Open your python interpreter of choice:I used pycharm, but VS code should also work.
    1. Open the HBM004.py file
    2. Do the following commands in the terminal:
       1. pip install python
       2. pip install audioop-lts
       3. pip install numpy
    3. Copy the user ID of the heartbeat webhook. Paste into line 19. (Right click o the username and select "Copy User ID". Make sure you have developer mode turned on in discord).
    4. Copy the channel ID of where the webhook is sending messages, and paste it into line 20.
    5. Copy the channel ID of where you want to post the status message, and paste it into line 21.
    6. Copy the channel ID of where you want to post the warning messages that ping users who have less than 3 instances running, and paste it into line 22.
    7. Copy the discord bot token into line 23.

4. Run the script.

Tips:
1. Make sure the heart beat user id field in the AHK window (heartBeatName in settings.ini) only contains the discord user ID of the person.
2. Make sure to have a seperate webhook for the god packs and the heart beat for it to run properly.
3. If you want to turn off warning messages, set line 28 to 0.
4. This script will hit the discord character limit at around 37 users. If you want to remove/ edit any part of the lines that are sent you can find it at line 78.





