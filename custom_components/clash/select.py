"""Proxy sensors."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the select platform."""

    coordinator = hass.data[DOMAIN]["coordinator"]

    selectors = [
        ClashSelector(coordinator, d["name"])
        for d in coordinator.data.proxies.values()
        if d["type"] == "Selector"
    ]
    selectors.append(
        ClashMode(
            coordinator,
        )
    )
    async_add_entities(selectors)


class ClashSelector(CoordinatorEntity, SelectEntity):
    """Clash selectors."""

    def __init__(self, coordinator, name) -> None:
        """Initialize."""
        super().__init__(coordinator, context=name)
        self.name_id = name
        self._proxy = coordinator.data.proxies[name]
        self._coordinator = coordinator
        _LOGGER.info("Selector %s created", name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        self._proxy = self.coordinator.data.proxies[self.name_id]
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._proxy["name"]} select"

    @property
    def current_option(self) -> str | None:
        """Return the current activity."""
        return self._proxy["now"]

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self._proxy["all"]

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self._proxy["name"]}-delay"

    async def async_select_option(self, option: str) -> None:
        """Change the current activity."""
        await self._coordinator.select_selector(self.name_id, option)
        self.schedule_update_ha_state(force_refresh=True)


class ClashMode(CoordinatorEntity, SelectEntity):
    """Clash selectors."""

    def __init__(self, coordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, context=0)
        self._coordinator = coordinator
        _LOGGER.info("Clash mode select created")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Clash mode"

    @property
    def current_option(self) -> str | None:
        """Return the current activity."""
        return self._coordinator.data.clash_mode

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return ["direct", "rule", "global"]

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-mode"

    async def async_select_option(self, option: str) -> None:
        """Change the current activity."""
        await self._coordinator.select_mode(option)
        self.schedule_update_ha_state(force_refresh=True)
