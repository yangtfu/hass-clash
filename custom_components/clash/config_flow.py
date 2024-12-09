"""Config flow for Clash integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import ClientConnectorError, ClientResponseError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er

from .const import (
    CONF_DELAY,
    CONF_SELECTOR,
    CONF_TRAFFIC,
    CONF_URLTEST,
    DELAY_TEST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST, description={"suggested_value": "127.0.0.1:9090"}
        ): cv.string,
        vol.Optional(CONF_PASSWORD, description={"suggested_value": ""}): cv.string,
    }
)


async def validate_auth(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    session = async_get_clientsession(hass=hass, verify_ssl=False)
    host = f"http://{data[CONF_HOST]}/proxies"
    headers = (
        {"authorization": f"Bearer {data[CONF_PASSWORD]}"}
        if CONF_PASSWORD in data
        else None
    )
    try:
        async with session.get(host, headers=headers) as resp:
            resp.raise_for_status()
            return json.loads(await resp.text())["proxies"]
        # If you cannot connect, raise CannotConnect
        # If the authentication is wrong, raise InvalidAuth
    except ClientConnectorError as err:
        raise CannotConnect from err
    except ClientResponseError as err:
        if err.message == "Unauthorized":
            raise InvalidAuth from err


def create_entities_schema(proxies, options) -> vol.Schema:
    """Create entities select schema."""
    delays = [p for p, v in proxies.items() if v["type"] in DELAY_TEST]
    urltests = [p for p, v in proxies.items() if v["type"] == "URLTest"]
    selectors = [p for p, v in proxies.items() if v["type"] == "Selector"]
    return vol.Schema(
        {
            vol.Optional(CONF_DELAY, default=options.get(CONF_DELAY)): cv.multi_select(
                delays
            ),
            vol.Optional(
                CONF_URLTEST, default=options.get(CONF_URLTEST)
            ): cv.multi_select(urltests),
            vol.Optional(
                CONF_TRAFFIC, default=options.get(CONF_TRAFFIC)
            ): cv.multi_select(["up", "down"]),
            vol.Optional(
                CONF_SELECTOR, default=options.get(CONF_SELECTOR)
            ): cv.multi_select(selectors),
        }
    )


class ClashConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Clash Integration."""

    VERSION = 1
    data: dict[str, Any]
    proxies: dict[str, Any]
    options: dict[str, Any]
    _unique_id: str

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        # Remove this method and the ExampleOptionsFlowHandler class
        # if you do not want any options for your integration.
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Called when you initiate adding an integration via the UI
        errors: dict[str, str] = {}

        if user_input is not None:
            # The form has been filled in and submitted, so process the data provided.
            try:
                # Validate that the setup data is valid and if not handle errors.
                # The errors["base"] values match the values in your strings.json and translation files.
                self.proxies = await validate_auth(self.hass, user_input)
                self.options = {
                    CONF_DELAY: [],
                    CONF_URLTEST: [],
                    CONF_TRAFFIC: [],
                    CONF_SELECTOR: [],
                }
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                self.data = user_input
                # Validation was successful, so create a unique id for this instance of your integration and create the config entry.
                self._unique_id = f"Clash - {self.data[CONF_HOST]}"
                await self.async_set_unique_id(self._unique_id)
                # If unique id already exists, then abort the config flow.
                # The Unique ID can be used to update the config entry data when device access details change.
                self._abort_if_unique_id_configured()
                return await self.async_step_entities()

        # Show initial form.
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the entities selection."""
        errors: dict[str, str] = {}

        ENTITIES_SCHEMA = create_entities_schema(self.proxies, self.options)

        if user_input is not None:
            return self.async_create_entry(
                title=self._unique_id, data=self.data, options=user_input
            )

        # Show form.
        return self.async_show_form(
            step_id="entities", data_schema=ENTITIES_SCHEMA, errors=errors
        )


class OptionsFlowHandler(OptionsFlow):
    """Handles the options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle options flow."""

        errors: dict[str, str] = {}
        # Grab all configured repos from the entity registry so we can populate the
        # multi-select dropdown that will allow a user to remove a repo.
        entity_registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        proxies = await validate_auth(self.hass, self.config_entry.data)
        ENTITIES_SCHEMA = create_entities_schema(proxies, self.config_entry.options)

        if user_input is not None:
            # Validation was successful, so create a unique id for this instance of your integration and create the config entry.
            # Remove any unchecked entities.
            # Store unique_id of selected entities.
            user_input_entities = []
            for k, v in user_input.items():
                user_input_entities.extend([f"{DOMAIN}-{k}-{name}" for name in v])
            # Store entity_id to be removed.
            removed_entities_id = [
                e.entity_id for e in entries if e.unique_id not in user_input_entities
            ]
            for entity_id in removed_entities_id:
                # Unregister from HA
                entity_registry.async_remove(entity_id)

            options = self.config_entry.options | user_input
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init", data_schema=ENTITIES_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
