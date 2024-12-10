"""Coordinators."""

from dataclasses import dataclass
from datetime import timedelta
import json
import logging

from aiohttp import ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class ClashData:
    """Clash mode and proxies."""

    clash_mode: str
    proxies: dict[str, dict]


class ClashCoordinator(DataUpdateCoordinator):
    """Clash coordinator."""

    data: ClashData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""

        super().__init__(
            hass,
            _LOGGER,
            name="Clash http coordinator",
            #  If the data returned from the API can be compared for changes with
            # the Python __eq__ method, set always_update=False when creating the
            # DataUpdateCoordinator to avoid unnecessary callbacks and writes to
            # the state machine.
            always_update=False,
            update_method=self.async_update_data,
            setup_method=self.async_setup,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        # Set variables from values entered in config flow setup
        self.host = config_entry.data[CONF_HOST]
        self.hass = hass
        self.headers = (
            {"authorization": f"Bearer {config_entry.data[CONF_PASSWORD]}"}
            if CONF_PASSWORD in config_entry.data
            else None
        )
        self.session = async_get_clientsession(hass=self.hass, verify_ssl=False)
        self.proxies = []
        self._mode = None

    async def async_setup(self):
        """Set up the coordinator.

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        proxies = await self.update_proxy()
        self.proxies = proxies.keys()
        self.data = ClashData(clash_mode=(await self.update_mode()), proxies=proxies)

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # What is returned here is stored in self.data by the DataUpdateCoordinator
        listening_entities = set(self.async_contexts())
        proxies_to_update = {}
        mode = ""
        if listening_entities:
            for name in self.proxies:
                if name in listening_entities:
                    proxies_to_update[name] = await self.update_proxy(proxy=name)
            if 0 in listening_entities:
                mode = await self.update_mode()
            # _LOGGER.debug(proxies_to_update)
            return ClashData(clash_mode=mode, proxies=proxies_to_update)

        return ClashData(
            clash_mode=(await self.update_mode()), proxies=(await self.update_proxy())
        )

    async def update_proxy(self, proxy=None) -> dict[str, dict] | None:
        """Update proxy data."""
        try:
            if proxy is None:
                async with self.session.get(
                    f"http://{self.host}/proxies",
                    headers=self.headers,
                ) as resp:
                    return json.loads(await resp.text())["proxies"]
            if proxy in self.proxies:
                async with self.session.get(
                    f"http://{self.host}/proxies/{proxy}",
                    headers=self.headers,
                ) as resp:
                    return json.loads(await resp.text())
        except ClientResponseError as e:
            _LOGGER.error("Proxy update error: %s", e)
            return None

    async def update_mode(self) -> str:
        """Update config data."""
        async with self.session.get(
            f"http://{self.host}/configs",
            headers=self.headers,
        ) as resp:
            resp.raise_for_status()
            self._mode = json.loads(await resp.text())["mode"].capitalize()
        return self._mode

    async def select_selector(self, proxy, option) -> None:
        """Select clash mode."""
        await self.session.put(
            f"http://{self.host}/proxies/{proxy}",
            headers=self.headers,
            data=f'{{"name": "{option}"}}',
        )

    async def select_mode(self, option) -> None:
        """Select clash mode."""
        await self.session.patch(
            f"http://{self.host}/configs",
            headers=self.headers,
            data=f'{{"mode": "{option}"}}',
        )
