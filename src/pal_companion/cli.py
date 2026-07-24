import argparse
import asyncio
from pathlib import Path

import uvicorn

from .config import Settings
from .discord_bot import run_discord
from .game_data import build_game_documents, write_jsonl
from .ingest import ingest_jsonl
from .rag import Companion


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="pal-companion")
    commands = root.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Index a JSONL game-data export")
    ingest.add_argument("path", type=Path)
    ingest.add_argument(
        "--replace-prefix",
        help="Remove stale indexed documents sharing this source ID prefix",
    )

    game_data = commands.add_parser(
        "game-data",
        help="Build private JSONL documents from converted local Palworld tables",
    )
    game_data.add_argument("--tables-dir", type=Path, required=True)
    game_data.add_argument("--output", type=Path, required=True)
    game_data.add_argument("--game-build", default="unknown")

    ask = commands.add_parser("ask", help="Ask from the terminal")
    ask.add_argument("question")
    ask.add_argument("--no-web", action="store_true")
    ask.add_argument("--no-live", action="store_true")

    api = commands.add_parser("api", help="Run the local HTTP API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8765)

    commands.add_parser("discord", help="Run the Discord bot")
    return root


async def _run_async(args: argparse.Namespace, settings: Settings) -> None:
    companion = Companion(settings)
    if args.command == "ingest":
        count = await ingest_jsonl(
            args.path,
            companion.store,
            companion.ollama,
            replace_prefix=args.replace_prefix,
        )
        print(f"Indexed {count} documents.")
    elif args.command == "game-data":
        count = write_jsonl(
            build_game_documents(args.tables_dir, args.game_build),
            args.output,
        )
        print(f"Wrote {count} private game-data documents.")
    elif args.command == "ask":
        answer = await companion.ask(
            args.question,
            allow_web=not args.no_web,
            include_live=not args.no_live,
        )
        print(answer.text)
        print(f"\nConfidence: {answer.confidence}")
        for source in answer.sources:
            print(f"- [{source.source_id}] {source.title}: {source.url or 'local'}")


def main() -> None:
    args = parser().parse_args()
    settings = Settings()
    if args.command == "api":
        uvicorn.run("pal_companion.api:app", host=args.host, port=args.port)
    elif args.command == "discord":
        run_discord(settings)
    else:
        asyncio.run(_run_async(args, settings))


if __name__ == "__main__":
    main()
