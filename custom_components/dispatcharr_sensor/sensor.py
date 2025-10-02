"""Sensor platform for Dispatcharr."""
import logging
from datetime import timedelta, datetime, timezone
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = DispatcharrDataUpdateCoordinator(hass, config_entry)
    
    try:
        await coordinator.async_populate_channel_details()
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    
    # This manager will add and remove stream sensors dynamically
    DispatcharrStreamManager(coordinator, async_add_entities)
    
    # Add the static "total" sensor
    async_add_entities([DispatcharrTotalStreamSensor(coordinator)])


class DispatcharrDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize."""
        self.config_entry = config_entry
        self.websession = aiohttp.ClientSession()
        self._access_token: str | None = None
        self.channel_details: dict = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @property
    def base_url(self) -> str:
        """Get the base URL for API calls."""
        data = self.config_entry.data
        protocol = "https" if data.get("ssl", False) else "http"
        return f"{protocol}://{data['host']}:{data['port']}"

    async def _api_request(self, method: str, url: str, is_json: bool = True, **kwargs):
        """Make an authenticated API request, refreshing token if necessary."""
        if not self._access_token:
            await self._get_new_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        
        try:
            response = await self.websession.request(method, url, headers=headers, **kwargs)
            if response.status == 401:
                _LOGGER.info("Access token expired, requesting a new one")
                await self._get_new_token()
                headers["Authorization"] = f"Bearer {self._access_token}"
                response = await self.websession.request(method, url, headers=headers, **kwargs)

            response.raise_for_status()
            return await response.json() if is_json else await response.text()

        except aiohttp.ClientResponseError as err:
            if "epg/grid" in url and err.status == 404:
                _LOGGER.warning("EPG Grid returned a 404 for the requested channels, treating as no program data.")
                return {}
            raise UpdateFailed(f"API request failed for {url}: {err.status} {err.message}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _get_new_token(self) -> str:
        """Get a new access token using username and password."""
        _LOGGER.debug("Requesting new access token from Dispatcharr")
        url = f"{self.base_url}/api/accounts/token/"
        auth_data = {
            "username": self.config_entry.data["username"],
            "password": self.config_entry.data["password"],
        }
        try:
            async with self.websession.post(url, json=auth_data) as response:
                response.raise_for_status()
                tokens = await response.json()
                self._access_token = tokens.get("access")
                if self._access_token:
                    _LOGGER.info("Successfully authenticated with Dispatcharr")
                    return self._access_token
                raise ConfigEntryNotReady("Authentication successful, but no access token was provided")
        except aiohttp.ClientError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryNotReady(f"Authentication failed: {err}") from err

    async def async_populate_channel_details(self):
        """Fetch all channel details to build a lookup map."""
        _LOGGER.info("Populating Dispatcharr channel details")
        all_channels = await self._api_request("GET", f"{self.base_url}/api/channels/channels/")
        
        if isinstance(all_channels, list):
            self.channel_details = {
                channel['uuid']: channel for channel in all_channels if 'uuid' in channel
            }
        else:
            _LOGGER.warning("Expected a list of channels but received: %s", type(all_channels))
            self.channel_details = {}
        
        _LOGGER.debug("Found %d channels", len(self.channel_details))

    async def _get_current_programs_from_xml(self, epg_ids: list[str]) -> dict:
        """Get current program for EPG IDs by parsing the raw XMLTV file."""
        if not epg_ids:
            return {}

        now = datetime.now(timezone.utc)
        try:
            xml_string = await self._api_request("GET", f"{self.base_url}/output/epg", is_json=False)
            root = ET.fromstring(xml_string)
            
            current_programs = {}
            for program in root.findall(".//programme"):
                channel_id = program.get("channel")
                if channel_id in epg_ids and channel_id not in current_programs:
                    start_str = program.get("start")
                    stop_str = program.get("stop")
                    if start_str and stop_str:
                        try:
                            start_time = datetime.strptime(start_str, "%Y%m%d%H%M%S %z")
                            stop_time = datetime.strptime(stop_str, "%Y%m%d%H%M%S %z")
                            if start_time <= now < stop_time:
                                current_programs[channel_id] = {
                                    "title": program.findtext("title"),
                                    "description": program.findtext("desc"),
                                    "start_time": start_time.isoformat(),
                                    "end_time": stop_time.isoformat(),
                                }
                        except (ValueError, TypeError):
                            _LOGGER.debug("Could not parse timestamp for program: %s", program.findtext("title"))
            return current_programs
        except Exception as e:
            _LOGGER.error("Failed to parse EPG XML file: %s", e)
            return {}

    async def _async_update_data(self):
        """Update data via library, enriching with logo and EPG info."""
        status_data = await self._api_request("GET", f"{self.base_url}/proxy/ts/status")
        active_streams = status_data.get("channels", [])
        if not active_streams:
            return {}
            
        active_epg_ids = list(set([
            details['tvg_id']
            for stream in active_streams
            if (details := self.channel_details.get(stream['channel_id'])) and details.get('tvg_id')
        ]))
        
        current_programs_map = await self._get_current_programs_from_xml(active_epg_ids)

        enriched_streams = {}
        for stream in active_streams:
            stream_id = stream['channel_id']
            enriched_stream = stream.copy()
            details = self.channel_details.get(stream_id)
            if details:
                if logo_id := details.get("logo_id"):
                    enriched_stream["logo_url"] = f"{self.base_url}/api/channels/logos/{logo_id}/cache/"
                if epg_id := details.get("tvg_id"):
                    enriched_stream["program"] = current_programs_map.get(epg_id)
            enriched_streams[stream_id] = enriched_stream
        return enriched_streams

class DispatcharrStreamManager:
    """Manages the creation and removal of stream sensors."""
    def __init__(self, coordinator: DispatcharrDataUpdateCoordinator, async_add_entities: AddEntitiesCallback):
        self._coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._known_stream_ids = set()
        self._coordinator.async_add_listener(self._update_sensors)
        self._update_sensors()

    @callback
    def _update_sensors(self) -> None:
        """Update, add, or remove sensors based on coordinator data."""
        if not isinstance(self._coordinator.data, dict):
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
        # --- FIX: Removed premature call to _handle_coordinator_update ---

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
        
        stream_data = self.coordinator.data.get(self._stream_id, {})
        name = stream_data.get("stream_name", f"Stream {self._stream_id[-6:]}")
        
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._stream_id}"
        self._attr_icon = "mdi:television-stream"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.config_entry.entry_id)}, name="Dispatcharr")

    @property
    def available(self) -> bool:
        """Return True if the stream is still in the coordinator's data."""
        return super().available and self._stream_id in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.available:
            self.async_write_ha_state()
            return
            
        stream_data = self.coordinator.data[self._stream_id]
        program_data = stream_data.get("program") or {}
        
        self._attr_native_value = "Streaming"
        self._attr_entity_picture = stream_data.get("logo_url")
        self._attr_extra_state_attributes = {
            "channel_number": stream_data.get("stream_id"),
            "channel_name": stream_data.get("stream_name"),
            "logo_url": stream_data.get("logo_url"),
            "clients": stream_data.get("client_count"),
            "resolution": stream_data.get("resolution"),
            "fps": stream_data.get("source_fps"),
            "video_codec": stream_data.get("video_codec"),
            "audio_codec": stream_data.get("audio_codec"),
            "avg_bitrate": stream_data.get("avg_bitrate"),
            "program_title": program_data.get("title"),
            "program_description": program_data.get("description"),
            "program_start": program_data.get("start_time"),
            "program_stop": program_data.get("end_time"),
        }
        self.async_write_ha_state()