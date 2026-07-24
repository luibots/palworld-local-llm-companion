# Pal Companion UI

Client-only UE4SS Lua prototype. Press `F2` while in a world to open the local
Pal Companion at `http://127.0.0.1:8765/`. The overlay passes the local player name
to the companion so an authorized live-server connection can match level and location.

This mod does not contain Ollama, credentials, game data, or server code. It only
creates an Unreal UMG browser panel and points it at the loopback companion service.
Answers can be read aloud through the embedded browser's free operating-system voice.
Location answers expose structured coordinates, and the in-game panel can pass up to
12 of them to Palworld's local custom map-marker system after the player confirms.
Resource, Pal, boss, dungeon, egg, base, food, and person results use the closest
native Palworld marker icon. Neither feature contacts or changes the dedicated server.
Optional microphone confirmation uses the companion process and default Windows
microphone only while a marker question is visible. The bundled chime plays after
the Lua bridge acknowledges successful placement.

The current script is a development prototype targeting Palworld Steam build
`24181527`. It must be tested against the current UE4SS experimental Palworld fork
before Workshop packaging. Marker placement uses reflected
`PalLocationManager:AddLocalCustomMarker` behavior and logs failures to the UE4SS
console if the current game build changes that function.
