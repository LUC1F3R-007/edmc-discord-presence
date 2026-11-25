\# edmc-discord-presence

EDMC Discord Presence, updated for EDMC 6.x.x (version 3.3.0)

=================================================================



Shows what you're doing in Elite Dangerous (star system, docked/supercruise/

landed, etc.) on your Discord profile, through Elite Dangerous Market Connector (EDMC).



This is a community patch of the original plugin by elite-kode:

https://github.com/elite-kode/edmc-discord-presence (Apache License 2.0, see

DiscordPresence\\LICENSE). The original hasn't been updated since 2021.





WHAT'S IN THIS ZIP

\------------------

&#x20; README.txt  - this file

&#x20; load.py     - the plugin itself

&#x20; L10n        - translations (German, French, Portuguese, Russian)

&#x20; LICENSE     - original license





REQUIREMENTS

\------------

&#x20; - Elite Dangerous Market Connector 6.0 or newer (tested against the 6.1.x code)

&#x20; - The Discord Desktop app, running on the same PC.

&#x09;\*Discord in a web browser can't show Rich Presence.





INSTALL

\-------

&#x20;1. Close Elite Dangerous Market Connector



&#x20;2. Open the EDMC plugins folder, Either:

&#x20;     - in EDMC: File > Settings > Plugins tab > click "Open", or

&#x20;     - paste this into the File Explorer address bar and press Enter:

&#x20;         %LOCALAPPDATA%\\EDMarketConnector\\plugins



&#x20;3. \*REMOVE THE OLD PLUGIN\* Delete the existing "DiscordPresence" folder,

&#x20;   or rename it to "DiscordPresence.disabled". If the old one is left in

&#x20;   place, the two will clash.



&#x20;4. Copy the "DiscordPresence" folder from this zip into the plugins folder.

&#x20;   The result must look like this:

&#x20;       ...\\plugins\\DiscordPresence\\load.py                    <- correct

&#x20;   NOT like this:

&#x20;       ...\\plugins\\DiscordPresence\\DiscordPresence\\load.py    <- wrong



&#x20;5. Start the Discord desktop app, then start EDMC (and the game).



&#x20;6. In Discord: User Settings > Activity Privacy > turn ON

&#x20;   "Share your detected activities with others".





CHECK THAT IT WORKS

\-------------------

&#x20; - In Elite Dangerous Market Connector, File > Settings > Plugins: "DiscordPresence" should be listed

&#x20;   as enabled.

&#x20; - The "DiscordPresence" settings tab should say "Version 3.3.0".

&#x20;   If it shows an older number, the old plugin is still installed (see step 3).

&#x20; - Your Discord profile should show "Connecting CMDR Interface" at the main

&#x20;   menu, then your system and status once you're in game.



To turn the status off without uninstalling: File > Settings > DiscordPresence

tab > tick "Disable Presence".





TROUBLESHOOTING

\---------------

&#x20; Nothing shows on Discord

&#x20;   - Make sure the Discord desktop app is running. The plugin checks for it

&#x20;     every 15 seconds, so you can start Discord after EDMC.

&#x20;   - Check the Activity Privacy setting (install step 6).

&#x20;   - Discord and EDMC must both run as the same Windows user. If one of them

&#x20;     is "Run as administrator" and the other isn't, they may not be able

&#x20;     to connect. Run both normally.



&#x20; Plugin not listed / errors in EDMC

&#x20;   - Check the folder layout (check install step 4).

&#x20;   - Make sure the old plugin is gone (check install step 3).



&#x20; Still stuck? Send the Elite Dangerous Market Connector log file:

&#x20;     %TEMP%\\EDMarketConnector\\EDMarketConnector-debug.log

&#x20;   and search it for "DiscordPresence".

