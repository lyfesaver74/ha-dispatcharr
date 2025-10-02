# Dispatcharr Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

This is a custom integration for [Home Assistant](https://www.home-assistant.io/) that connects to your [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) instance. It provides real-time monitoring of active streams, creating dynamic sensors for each stream and a summary sensor for the total count.

## Features

* **Total Stream Count:** A dedicated sensor (`sensor.dispatcharr_total_active_streams`) that shows the total number of currently active streams.

* **Dynamic Stream Sensors:** Creates a new sensor entity for each active stream automatically. These sensors are removed automatically when the stream stops, keeping your Home Assistant instance clean.

* **Rich Stream Data:** Each stream sensor provides detailed attributes, including:

  * Channel Name and Number

  * Channel Logo URL

  * Client Count

  * Video Resolution, FPS, and Codec

  * Audio Codec

  * Average Bitrate

* **Live Program Information:** The integration parses your EPG data to display the currently airing program's title, description, start time, and stop time for each active stream.

## Prerequisites

* A running instance of [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr).

* [Home Assistant Community Store (HACS)](https://hacs.xyz/) installed on your Home Assistant instance.

* The username and password for your Dispatcharr user account.

## Installation via HACS

This integration is not yet in the default HACS repository. You can add it as a custom repository.

1. In Home Assistant, go to **HACS** > **Integrations**.

2. Click the three dots in the top-right corner and select **"Custom repositories"**.

3. In the "Repository" field, enter the URL to this GitHub repository: `https://github.com/lyfesaver74/ha-dispatcharr`

4. For the "Category" dropdown, select **"Integration"**.

5. Click **"Add"**.

6. You should now see the "Dispatcharr Sessions Sensor" in your HACS integrations list. Click **"Install"** and proceed with the installation.

7. Restart Home Assistant when prompted.

## Configuration

Once the integration is installed, you can add it to Home Assistant via the UI.

1. Go to **Settings** > **Devices & Services**.

2. Click the **"+ Add Integration"** button in the bottom right.

3. Search for **"Dispatcharr"** and select it.

4. A configuration dialog will appear. Enter the following information:

   * **Host:** The IP address of your Dispatcharr server (e.g., `192.168.0.121`).

   * **Port:** The port your Dispatcharr server is running on (default is `9191`).

   * **Username:** Your Dispatcharr username.

   * **Password:** Your Dispatcharr password.

5. Click **"Submit"**. The integration will be set up and your sensors will be created.

## Provided Sensors

The integration will create the following entities:

* **`sensor.dispatcharr_total_active_streams`**: A sensor that always exists and shows the total number of active streams. Its state is a number (e.g., `0`, `1`, `2`).

* **`sensor.dispatcharr_stream_<channel_name>`** (Dynamic): A new sensor will be created for each active stream. The entity ID is based on the channel name. For example, a stream of "BBC America" might create `sensor.dispatcharr_stream_us_bbc_america_hd`.

  * The state of these sensors is either `Streaming` (when active) or `Idle` (if it persists briefly after stopping).

  * These sensors will be removed automatically when no longer active.

### Stream Sensor Attributes

Each dynamic stream sensor will have the following attributes:

| Attribute | Description | Example | 
|---|---|---|
| `channel_number` | The stream's channel number or ID. | `98209` | 
| `channel_name` | The friendly name of the channel. | `US| BBC America ᴴᴰ` | 
| `logo_url` | A direct URL to the channel's logo image. | `http://.../api/channels/logos/262/cache/` | 
| `clients` | The number of clients watching this stream. | `1` | 
| `resolution` | The current video resolution. | `1280x720` | 
| `fps` | The current frames per second. | `59.94` | 
| `video_codec` | The video codec being used. | `h264` | 
| `audio_codec` | The audio codec being used. | `aac` | 
| `avg_bitrate` | The average bitrate of the stream. | `4.11 Mbps` | 
| `program_title` | The title of the currently airing program. | `Doctor Who` | 
| `program_description` | A description of the current program. | `The Doctor travels through time...` | 
| `program_start` | The start time of the current program. | `2025-10-02T14:00:00-05:00` | 
| `program_stop` | The end time of the current program. | `2025-10-02T15:00:00-05:00` | 

## Troubleshooting

* **Program Data is `null`:** If your stream sensors are created but the `program_title`, `program_description`, etc., are `null`, it means the integration was unable to find matching guide data for that specific channel in your Dispatcharr EPG file. Please ensure that the channel has EPG data assigned within the Dispatcharr UI and that your EPG source has been recently refreshed.

* **Authentication Errors:** If you receive errors after setup, double-check that your Dispatcharr username and password are correct.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
```


