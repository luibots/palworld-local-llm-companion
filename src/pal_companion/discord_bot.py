import discord
from discord import app_commands

from .config import Settings
from .rag import Companion


class CompanionBot(discord.Client):
    def __init__(self, settings: Settings):
        super().__init__(intents=discord.Intents.default())
        self.settings = settings
        self.tree = app_commands.CommandTree(self)
        self.companion = Companion(settings)

    async def setup_hook(self) -> None:
        if self.settings.discord_guild_id:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


def build_bot(settings: Settings) -> CompanionBot:
    bot = CompanionBot(settings)

    @bot.tree.command(name="askpal", description="Ask the source-grounded Palworld companion")
    @app_commands.describe(question="Locations, materials, Pals, strategies, or live server state")
    async def askpal(interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer(thinking=True)
        answer = await bot.companion.ask(question)
        citations = "\n".join(
            f"- [{source.source_id}] {source.title}"
            + (f": {source.url}" if source.url else "")
            for source in answer.sources[:6]
        )
        message = (
            f"{answer.text}\n\n**Confidence:** {answer.confidence}"
            + (f"\n**Sources**\n{citations}" if citations else "")
        )
        await interaction.followup.send(message[:2000])

    return bot


def run_discord(settings: Settings) -> None:
    if not settings.discord_token:
        raise RuntimeError("DISCORD_TOKEN is not configured")
    build_bot(settings).run(settings.discord_token, log_handler=None)
