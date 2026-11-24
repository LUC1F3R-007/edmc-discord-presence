# edmc-discord-presence
EDMC Discord Presence, updated for EDMC 6.x.x (version 3.3.0)
=================================================================

Shows what you're doing in Elite Dangerous (star system, docked/supercruise/
landed, etc.) on your Discord profile, through EDMarketConnector (EDMC).

This is a community patch of the original plugin by elite-kode:
https://github.com/elite-kode/edmc-discord-presence (Apache License 2.0, see
DiscordPresence\LICENSE). The original hasn't been updated since 2021.


WHAT'S IN THIS ZIP
------------------
    README.txt                  - this file
    SECURITY.txt                - security changes made in this patch
    DiscordPresence\load.py     - the plugin itself
    DiscordPresence\L10n\       - translations (German, French, Portuguese, Russian)
    DiscordPresence\LICENSE     - original license


REQUIREMENTS
------------
  - EDMarketConnector 6.0 or newer (tested against the 6.1.x code)
  - The Discord DESKTOP app, running on the same PC.
    Discord in a web browser can't show Rich Presence.


INSTALL
-------
 1. Close EDMC.

 2. Open the EDMC plugins folder. Either:
      - in EDMC: File > Settings > Plugins tab > click "Open", or
      - paste this into the File Explorer address bar and press Enter:
          %LOCALAPPDATA%\EDMarketConnector\plugins

 3. REMOVE THE OLD PLUGIN. Delete the existing "DiscordPresence" folder,
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
  - In EDMC, File > Settings > Plugins: "DiscordPresence" should be listed
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
    - Check the folder layout (install step 4).
    - Make sure the old plugin is gone (install step 3).

  Still stuck? Send the EDMC log file:
      %TEMP%\EDMarketConnector\EDMarketConnector-debug.log
    and search it for "DiscordPresence".


WHY THE ORIGINAL PLUGIN STOPPED WORKING
---------------------------------------
EDMC 6.0 (2025) broke the original 2021 plugin in three ways:
 1. EDMC removed the old translation object the plugin used
    (l10n.Translations), so the plugin crashed the first time it showed text.
 2. EDMC became a 64-bit app. The plugin relied on a 32-bit Discord file
    (discord_game_sdk.dll) that can't load in it, so it never connected and
    kept retrying silently.
 3. Because of 1 and 2, the plugin's state was never set up, so every game
    event logged "AttributeError: ... has no attribute 'presence_state'"
    (issue #33 on the original plugin's GitHub page).

WHAT THIS PATCH CHANGES
 - Uses EDMC 6.x.x current translation method.
 - Talks to the Discord desktop app directly in plain Python. The Discord
   files are gone.
 - Sets up its state when it loads, so game events can't crash it.
 - Reconnects by itself if Discord is closed and reopened.
 - Clears your Discord status when EDMC closes or the plugin is disabled.
 - The status messages and translations are the same as the original.
