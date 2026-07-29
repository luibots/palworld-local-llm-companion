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
    ):
        self.enabled = settings.admin_supplies_enabled
        self.base_url = settings.paldefender_url.rstrip("/")
        self.token = settings.paldefender_token
        self.player_id = settings.admin_supply_player_id
        self.max_count = settings.admin_supply_max_count
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.base_url and self.token and self.player_id)

    async def grant(self, item_id: str, count: int) -> int:
        if not self.configured:
            raise AdminSupplyError("Private Admin Supplies is not configured.")
        if count < 1 or count > self.max_count:
            raise AdminSupplyError(
                f"Quantity must be between 1 and {self.max_count:,}."
            )

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
