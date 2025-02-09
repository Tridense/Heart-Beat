# Heart-Beat

The bot reads the heart beat messages and converts the IDs and additional information into a list of active contributors. It also sets inactive users as offline.

https://i.imgur.com/EyPgvl5.png


Make sure to format the heart beat webhook message like this:



example:

<1234567891234569>

Online: Main, 1, 2, 3, 4.

Offline: none.

Time: 120m Packs: 111




example:

1234567891234569 

Online: Main, 1, 2, 3, 4.

Offline: none.

Time: 120m Packs: 111




example:

1234567891234569 Username-example

Online: Main, 1, 2, 3, 4.

Offline: none.

Time: 120m Packs: 111




The discord bot should have the following perms:
- View channels
- Send messages
- View channel history

Make sure to: pip install discord

Heart beat status for Arturo's PTCGP bot (His version 6.1.9beta)
