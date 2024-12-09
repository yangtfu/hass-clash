"""Clash integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from homeassistant.helpers.device_registry import DeviceEntry

# from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN
from .coordinator import ClashCoordinator

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Integretion setup."""
    hass.data.setdefault(DOMAIN, {})

    # Initialise coordinators
    coordinator = ClashCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Initialise a listener for config flow options changes.
    # See config_flow for defining an options setting that shows up as configure on the integration.
    # Registers update listener to update config entry when options are updated.
    config_entry.async_on_unload(
        config_entry.add_update_listener(options_update_listener)
    )

    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    # accessible throughout your integration
    # Note: this will change on HA2024.6 to save on the config entry.
    hass.data[DOMAIN][config_entry.entry_id] = {
        "coordinator": coordinator,
    }

    # forward the Config Entry to the platform.
    # For a platform to support config entries, it will need to add a setup entry method.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def options_update_listener(hass: HomeAssistant, config_entry):
    """Handle config options update.

    Reload the integration when the options change.
    """
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI."""
    # Adding this function shows the delete device option in the UI.
    # Remove this function if you do not want that option.
    # You may need to do some checks here before allowing devices to be removed.
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry.

    This is called when you remove your integration or shutdown HA.
    If you have created any custom services, they need to be removed here too.
    """

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # Remove the config entry from the hass data object.
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    # Return that unloading was successful.
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    # If a component needs to clean up code when an entry is removed, it can define
    # this removal method.
    _LOGGER.debug("%s config entry removed", DOMAIN)
