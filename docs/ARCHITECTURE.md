# Architecture and data flow

The companion is local-first. The browser or optional in-game panel talks only to the
loopback FastAPI service. Retrieval happens before generation so Ollama receives an
evidence pack with stable source identifiers instead of an ungrounded question.

## C4 system context

```mermaid
%%{init: {"theme":"dark","flowchart":{"curve":"basis","htmlLabels":false,"nodeSpacing":70,"rankSpacing":90},"themeVariables":{"background":"#0d1117","primaryColor":"#161b22","primaryTextColor":"#f0f6fc","primaryBorderColor":"#58a6ff","lineColor":"#79c0ff","secondaryColor":"#21262d","tertiaryColor":"#30363d","clusterBkg":"#0d1117","clusterBorder":"#8b949e","fontFamily":"Segoe UI, Arial, sans-serif"}}}%%
flowchart LR
    PLAYER["Player\nPaldeck, CLI, or Discord"]
    COMPANION["Local LLM Companion\nGrounded answers with citations"]

    subgraph SYSTEMS["External systems"]
        direction LR
        PALWORLD["Palworld Client and Server\nRead context; validate item moves"]
        OLLAMA["Local Ollama\nEmbeddings and chat"]
        SERVICES["Brave Search and Discord\nOptional HTTPS services"]
    end

    PLAYER -->|"questions and answers"| COMPANION
    COMPANION -->|"read-only REST context"| PALWORLD
    PLAYER -->|"confirmed storage plan"| PALWORLD
    COMPANION -->|"local model calls"| OLLAMA
    COMPANION -.->|"optional HTTPS"| SERVICES

    classDef person fill:#1f2937,stroke:#a5d6ff,color:#f0f6fc,stroke-width:2px;
    classDef system fill:#13233a,stroke:#58a6ff,color:#f0f6fc,stroke-width:2px;
    classDef external fill:#2b2111,stroke:#d29922,color:#f0f6fc,stroke-width:2px;
    class PLAYER person;
    class COMPANION system;
    class PALWORLD,OLLAMA,SERVICES external;
    linkStyle default stroke:#79c0ff,stroke-width:2px,fill:none;
```

## Container view

```mermaid
%%{init: {"theme":"dark","flowchart":{"curve":"basis","htmlLabels":false,"nodeSpacing":55,"rankSpacing":75},"themeVariables":{"background":"#0d1117","primaryColor":"#161b22","primaryTextColor":"#f0f6fc","primaryBorderColor":"#58a6ff","lineColor":"#79c0ff","secondaryColor":"#21262d","tertiaryColor":"#30363d","clusterBkg":"#0d1117","clusterBorder":"#8b949e","fontFamily":"Segoe UI, Arial, sans-serif"}}}%%
flowchart LR
    subgraph SURFACES["Player surfaces"]
        direction LR
        GAME["F2 Paldeck, F3 vendors, F4 storage"]
        WEB["Local browser"]
        CLI["CLI and Discord"]
    end

    subgraph LOCAL["Local trust boundary"]
        direction LR
        UI["Static Paldeck UI"]
        BRIDGE["UE4SS client bridge"]
        API["Session-protected FastAPI"]
        RAG["RAG orchestrator"]

        subgraph SOURCES["Evidence sources"]
            direction LR
            INDEX[("SQLite vector index")]
            LIVE["Palworld REST read-only"]
            SEARCH["Brave Search"]
        end

        PACK["Bounded evidence pack"]
        MODEL["Local Ollama"]
        ANSWER["Answer, citations, and confidence"]

        UI --> API --> RAG
        UI --> BRIDGE
        RAG --> INDEX
        RAG -. "optional" .-> LIVE
        RAG -. "optional" .-> SEARCH
        INDEX --> PACK
        LIVE --> PACK
        SEARCH --> PACK
        PACK --> MODEL --> ANSWER
    end

    GAME --> UI
    WEB --> UI
    CLI --> API

    classDef surface fill:#1f2937,stroke:#a5d6ff,color:#f0f6fc,stroke-width:2px;
    classDef local fill:#13233a,stroke:#58a6ff,color:#f0f6fc,stroke-width:2px;
    classDef optional fill:#2b2111,stroke:#d29922,color:#f0f6fc,stroke-width:2px;
    class GAME,WEB,CLI surface;
    class API,RAG,INDEX,MODEL,UI,BRIDGE,PACK,ANSWER local;
    class LIVE,SEARCH optional;
    linkStyle default stroke:#79c0ff,stroke-width:2px,fill:none;
```

## Question sequence

