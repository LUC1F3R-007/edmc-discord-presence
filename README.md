# edmc-discord-presence
EDMC Discord Presence, updated for EDMC 6.x.x (version 3.3.0)
=================================================================

Shows what you're doing in Elite Dangerous (star system, docked/supercruise/
landed, etc.) on your Discord profile, through Elite Dangerous Market Connector (EDMC).

This is a community patch of the original plugin by elite-kode:
https://github.com/elite-kode/edmc-discord-presence (Apache License 2.0, see
DiscordPresence\LICENSE). The original hasn't been updated since 2021.
Most of the original code is no


WHAT'S IN THIS ZIP
------------------
  README.txt  - this file  
  load.py     - the plugin itself  
  L10n        - translations (German, French, Portuguese, Russian)  
  LICENSE     - original license  


REQUIREMENTS
------------
  - Elite Dangerous Market Connector 6.0 or newer (tested against the 6.1.x code)
  - The Discord Desktop app, running on the same PC.
	*Discord in a web browser can't show Rich Presence.


INSTALL
-------
 1. Close Elite Dangerous Market Connector

 2. Open the EDMC plugins folder, Either:
      - in EDMC: File > Settings > Plugins tab > click "Open", or
      - paste this into the File Explorer address bar and press Enter:
          %LOCALAPPDATA%\EDMarketConnector\plugins

 3. *REMOVE THE OLD PLUGIN* Delete the existing "DiscordPresence" folder,
    or rename it to "DiscordPresence.disabled". If the old one is left in
    place, the two will clash.

 4. Copy the "DiscordPresence" folder from this zip into the plugins folder.
    The result must look like this:
        ...\plugins\DiscordPresence\load.py                    <- correct
    NOT like this:
        ...\plugins\DiscordPresence\DiscordPresence\load.py    <- wrong

 5. Start the Discord desktop app, then start EDMC (and the game).

 6. In Discord: User Settings > Activity Privacy > turn ON
    "Share your detected activities with others".


CHECK THAT IT WORKS
-------------------
  - In Elite Dangerous Market Connector, File > Settings > Plugins: "DiscordPresence" should be listed
    as enabled.
  - The "DiscordPresence" settings tab should say "Version 3.3.0".
    If it shows an older number, the old plugin is still installed (see step 3).
  - Your Discord profile should show "Connecting CMDR Interface" at the main
    menu, then your system and status once you're in game.

To turn the status off without uninstalling: File > Settings > DiscordPresence
tab > tick "Disable Presence".


TROUBLESHOOTING
---------------
  Nothing shows on Discord
    - Make sure the Discord desktop app is running. The plugin checks for it
      every 15 seconds, so you can start Discord after EDMC.
    - Check the Activity Privacy setting (install step 6).
    - Discord and EDMC must both run as the same Windows user. If one of them
      is "Run as administrator" and the other isn't, they may not be able
      to connect. Run both normally.

  Plugin not listed / errors in EDMC
    - Check the folder layout (check install step 4).
    - Make sure the old plugin is gone (check install step 3).

  Still stuck? Send the Elite Dangerous Market Connector log file:
      %TEMP%\EDMarketConnector\EDMarketConnector-debug.log
    and search it for "DiscordPresence".
