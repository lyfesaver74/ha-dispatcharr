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
PLATFORMS = [Platform.SENSOR, Platform.MEDIA_PLAYER]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dispatcharr from a config entry."""
    coordinator = DispatcharrDataUpdateCoordinator(hass, entry)

    await coordinator.async_populate_channel_map_from_xml()
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
        self.channel_map: dict = {}

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

    async def async_populate_channel_map_from_xml(self):
        """Fetch the XML file once to build a reliable map of channels."""
        _LOGGER.info("Populating Dispatcharr channel map from XML file...")
        try:
            xml_string = await self._api_request("GET", f"{self.base_url}/output/epg", is_json=False)
        except UpdateFailed as err:
            raise ConfigEntryNotReady(f"Could not fetch EPG XML file to build channel map: {err}") from err

        try:
            root = ET.fromstring(xml_string)
            self.channel_map = {}
            for channel in root.iterfind("channel"):
                display_name = channel.findtext("display-name")
                channel_id = channel.get("id")
                icon_tag = channel.find("icon")
                icon_url = icon_tag.get("src") if icon_tag is not None else None
                
                if display_name and channel_id:
                    slug_name = slugify(display_name)
                    self.channel_map[slug_name] = {"id": channel_id, "name": display_name, "logo_url": icon_url}
            
            if not self.channel_map:
                 raise ConfigEntryNotReady("XML was fetched, but no channels could be mapped.")

            _LOGGER.info("Successfully built channel map with %d entries.", len(self.channel_map))
        except ET.ParseError as e:
            _LOGGER.error("Failed to parse XML for channel map: %s", e)
            raise ConfigEntryNotReady(f"Failed to parse XML for channel map: {e}") from e

    def _get_channel_details_from_stream_name(self, stream_name: str) -> dict | None:
        """(REWRITTEN) Match a stream name to a channel in the map, preferring the longest match."""
        if not stream_name:
            return None
        
        simple_stream_name = slugify(re.sub(r'^\w+:\s*|\s+HD$', '', stream_name, flags=re.IGNORECASE))
        _LOGGER.debug("Attempting to match simplified stream name: '%s'", simple_stream_name)

        # 1. Try for a direct, exact match first (most reliable)
        if simple_stream_name in self.channel_map:
            _LOGGER.debug("Found exact match for '%s'", simple_stream_name)
            return self.channel_map[simple_stream_name]

        # 2. If no exact match, find all possible substring matches
        possible_matches = []
        for slug_key, details in self.channel_map.items():
            if slug_key in simple_stream_name:
                possible_matches.append((slug_key, details))
        
        # 3. If any matches were found, sort them by length and return the longest one
        if possible_matches:
            _LOGGER.debug("Found possible matches: %s", [m[0] for m in possible_matches])
            # Sort by the length of the key (item[0]), descending, and return the details of the best match
            best_match = sorted(possible_matches, key=lambda item: len(item[0]), reverse=True)[0]
            _LOGGER.debug("Selected best match: '%s'", best_match[0])
            return best_match[1]
            
        _LOGGER.debug("Could not find any match for stream name: '%s'", stream_name)
        return None

    async def _async_update_data(self):
        """Update data by fetching from authenticated endpoints."""
        status_data = await self._api_request("GET", f"{self.base_url}/proxy/ts/status")
        active_streams = status_data.get("channels", [])
        if not active_streams: return {}

        xml_string = await self._api_request("GET", f"{self.base_url}/output/epg", is_json=False)
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            _LOGGER.error("Could not parse EPG XML on update: %s", e)
            return self.data

        enriched_streams = {}
        now = datetime.now(timezone.utc)

        for stream in active_streams:
            stream_uuid = stream.get("channel_id")
            stream_name = stream.get("stream_name")
            if not stream_uuid or not stream_name: continue

            details = self._get_channel_details_from_stream_name(stream_name)
            enriched_stream = stream.copy()
            
            if details:
                xmltv_id = details["id"]
                enriched_stream["xmltv_id"] = xmltv_id
                enriched_stream["channel_name"] = details["name"]
                enriched_stream["logo_url"] = details.get("logo_url")
                
                for program in root.iterfind(f".//programme[@channel='{xmltv_id}']"):
                    start_str, stop_str = program.get("start"), program.get("stop")
                    if start_str and stop_str:
                        try:
                            start_time = datetime.strptime(start_str, "%Y%m%d%H%M%S %z")
                            stop_time = datetime.strptime(stop_str, "%Y%m%d%H%M%S %z")
                            if start_time <= now < stop_time:
                                episode_num_tag = program.find("episode-num[@system='onscreen']")
                                enriched_stream["program"] = {
                                    "title": program.findtext("title"), "description": program.findtext("desc"),
                                    "start_time": start_time.isoformat(), "end_time": stop_time.isoformat(),
                                    "subtitle": program.findtext("sub-title"),
                                    "episode_num": episode_num_tag.text if episode_num_tag is not None else None,
                                }
                                break
                        except (ValueError, TypeError):
                            continue
            
            enriched_streams[stream_uuid] = enriched_stream
        
        return enriched_streams
