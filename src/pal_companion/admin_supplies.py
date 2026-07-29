import asyncio
import json
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx

from .config import Settings


class AdminSupplyError(RuntimeError):
    pass


class AdminSupplies:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        rcon_runner: Callable[[str, str, int], Awaitable[str]] | None = None,
    ):
        self.enabled = settings.admin_supplies_enabled
        self.supply_transport = settings.admin_supplies_transport.lower()
        self.base_url = settings.paldefender_url.rstrip("/")
        self.token = settings.paldefender_token
        self.rcon_helper = settings.palcommand_rcon_helper
        self.player_id = settings.admin_supply_player_id
        self.max_count = settings.admin_supply_max_count
        self.max_progression = settings.admin_supply_max_progression
        self.transport = transport
        self.rcon_runner = rcon_runner

    @property
    def configured(self) -> bool:
        if not self.enabled or not self.player_id:
            return False
        if self.supply_transport == "rcon":
            return bool(self.rcon_runner or self.rcon_helper)
        return bool(self.base_url and self.token)

    async def _run_rcon(self, action: str, item_id: str = "", amount: int = 1) -> str:
        if self.rcon_runner:
            return await self.rcon_runner(action, item_id, amount)
        if not self.rcon_helper:
            raise AdminSupplyError("The private RCON helper is not configured.")

        arguments = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.rcon_helper),
            "-Action",
            action,
            "-Amount",
            str(amount),
        ]
        if item_id:
            arguments.extend(["-ItemId", item_id])
        try:
            process = await asyncio.create_subprocess_exec(
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        except (OSError, TimeoutError) as error:
            raise AdminSupplyError("The private RCON grant service is unreachable.") from error

        try:
            payload = json.loads(stdout.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AdminSupplyError("The private RCON helper returned invalid data.") from error
        if process.returncode != 0 or not payload.get("Success"):
            raise AdminSupplyError("PalDefender rejected the private RCON grant.")
        return str(payload.get("Response", ""))

    async def grant(self, item_id: str, count: int) -> int:
        if not self.configured:
            raise AdminSupplyError("Private Admin Supplies is not configured.")
        if count < 1 or count > self.max_count:
            raise AdminSupplyError(
                f"Quantity must be between 1 and {self.max_count:,}."
            )

        if self.supply_transport == "rcon":
            await self._run_rcon("GrantItem", item_id, count)
            return count

        endpoint = (
            f"{self.base_url}/v1/pdapi/give/items/"
            f"{quote(self.player_id, safe='')}"
        )
        try:
            async with httpx.AsyncClient(
                timeout=10,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"Items": [{"ItemID": item_id, "Count": count}]},
                )
        except httpx.HTTPError as error:
            raise AdminSupplyError("The private server grant service is unreachable.") from error

        if response.status_code == 401:
            raise AdminSupplyError("The private server grant token was rejected.")
        if response.status_code == 403:
            raise AdminSupplyError("The private token cannot grant items.")
        if response.status_code >= 400:
            try:
                detail = response.json().get("Error", {}).get("Message")
            except ValueError:
                detail = None
            raise AdminSupplyError(detail or f"Item grant failed ({response.status_code}).")

        try:
            granted = int(response.json()["Granted"]["Items"])
        except (KeyError, TypeError, ValueError) as error:
            raise AdminSupplyError("The server returned an invalid grant response.") from error
        if granted < 1:
            raise AdminSupplyError("The server did not grant any items.")
        return granted

    async def grant_progression(self, kind: str, amount: int) -> tuple[int, int | None]:
        if not self.configured:
            raise AdminSupplyError("Private Admin Supplies is not configured.")
        if amount < 1 or amount > self.max_progression:
            raise AdminSupplyError(
                f"Progression amount must be between 1 and {self.max_progression:,}."
            )
        fields = {
            "technology_points": "TechnologyPoints",
            "ancient_technology_points": "AncientTechnologyPoints",
        }
        field = fields.get(kind)
        if field is None:
            raise AdminSupplyError("Unsupported progression grant.")

        if self.supply_transport == "rcon":
            actions = {
                "technology_points": "GrantTechnologyPoints",
                "ancient_technology_points": "GrantAncientTechnologyPoints",
            }
            await self._run_rcon(actions[kind], amount=amount)
            return amount, None

        endpoint = (
            f"{self.base_url}/v1/pdapi/give/progression/"
            f"{quote(self.player_id, safe='')}"
        )
        try:
            async with httpx.AsyncClient(
                timeout=10,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={field: amount},
                )
        except httpx.HTTPError as error:
            raise AdminSupplyError("The private server grant service is unreachable.") from error

        if response.status_code == 401:
            raise AdminSupplyError("The private server grant token was rejected.")
        if response.status_code == 403:
            raise AdminSupplyError("The private token cannot grant progression.")
        if response.status_code >= 400:
            try:
                detail = response.json().get("Error", {}).get("Message")
            except ValueError:
                detail = None
            raise AdminSupplyError(
                detail or f"Progression grant failed ({response.status_code})."
            )

        try:
            payload = response.json()
            granted = int(payload["Granted"][field])
            raw_total = payload.get("Totals", {}).get(field)
            total = int(raw_total) if raw_total is not None else None
        except (KeyError, TypeError, ValueError) as error:
            raise AdminSupplyError("The server returned an invalid grant response.") from error
        if granted < 1:
            raise AdminSupplyError("The server did not grant any progression.")
        return granted, total