```mermaid
%%{init: {"theme":"dark","sequence":{"useMaxWidth":true,"wrap":true,"diagramMarginX":30,"actorMargin":55,"messageMargin":35},"themeVariables":{"background":"#0d1117","primaryColor":"#161b22","primaryTextColor":"#f0f6fc","primaryBorderColor":"#58a6ff","lineColor":"#79c0ff","actorBkg":"#161b22","actorBorder":"#58a6ff","actorTextColor":"#f0f6fc","signalColor":"#79c0ff","signalTextColor":"#f0f6fc","labelBoxBkgColor":"#21262d","labelBoxBorderColor":"#8b949e","labelTextColor":"#f0f6fc","noteBkgColor":"#2b2111","noteBorderColor":"#d29922","noteTextColor":"#f0f6fc","fontFamily":"Segoe UI, Arial, sans-serif"}}}%%
sequenceDiagram
    autonumber
    actor Player
    participant UI as Paldeck UI
    participant API as Local API
    participant Index as Vector Index
    participant Live as Palworld REST
    participant Web as Web Search
    participant LLM as Ollama

    Player->>UI: Ask a Palworld question
    UI->>API: POST /ask with session cookie
    par Grounded local retrieval
        API->>Index: Embed and retrieve matching documents
        Index-->>API: Evidence with source IDs
    and Optional live context
        API->>Live: Read authorized player or world context
        Live-->>API: Current server facts
    and Optional current information
        API->>Web: Search recent guides or patch information
        Web-->>API: Labeled links and excerpts
    end
    API->>LLM: Question plus bounded evidence pack
    LLM-->>API: Answer constrained to supplied evidence
    API-->>UI: Answer, citations, and confidence
    UI-->>Player: Render the grounded response
```

## Security boundaries

- The UI and API bind to `127.0.0.1`; they are not a public server.
- `/ask` requires the same-origin session cookie issued when the Paldeck loads.
- Ollama runs locally. Prompts are not sent to a hosted model.
- Palworld REST access is optional and read-only.
- Storage Router is a separate confirmed write path. The client bridge revalidates
  labeled, loaded source slots and labeled same-base destinations before Palworld's server
  accepts or rejects each replicated item request.
- Server, Brave, and Discord credentials remain in local environment configuration.
- `.env`, generated indexes, private exports, and server data are excluded from Git.
- The UE4SS layer contains no server credentials and does not run Ollama. It displays
  the UI, reads loaded chest metadata, and submits only explicitly confirmed bounded
  item moves.

## Storage organizer sequence

```mermaid
%%{init: {"theme":"dark","sequence":{"useMaxWidth":true,"wrap":true,"diagramMarginX":30,"actorMargin":45,"messageMargin":32},"themeVariables":{"background":"#0d1117","primaryColor":"#161b22","primaryTextColor":"#f0f6fc","primaryBorderColor":"#58a6ff","lineColor":"#79c0ff","actorBkg":"#161b22","actorBorder":"#58a6ff","actorTextColor":"#f0f6fc","signalColor":"#79c0ff","signalTextColor":"#f0f6fc","labelBoxBkgColor":"#21262d","labelBoxBorderColor":"#8b949e","labelTextColor":"#f0f6fc","noteBkgColor":"#2b2111","noteBorderColor":"#d29922","noteTextColor":"#f0f6fc","fontFamily":"Segoe UI, Arial, sans-serif"}}}%%
sequenceDiagram
    autonumber
    actor Player
    participant Bridge as UE4SS Bridge
    participant UI as Storage Router UI
    participant API as Local API
    participant LLM as Local Ollama
    participant Game as Palworld Server

    Player->>Bridge: Press F4
    Bridge->>Bridge: Scan loaded item-storage models
    Bridge-->>UI: Labels, container IDs, and occupied slots
    UI->>API: POST /storage/plan
    API->>LLM: Exact item IDs and allowed labeled targets
    LLM-->>API: Strict JSON routes
    API-->>UI: Validated move preview
    Player->>UI: Arm, review, and confirm
    UI->>Bridge: Bounded move command
    Bridge->>Bridge: Revalidate labels, exact item, slot, count, and base
    Bridge->>Game: Replicated move request
    Game-->>Bridge: Server accepts or rejects operation
    Bridge-->>UI: Submission result and fresh scan
```

## Runtime modes

| Mode | Required locally | Server changes |
|---|---|---|
| Browser pilot | Python environment, Ollama, companion API | None |
| In-game Paldeck | Browser pilot requirements plus UE4SS and PalCompanionUI | None |
| Storage Router beta | In-game Paldeck plus named loaded chests | Server validates confirmed item moves |
| Discord | Python environment, Ollama, Discord token | None |
| Live context | Browser pilot requirements plus authorized Palworld REST settings | Read-only API must be available |
