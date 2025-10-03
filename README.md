# Dispatcharr Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

This is a custom integration for [Home Assistant](https://www.home-assistant.io/) that connects to your [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) instance. It provides real-time monitoring of active streams, creating dynamic media player entities for each stream and a summary sensor for the total count.

## Features

* **Total Stream Count:** A dedicated sensor (`sensor.dispatcharr_total_active_streams`) that shows the total number of currently active streams.
* **Dynamic Media Player Entities:** Creates a new media player entity for each active stream automatically. These entities are removed when the stream stops, keeping your Home Assistant instance clean.
* **Rich Stream Data:** Each media player provides detailed attributes, including channel name, client count, video/audio codecs, and more.
* **Live Program Information (Optional):** Parses your EPG data to display the currently airing program's title, description, and times as media player attributes. This feature can be disabled for performance.

## Prerequisites

* An understanding and acceptance that AI helped me make this. If that is not your thang... don't use it.
* A running instance of [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr).
* [Home Assistant Community Store (HACS)](https://hacs.xyz/) installed on your Home Assistant instance.
* The username and password for your Dispatcharr user account.

## Installation via HACS

This integration is not yet in the default HACS repository. You can add it as a custom repository.

1.  In Home Assistant, go to **HACS** > **Integrations**.
2.  Click the three dots in the top-right corner and select **"Custom repositories"**.
3.  In the "Repository" field, enter the URL to this GitHub repository: `https://github.com/lyfesaver74/ha-dispatcharr`
4.  For the "Category" dropdown, select **"Integration"**.
5.  Click **"Add"**.
6.  You should now see the "Dispatcharr Integration" in your HACS integrations list. Click **"Install"** and proceed with the installation.
7.  Restart Home Assistant when prompted.

## Configuration

Once the integration is installed, you can add it to Home Assistant via the UI.

1.  Go to **Settings** > **Devices & Services**.
2.  Click the **"+ Add Integration"** button in the bottom right.
3.  Search for **"Dispatcharr"** and select it.
4.  A configuration dialog will appear. Enter the following information:
    * **Host:** The IP address of your Dispatcharr server (e.g., `192.168.0.121`).
    * **Port:** The port your Dispatcharr server is running on (default is `9191`).
    * **Username:** Your Dispatcharr username.
    * **Password:** Your Dispatcharr password.
5.  Click **"Submit"**. The integration will be set up and your entities will be created.

## Optional Configuration (After Installation)

The EPG data feature can be turned on or off at any time without re-installing the integration. This is useful for performance tuning on slower servers.

1.  Go to **Settings** > **Devices & Services**.
2.  Find the Dispatcharr integration and click **"Configure"**.
3.  Check or uncheck the **"Enable EPG Data"** option.
4.  Click **"Submit"**. The integration will automatically reload with the new setting.

## Provided Entities

The integration will create the following entities:

* **`sensor.dispatcharr_total_active_streams`**: A sensor that always exists and shows the total number of active streams. Its state is a number (e.g., `0`, `1`, `2`).
* **`media_player.dispatcharr_<channel_name>`** (Dynamic): A new media player entity will be created for each active stream. The entity ID is based on the channel name.
    * The state will be `playing` when active.
    * These entities will be removed automatically when no longer active.

### Media Player Attributes

Each dynamic media player entity will have the following attributes:

| Attribute | Description | Example |
|---|---|---|
| `media_title` | The title of the currently airing program. | `Doctor Who` |
| `media_series_title` | The friendly name of the channel. | `US: BBC AMERICA HD` |
| `media_content_id` | The stream's internal channel number/ID. | `98209` |
| `app_name` | The source of the stream. | `Dispatcharr` |
| `entity_picture` | A direct URL to the channel's logo image. | `http://.../logos/262/cache/` |
| `clients` | The number of clients watching this stream. | `1` |
| `resolution` | The current video resolution. | `1280x720` |
| `fps` | The current frames per second. | `59.94` |
| `video_codec` | The video codec being used. | `h264` |
| `audio_codec` | The audio codec being used. | `aac` |
| `avg_bitrate` | The average bitrate of the stream. | `4.11 Mbps` |
| `program_description` | A description of the current program. | `The Doctor travels through time...` |
| `program_start` | The start time of the current program. | `2025-10-02T14:00:00-05:00` |
| `program_stop` | The end time of the current program. | `2025-10-02T15:00:00-05:00` |

## Troubleshooting

* **Program Data is `null`:** If the `media_title` and other program attributes are `null` (and the EPG option is enabled), it means the integration was unable to find matching guide data for that specific channel in your Dispatcharr EPG file. Please ensure that the channel has EPG data assigned within the Dispatcharr UI and that your EPG source has been recently refreshed.
* **Authentication Errors:** If you receive errors after setup, double-check that your Dispatcharr username and password are correct.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

