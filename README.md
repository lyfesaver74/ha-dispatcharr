# Dispatcharr Integration for Home Assistant

This is a custom integration for Home Assistant that monitors active streams from a Dispatcharr server. It provides sensors to track the total number of streams and detailed information for each individual stream.

## Features

-   Provides a sensor showing the total number of active streams (`sensor.total_active_streams`).
-   Dynamically creates a unique sensor for each active stream, which is automatically removed when the stream stops.
-   Pulls detailed Electronic Program Guide (EPG) information for each active stream, including:
    -   Program Title
    -   Episode Title (Subtitle)
    -   Episode Number
    -   Description
    -   Start and End times
-   Displays stream-specific details like client count, resolution, codecs, and bitrate as sensor attributes.

## Installation and Configuration

### Installation

1.  Copy the `dispatcharr_sensor` directory into your Home Assistant `<config>/custom_components/` directory.
2.  Restart Home Assistant.

### Configuration

Configuration is done via the UI.

1.  Go to **Settings** > **Devices & Services**.
2.  Click the **Add Integration** button in the bottom right.
3.  Search for "Dispatcharr" and select it.
4.  In the configuration dialog, enter the required information:
    -   **Host:** The IP address of your Dispatcharr server (e.g., `192.168.0.121`).
    -   **Port:** The port your Dispatcharr server is running on (e.g., `9191`).
    -   **Username:** Your Dispatcharr username.
    -   **Password:** Your Dispatcharr password.

## Sensors Provided

### Total Active Streams Sensor

A single sensor that provides a numeric count of the total active streams.

-   **Entity ID:** `sensor.total_active_streams`
-   **State:** A number representing the count of active streams (e.g., `2`).

### Individual Stream Sensors

These sensors are created on-the-fly when a stream starts and are removed when it stops.

-   **Entity ID:** Will be generated based on the channel name, like `sensor.dispatcharr_amc`.
-   **State:** "Streaming"
-   **Attributes:**
    -   `channel_number`: The channel number from the EPG guide (e.g., `102`).
    -   `channel_name`: The display name of the channel (e.g., `AMC`).
    -   `program_title`: The title of the currently airing program.
    -   `episode_title`: The title of the specific episode, if available.
    -   `episode_number`: The season/episode number (e.g., `S1E18`), if available.
    -   `program_description`: The description of the current program.
    -   `program_start`: The start time of the current program (ISO format).
    -   `program_stop`: The end time of the current program (ISO format).
    -   `clients`: The number of clients watching the stream.
    -   `resolution`: The resolution of the stream (e.g., `1280x720`).
    -   `fps`: The frame rate of the stream.
    -   `video_codec`: The video codec being used.
    -   `audio_codec`: The audio codec being used.
    -   `avg_bitrate`: The average bitrate of the stream.

## Example Lovelace Card

You can use a Markdown card in your Home Assistant dashboard to display a clean summary of all active streams.

```yaml
type: markdown
title: Active Dispatcharr Streams
content: |
  {% for stream in states.sensor | selectattr('attributes.channel_name', 'defined') | selectattr('entity_id', 'search', 'dispatcharr_') %}
    **{{ stream.attributes.channel_name }} ({{ stream.attributes.channel_number }})**
    *Now Playing:* {{ stream.attributes.program_title }}
    {% if stream.attributes.episode_title %}
      *Episode:* {{ stream.attributes.episode_title }} ({{ stream.attributes.episode_number }})
    {% endif %}
    *Clients:* {{ stream.attributes.clients }} | *Resolution:* {{ stream.attributes.resolution }}
    ***
  {% else %}
    No active streams.
  {% endfor %}
