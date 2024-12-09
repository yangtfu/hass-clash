"""Proxy sensors."""

from ast import literal_eval
from datetime import datetime
import logging

import aiohttp

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DELAY, CONF_TRAFFIC, CONF_URLTEST, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry, async_add_entities
) -> bool:
    """Set up platform from a ConfigEntry."""
    # Add options flow sensors.
    # if config_entry.options:
    #     delays = config_entry.options.get(CONF_DELAY, [])
    #     urltests = config_entry.options.get(CONF_URLTEST, [])
    #     traffics = config_entry.options.get(CONF_TRAFFIC, [])

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    # Add config flow sensors.
    delays = config_entry.options[CONF_DELAY]
    urltests = config_entry.options[CONF_URLTEST]
    traffics = config_entry.options[CONF_TRAFFIC]
    # Add sensors.
    sensors = [DelaySensor(coordinator, d) for d in delays]
    sensors.extend([URLTestSensor(coordinator, d) for d in urltests])
    sensors.extend([TrafficSensor(hass, coordinator, updown) for updown in traffics])

    async_add_entities(sensors)

    return True


class URLTestSensor(CoordinatorEntity, SensorEntity):
    """Sensors display URLTest and Selector options."""

    def __init__(self, coordinator, name) -> None:
        """Initialize."""
        super().__init__(coordinator, context=name)
        self.host = coordinator.host
        self.name_id = name
        self._proxy = coordinator.data.proxies[name]
        _LOGGER.info("URLTest sensor %s created", name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        self._proxy = self.coordinator.data.proxies[self.name_id]
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._proxy["name"]} urltest"

    @property
    def native_value(self) -> int:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.
        return self._proxy["now"]

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.host}-{self.name}"

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        # Add any additional attributes you want on your sensor.
        attrs = {}
        attrs["all"] = self._proxy["all"]
        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Identifiers are what group entities into the same device.
        # If your device is created elsewhere, you can just specify the identifiers parameter.
        # If your device connects via another device, add via_device parameter with the identifiers of that device.
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.host)
            },
            configuration_url=f"http://{self.host}/ui",
        )


class DelaySensor(CoordinatorEntity, SensorEntity):
    """Proxy delay sensor like ss/Trojan etc."""

    def __init__(self, coordinator, name) -> None:
        """Initialize."""
        super().__init__(coordinator, context=name)
        self.host = coordinator.host
        self.name_id = name
        self._proxy = coordinator.data.proxies[name]
        _LOGGER.info("Delay sensor %s created", name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        self._proxy = self.coordinator.data.proxies[self.name_id]
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._proxy["name"]} delay"

    @property
    def native_value(self) -> int:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.
        if (self._proxy["history"] is not None) and (len(self._proxy["history"]) > 0):
            return self._proxy["history"][0]["delay"]
        return None

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-device-classes
        return SensorDeviceClass.DURATION

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Identifiers are what group entities into the same device.
        # If your device is created elsewhere, you can just specify the identifiers parameter.
        # If your device connects via another device, add via_device parameter with the identifiers of that device.
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.host)
            },
            configuration_url=f"http://{self.host}/ui",
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of temperature."""
        return UnitOfTime.MILLISECONDS

    @property
    def state_class(self) -> str:
        """Return state class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
        return SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.host}-{self.name}"

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        # Add any additional attributes you want on your sensor.
        attrs = {}
        attrs["type"] = self._proxy["type"]
        attrs["udp"] = self._proxy["udp"]
        if (self._proxy["history"] is not None) and (len(self._proxy["history"]) > 0):
            attrs["last_check"] = datetime.fromisoformat(
                self._proxy["history"][0]["time"]
            )
        return attrs


class TrafficSensor(SensorEntity):
    """Traffic sensor of updown speed."""

    def __init__(self, hass: HomeAssistant, coordinator, updown) -> None:
        """Initialize."""
        self.value = None
        self.updown = updown
        self.session = async_get_clientsession(hass=hass, verify_ssl=False)
        self.host = coordinator.host
        self.headers = coordinator.headers
        self._attr_should_poll = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"traffic {self.updown}"

    @property
    def native_value(self) -> float:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.
        return self.value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of KB/s."""
        return UnitOfDataRate.KILOBYTES_PER_SECOND

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.host}-{self.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Identifiers are what group entities into the same device.
        # If your device is created elsewhere, you can just specify the identifiers parameter.
        # If your device connects via another device, add via_device parameter with the identifiers of that device.
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.host)
            },
            configuration_url=f"http://{self.host}/ui",
        )

    @property
    def state_class(self) -> str:
        """Return state class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
        return SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Update all sensors."""
        # Use this to setup async function callbacks when using push method.
        ws = await self.session.ws_connect(
            f"http://{self.host}/traffic", headers=self.headers
        )
        self.hass.loop.create_task(self.async_receive_msg(ws))

    async def async_receive_msg(self, ws) -> None:
        """Receive message and write into ha."""
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                value = float(literal_eval(msg.data[:-1])[self.updown]) / 1024
                if self.value != value:
                    self.value = value
                    # _LOGGER.debug("Traffic %s: %f", self.updown, self.value)
                    self.schedule_update_ha_state()
            elif msg.type == (aiohttp.WSMsgType.CLOSE or aiohttp.WSMsgType.ERROR):
                ws = await self.session.ws_connect(
                    f"http://{self.host}/traffic", headers=self.headers
                )
