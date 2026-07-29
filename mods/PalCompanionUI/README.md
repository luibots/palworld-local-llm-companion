# Pal Companion UI

Client-only UE4SS Lua prototype. Press `F2` while in a world to open the local
Pal Companion at `http://127.0.0.1:8765/`. Press `F3` to open the verified vendor
directory directly without an LLM request. The overlay passes the local player name
to the companion so an authorized live-server connection can match level and location.
While the overlay is visible, it captures keyboard and mouse input for the embedded
browser so typing cannot also trigger Palworld controls. Closing it restores the
game's previous movement and camera input state; `Escape` provides an in-browser
close path in addition to the `F2` toggle.

Press `F4` to open the private Storage Router beta. It scans only loaded item-storage
models built by the current player, uses chest names as routing labels, ignores
unlabeled storage, previews every stack move, and submits a confirmed plan through
Palworld's replicated item-move request. Other-player and unknown-owner chests fail
closed. It never edits saves.

Press `F5` to open Private Admin Supplies. The panel searches the locally indexed item
catalog and submits a two-step-confirmed grant through the loopback companion service.
The target player is fixed in local configuration and cannot be selected from the UI.
The companion requires a dedicated-server PalDefender endpoint and a bearer token
restricted to `REST.Items.Give`. Grants do not call Palworld broadcast or the guild
Discord queue. PalDefender may retain a private server-side administrative log.

This mod does not contain Ollama, credentials, game data, or server code. It only
creates an Unreal UMG browser panel and points it at the loopback companion service.
Answers can be read aloud through the embedded browser's free operating-system voice.
Location answers expose structured coordinates, and the in-game panel can pass up to
12 of them to Palworld's local custom map-marker system after the player confirms.
Resource, Pal, boss, dungeon, egg, base, food, and person results use the closest
native Palworld marker icon. Neither feature contacts or changes the dedicated server.
Optional microphone confirmation uses the companion process and default Windows
microphone only while a marker question is visible. Windows uses a constrained
yes/no grammar instead of loading a speech AI model. The bundled chime plays after the
Lua bridge acknowledges successful placement.

The vendor directory uses a bundled, verified catalog, optionally sorts locations by
the player's live position, and places a native person marker. Its guild action queues
a sanitized location event for the existing PAL COMMAND Discord bot. It does not send
credentials, live player coordinates, or arbitrary text to Discord.

The current script is a development prototype targeting Palworld Steam build
`24181527`. It must be tested against the current UE4SS experimental Palworld fork
before Workshop packaging. Marker placement uses reflected
`PalLocationManager:AddLocalCustomMarker` behavior and logs failures to the UE4SS
console if the current game build changes that function.
