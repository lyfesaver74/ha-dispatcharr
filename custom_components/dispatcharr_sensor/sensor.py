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
    
    DispatcharrStreamManager(coordinator, async_add_entities)
    async_add_entities([DispatcharrTotalStreamSensor(coordinator)])


class DispatcharrStreamManager:
    """Manages the creation and removal of stream sensors."""
    def __init__(self, coordinator: DispatcharrDataUpdateCoordinator, async_add_entities: AddEntitiesCallback):
        self._coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._known_stream_ids = set()
        self._coordinator.async_add_listener(self._update_sensors)

    @callback
    def _update_sensors(self) -> None:
        """Update, add, or remove sensors based on coordinator data."""
        if self._coordinator.data is None:
            current_stream_ids = set()
        else:
            current_stream_ids = set(self._coordinator.data.keys())
        
        new_stream_ids = current_stream_ids - self._known_stream_ids
        if new_stream_ids:
            new_sensors = [DispatcharrStreamSensor(self._coordinator, stream_id) for stream_id in new_stream_ids]
            self._async_add_entities(new_sensors)
            self._known_stream_ids.update(new_stream_ids)

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


class DispatcharrStreamSensor(CoordinatorEntity, SensorEntity):
    """Representation of a single, dynamic Dispatcharr stream sensor."""
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: DispatcharrDataUpdateCoordinator, stream_id: str):
        super().__init__(coordinator)
        self._stream_id = stream_id
        
        channel_details = coordinator.channel_details.get(stream_id) or {}
        name = channel_details.get("name", f"Stream {self._stream_id[-6:]}")
        
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._stream_id}"
        self._attr_icon = "mdi:television-stream"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.config_entry.entry_id)}, name="Dispatcharr")

    @property
    def available(self) -> bool:
        """Return True if the stream is still in the coordinator's data."""
        return super().available and self.coordinator.data is not None and self._stream_id in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.available:
            self.async_write_ha_state()
            return
            
        stream_data = self.coordinator.data[self._stream_id]
        program_data = stream_data.get("program") or {}
        channel_details = self.coordinator.channel_details.get(self._stream_id) or {}
        
        self._attr_native_value = "Streaming"
        self._attr_entity_picture = stream_data.get("logo_url")
        self._attr_name = channel_details.get("name", self._attr_name)
        self._attr_extra_state_attributes = {
            "channel_number": channel_details.get("channel_number"),
            "channel_name": channel_details.get("name"),
            "logo_url": stream_data.get("logo_url"),
            "clients": stream_data.get("client_count"),
            "resolution": stream_data.get("resolution"),
            "fps": stream_data.get("source_fps"),
            "video_codec": stream_data.get("video_codec"),
            "audio_codec": stream_data.get("audio_codec"),
            "avg_bitrate": stream_data.get("avg_bitrate"),
            "program_title": program_data.get("title"),
            "episode_title": program_data.get("subtitle"),
            "episode_number": program_data.get("episode_num"),
            "program_description": program_data.get("description"),
            "program_start": program_data.get("start_time"),
            "program_stop": program_data.get("end_time"),
        }
        self.async_write_ha_state()
