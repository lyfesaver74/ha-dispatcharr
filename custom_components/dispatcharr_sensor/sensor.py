"""Sensor platform for Dispatcharr."""
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import PlatformNotReady

from .const import DOMAIN
from . import DispatcharrDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform from a ConfigEntry."""
    try:
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
    except KeyError:
        raise PlatformNotReady(f"Coordinator not found for entry {config_entry.entry_id}")
    
    # This platform now ONLY creates the total streams sensor.
    async_add_entities([DispatcharrTotalStreamSensor(coordinator)])


class DispatcharrTotalStreamSensor(CoordinatorEntity, SensorEntity):
    """A sensor to show the total number of active Dispatcharr streams."""
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(self, coordinator: DispatcharrDataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_name = "Total Active Streams"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_total_streams"
        self._attr_icon = "mdi:play-network"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.config_entry.entry_id)}, name="Dispatcharr")

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = len(self.coordinator.data or {})
        self.async_write_ha_state()
