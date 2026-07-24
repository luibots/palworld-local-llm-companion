# Pal Companion UI

Client-only UE4SS Lua prototype. Press `F2` while in a world to open the local
Pal Companion at `http://127.0.0.1:8765/`.

This mod does not contain Ollama, credentials, game data, or server code. It only
creates an Unreal UMG browser panel and points it at the loopback companion service.

The current script is a development prototype targeting Palworld Steam build
`24181527`. It must be tested against the current UE4SS experimental Palworld fork
before Workshop packaging.
