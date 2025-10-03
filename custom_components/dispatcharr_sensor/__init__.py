"""The Dispatcharr integration."""
import logging
from datetime import timedelta, datetime, timezone
import xml.etree.ElementTree as ET
import re
import json

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dispatcharr from a config entry."""
    coordinator = DispatcharrDataUpdateCoordinator(hass, entry)

    # Perform initial data population. This will raise ConfigEntryNotReady on failure.
    await coordinator.async_populate_channel_details()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

class DispatcharrDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages fetching and coordinating Dispatcharr data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize."""
        self.config_entry = config_entry
        self.websession = async_get_clientsession(hass)
        self._access_token: str | None = None
        self.channel_details: dict = {}

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    @property
    def base_url(self) -> str:
        """Get the base URL for API calls."""
        data = self.config_entry.data
        protocol = "https" if data.get("ssl", False) else "http"
        return f"{protocol}://{data['host']}:{data['port']}"

    async def _get_new_token(self) -> None:
        """Get a new access token using username and password."""
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
                if not self._access_token:
                    raise ConfigEntryNotReady("Authentication successful, but no access token received.")
                _LOGGER.info("Successfully authenticated with Dispatcharr")
        except aiohttp.ClientError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryNotReady(f"Authentication failed: {err}") from err

    async def _api_request(self, method: str, url: str, is_json: bool = True, **kwargs):
        """Make an authenticated API request, with token refresh."""
        if not self._access_token:
            await self._get_new_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        
        try:
            response = await self.websession.request(method, url, headers=headers, **kwargs)
            if response.status == 401:
                _LOGGER.info("Access token expired or invalid, requesting a new one.")
                await self._get_new_token()
                headers["Authorization"] = f"Bearer {self._access_token}"
                response = await self.websession.request(method, url, headers=headers, **kwargs)

            response.raise_for_status()
            return await response.json() if is_json else await response.text()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"API request to {url} failed: {err}") from err

    async def async_populate_channel_details(self):
        """Fetch all channel details to build a lookup map."""
        _LOGGER.info("Populating Dispatcharr channel details")
        try:
            all_channels = await self._api_request("GET", f"{self.base_url}/api/channels/channels/")
            if isinstance(all_channels, list):
                self.channel_details = {
                    channel['uuid']: channel for channel in all_channels if 'uuid' in channel
                }
            else:
                _LOGGER.warning("Expected a list of channels, but received: %s", type(all_channels))
                self.channel_details = {}
            _LOGGER.debug("Found %d channels", len(self.channel_details))
        except Exception as e:
            _LOGGER.error("Could not populate channel details: %s", e)
            raise ConfigEntryNotReady(f"Could not fetch channel details: {e}") from e

    async def _get_current_programs_from_xml(self, numeric_channel_ids: list[str]) -> dict:
        """Get current program for EPG IDs by parsing the raw XMLTV file."""
        if not numeric_channel_ids:
            return {}

        now = datetime.now(timezone.utc)
        try:
            xml_string = await self._api_request("GET", f"{self.base_url}/output/epg", is_json=False)
            root = ET.fromstring(xml_string)
            
            found_programs, channels_to_find = {}, set(numeric_channel_ids)
            for program in root.iterfind("programme"):
                if not channels_to_find: break
                channel_id_str = program.get("channel")
                if channel_id_str in channels_to_find:
                    start_str, stop_str = program.get("start"), program.get("stop")
                    if start_str and stop_str:
                        try:
                            start_time = datetime.strptime(start_str, "%Y%m%d%H%M%S %z")
                            stop_time = datetime.strptime(stop_str, "%Y%m%d%H%M%S %z")
                            if start_time <= now < stop_time:
                                episode_num_tag = program.find("episode-num[@system='onscreen']")
                                found_programs[channel_id_str] = {
                                    "title": program.findtext("title"),
                                    "description": program.findtext("desc"),
                                    "start_time": start_time.isoformat(),
                                    "end_time": stop_time.isoformat(),
                                    "subtitle": program.findtext("sub-title"),
                                    "episode_num": episode_num_tag.text if episode_num_tag is not None else None,
                                }
                                channels_to_find.remove(channel_id_str)
                        except (ValueError, TypeError): continue
            return found_programs
        except (UpdateFailed, ET.ParseError) as e:
            _LOGGER.warning("Could not get or parse EPG XML file, program info will be unavailable: %s", e)
        return {}

    async def _async_update_data(self):
        """Update data via authenticated API calls."""
        status_data = await self._api_request("GET", f"{self.base_url}/proxy/ts/status")
        active_streams = status_data.get("channels", [])
        if not active_streams: return {}
            
        current_programs_map = {}
        if self.config_entry.options.get("enable_epg", True):
            active_numeric_ids = list(set([
                str(int(details['channel_number']))
                for stream in active_streams
                if (details := self.channel_details.get(stream['channel_id'])) and details.get('channel_number') is not None
            ]))
            if active_numeric_ids:
                current_programs_map = await self._get_current_programs_from_xml(active_numeric_ids)

        enriched_streams = {}
        for stream in active_streams:
            stream_uuid = stream['channel_id']
            enriched_stream = stream.copy()
            details = self.channel_details.get(stream_uuid)
            if details:
                if logo_id := details.get("logo_id"):
                    enriched_stream["logo_url"] = f"{self.base_url}/api/channels/logos/{logo_id}/cache/"
                if numeric_id_float := details.get("channel_number"):
                    numeric_id_str = str(int(numeric_id_float))
                    enriched_stream["program"] = current_programs_map.get(numeric_id_str)
            enriched_streams[stream_uuid] = enriched_stream
        return enriched_streams
