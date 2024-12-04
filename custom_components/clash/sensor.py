"""Proxy sensors."""

from ast import literal_eval
from datetime import datetime
import logging

import aiohttp

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DELAY_TEST, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    # # We only want this platform to be set up via discovery.
    # if discovery_info is None:
    #     return

    coordinator = hass.data[DOMAIN]["coordinator"]
    host = hass.data[DOMAIN]["host"]
    pwd = hass.data[DOMAIN]["pwd"]

    delay_sensors = [
        DelaySensor(coordinator, d["name"])
        for d in coordinator.data.proxies.values()
        if d["type"] in DELAY_TEST
    ]
    urltest_sensors = [
        URLTestSensor(coordinator, d["name"])
        for d in coordinator.data.proxies.values()
        if ("now" in d) and (d["type"] == "URLTest")
    ]
    traffic_sensors = [
        TrafficSensor(hass, host, pwd, "up"),
        TrafficSensor(hass, host, pwd, "down"),
    ]
    async_add_entities(delay_sensors)
    async_add_entities(urltest_sensors)
    async_add_entities(traffic_sensors)


class URLTestSensor(CoordinatorEntity, SensorEntity):
    """Sensors display URLTest and Selector options."""

    def __init__(self, coordinator, name) -> None:
        """Initialize."""
        super().__init__(coordinator, context=name)
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
        return f"{self._proxy["name"]} select"

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
        return f"{DOMAIN}-urltest-{self._proxy["name"]}"

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        # Add any additional attributes you want on your sensor.
        attrs = {}
        attrs["all"] = self._proxy["all"]
        return attrs


class DelaySensor(CoordinatorEntity, SensorEntity):
    """Proxy delay sensor like ss/Trojan etc."""

    def __init__(self, coordinator, name) -> None:
        """Initialize."""
        super().__init__(coordinator, context=name)
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

    # @property
    # def device_info(self) -> DeviceInfo:
    #     """Return device information."""
    #     # Identifiers are what group entities into the same device.
    #     # If your device is created elsewhere, you can just specify the indentifiers parameter.
    #     # If your device connects via another device, add via_device parameter with the indentifiers of that device.
    #     return DeviceInfo(
    #         name="Clash server",
    #         # manufacturer="ACME Manufacturer",
    #         # model="Door&Temp v1",
    #         # sw_version="1.0",
    #         identifiers={
    #             (
    #                 DOMAIN,
    #                 "Clash",
    #             )
    #         },
    #     )

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
        return f"{DOMAIN}-{self._proxy["name"]}-delay"

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

    def __init__(self, hass: HomeAssistant, host, pwd, updown) -> None:
        """Initialize."""
        self.value = None
        self.updown = updown
        self.session = async_get_clientsession(hass=hass, verify_ssl=False)
        self.host = host
        self.pwd = pwd
        self._attr_should_poll = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Clash {self.updown}"

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
        return f"{DOMAIN}-{self.updown}"

    @property
    def state_class(self) -> str:
        """Return state class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
        return SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Update all sensors."""
        # Use this to setup async function callbacks when using push method.
        ws = await self.session.ws_connect(
            f"ws://{self.host}/traffic",
            headers={"authorization": f"Bearer {self.pwd}"},
        )
        self.hass.loop.create_task(self.async_receive_msg(ws))

    async def async_receive_msg(self, ws) -> None:
        """Receive message and write into ha."""
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                value = float(literal_eval(msg.data[:-1])[self.updown]) / 1024
                if self.value != value:
                    self.value = value
                    _LOGGER.debug("Traffic %s: %f", self.updown, self.value)
                    self.schedule_update_ha_state()
            elif msg.type == (aiohttp.WSMsgType.CLOSE or aiohttp.WSMsgType.ERROR):
                ws = await self.session.ws_connect(
                    f"ws://{self.host}/traffice",
                    headers={"authorization": f"Bearer {self.pwd}"},
                )
