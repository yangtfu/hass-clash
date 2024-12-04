"""Clash integration."""

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import ClashCoordinator

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Integretion setup."""
    host = config[DOMAIN][CONF_HOST]
    pwd = config[DOMAIN][CONF_PASSWORD]
    # Initialise coordinators
    coordinator = ClashCoordinator(hass, host, pwd)
    await coordinator.async_config_entry_first_refresh()

    # Add the coordinator to hass data to make
    # accessible throughout integration
    # TODO Note: this will change on HA2024.6 to save on the config entry.
    hass.data[DOMAIN] = {"coordinator": coordinator, "host": host, "pwd": pwd}

    # Load sensor and select entities.
    await hass.helpers.discovery.async_load_platform(
        Platform.SENSOR, DOMAIN, {}, config
    )
    await hass.helpers.discovery.async_load_platform(
        Platform.SELECT, DOMAIN, {}, config
    )

    return True
