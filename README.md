# Synaps
Synaps is a sensor management middleware that transforms low-level device interfaces (serial, I2C, GPIO) 
into high-level communication systems (WebSockets, MQTT) and management tools (CLI). 
It acts as a middleware layer that abstracts away sensor implementation complexities, providing a unified facade 
for interacting with various IoT sensors and devices. By translating device-specific data into standardized event streams, 
Synaps enables seamless integration of physical sensors into networked applications and automation systems.

The distribution package consists of two main components:

**Synaps Service**
- Executable: `synapsd`
- Manages IoT devices and sensors utilizing the [Sensation library](https://github.com/symbol-signal/sensation).
- Runs as a background process.
- Handles communication and data processing for connected sensors.
- Sends sensor data and events to external systems according to configured endpoints (MQTT, WebSockets, etc.)
- Provides domain socket API for the CLI part

**Synaps Control CLI**
- Executable: `synaps`
- Provides a command-line tool for controlling and interacting with the Synaps Service.
- Allows users to start, stop, configure, and monitor sensors/devices through the command line.
- Offers a convenient way to manage the Synaps Service and connected devices.

## Table of Contents
- [Installation](#installation)
  - [Installing for a given user](#installing-for-a-given-user)
  - [Installing system-wide](#installing-system-wide)
- [Synaps Service](#synaps-service)
  - [Configuration Directory](#configuration-directory)
  - [Sensors](#sensors)
    - [Configuration](#configuration)
    - [SEN0395](#sen0395)
      - [Mandatory fields](#mandatory-fields)
      - [Optional fields](#optional-fields)
      - [Section [[sensor.mqtt]]](#section-sensormqtt-optional)
      - [Section [[sensor.ws]]](#section-sensorws-optional)
    - [SEN0311](#sen0311)
      - [Mandatory fields-1](#mandatory-fields-1)
      - [Optional fields-1](#optional-fields-1)
      - [Section [sensor.presence]](#section-sensorpresence-required)
      - [Section [[sensor.presence.mqtt]]](#section-sensorpresencemqtt-optional)
      - [Section [[sensor.presence.ws]]](#section-sensorpresencews-optional)
  - [MQTT](#mqtt)
    - [Broker Configuration](#broker-configuration)
    - [Payload](#payload)
    - [Sensor Configuration](#sensor-configuration)
  - [WebSocket](#websocket)
    - [Endpoint Configuration](#endpoint-configuration)
    - [Payload](#payload-1)
    - [Sensor Configuration](#sensor-configuration-1)
  - [Systemd](#systemd)
- [Synaps Control CLI](#synaps-control-cli)
  - [Subcommands](#subcommands)
    - [SEN0395](#sen0395-1)
    - [SEN0311](#sen0311-1)

## Installation
The recommended way of installing this service is using [pipx](https://pipx.pypa.io/stable/), 
since this is a Python application. See [this manual](https://pipx.pypa.io/stable/installation/) about how to install
pipx if it is not already on your system.

### Installing for a given user
```commandline
pipx install synaps
```

### Installing system-wide
If your pipx is installed system-wide, you can also install this service globally.
```commandline
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install --global synaps
```
This makes `synaps` available for all users in the system, which can be convenient, for example, if you plan to
run it as a systemd service by a dedicated user.

## Synaps Service
Execute by: `synapsd` command or run [as a systemd service](#systemd)
> Never run more than one instance of the service at the same time. Especially, do not run simultaneously 
> under a super user and a normal user.

### Configuration Directory
All service configuration files must be placed in the `synaps` directory located in one of the configuration paths 
according to the [XDG specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html):
- For a given user: `~/.config/synaps` or `$XDG_CONFIG_HOME/synaps`
- For all users: `/etc/xdg/synaps` or `/etc/synaps`

### Sensors
#### Configuration
All sensors are configured in the configuration file `sensors.toml` which must be placed in the configuration directory. 
See the [example configuration file](examples/config/sensors.toml).

##### SEN0395
###### Mandatory fields
- `type`: Specifies the type of the sensor. Must be set to `"sen0395"` for the SEN0395 sensor.
- `name`: A unique name for the sensor instance. Used for identification.
- `port`: The serial port to which the sensor is connected (e.g., `"/dev/ttyAMA0"`, `"/dev/ttyUSB0"`).

###### Optional fields
- `enabled` (default: `true`): If set to `true`, the service will start reading and processing sensor data (MQTT, presence logging, etc.).
- `autostart` (default: `true`): Specifies whether the sensor should automatically start scanning upon service startup.
- `print_presence` (default: `true`): Determines whether presence changes should be printed to stdout and logged.

###### Section [[sensor.mqtt]] (optional)
 - `broker`: The configured name of the MQTT broker to which the sensor should publish presence data.
 - `topic`: The MQTT topic under which the presence data should be published.

###### Section [[sensor.ws]] (optional)
 - `endpoint`: The configured name of the WS endpoint to which the sensor should publish presence data.

##### SEN0311
###### Mandatory fields
- `type`: Specifies the type of the sensor. Must be set to `"sen0311"` for the SEN0311 sensor.
- `name`: A unique name for the sensor instance. Used for identification.
- `port`: The serial port to which the sensor is connected (e.g., `"/dev/ttyAMA0"`, `"/dev/ttyUSB0"`).

###### Optional fields
- `enabled` (default: `true`): If set to `true`, the service will start reading and processing sensor data.
- `print_presence` (default: `true`): Determines whether presence changes should be printed to stdout and logged.

###### Section [sensor.presence] (required)
- `threshold_presence`: Distance in cm below which presence is detected.
- `threshold_absence`: Distance in cm above which absence is detected.
- `hysteresis_count` (optional, default: `1`): Number of consecutive readings required to change the presence state.
- `delay_presence` (optional, default: `0`): Delay in seconds before confirming a presence detection.
- `delay_absence` (optional, default: `0`): Delay in seconds before confirming an absence detection.

###### Section [[sensor.presence.mqtt]] (optional)
- `broker`: The configured name of the MQTT broker to which the sensor should publish presence data.
- `topic`: The MQTT topic under which the presence data should be published.

###### Section [[sensor.presence.ws]] (optional)
- `endpoint`: The configured name of the WS endpoint to which the sensor should publish presence data.

### MQTT
#### Broker Configuration
Presence change events of a sensor can be sent as an MQTT message to an MQTT broker. For this, a broker must first be
defined in the `mqtt.toml` configuration file. See the [example configuration file](examples/config/mqtt.toml).

#### Payload
The schema of the MQTT message payload is defined in the [presence-message-schema.json](DOC/presence-message-schema.json) file.
##### Example
```json
{
  "sensorId": "sen0395/desk",
  "event": "presence_change",
  "eventAt": "2024-05-30T06:25:13.929544+00:00",
  "eventData": {
    "presence": false
  }
}
```
#### Sensor Configuration
A sensor must explicitly define an MQTT broker for the notification to be sent. 
Multiple brokers can be defined to send notifications to different MQTT brokers:
```toml
[[sensor]]
# Sensor configuration is here
[[sensor.mqtt]]
broker = "local-rpi"  # Broker name defined as `broker.name` in the `mqtt.toml` file
topic = "living_room/desk/presence"  # Topic where the notification events are sent

[[sensor.mqtt]]
broker = "cloud-broker"  # Another broker name defined in the `mqtt.toml` file
topic = "sensors/living_room/desk/presence"  # Topic on the second broker
```

### WebSocket
#### Endpoint Configuration
Presence change events of a sensor can be sent as a WebSocket message to a WebSocket server.
For this, an endpoint must first be defined in the `ws.toml` configuration file. See the [example configuration file](examples/config/ws.toml).

#### Payload
The schema of the WebSocket message payload is defined in the [presence-message-schema.json](DOC/presence-message-schema.json) file.
##### Example
```json
{
  "sensorId": "sen0395/desk",
  "event": "presence_change",
  "eventAt": "2024-05-30T06:25:13.929544+00:00",
  "eventData": {
    "presence": false
  }
}
```
#### Sensor Configuration
A sensor must explicitly define a WebSocket endpoint for the notification to be sent. 
Multiple endpoints can be defined to send notifications to different WebSocket servers:
```toml
[[sensor]]
# Sensor configuration is here
[[sensor.ws]]
endpoint = "local-rpi"  # Endpoint name defined as `endpoint.name` in the `ws.toml` file

[[sensor.ws]]
endpoint = "cloud-ws"  # Another endpoint name defined in the `ws.toml` file
```

### Systemd
To run this service as a systemd service, follow the steps below.

*You can create a dedicated user for the service and add the user to the required groups (optional):*
```commandline
sudo useradd -r -s /usr/sbin/nologin synaps
sudo usermod -a -G dialout synaps
```
**Note:** *`dialout` group is required for reading serial port on Raspberry Pi OS*

Create the service file `/etc/systemd/system/synapsd.service`:
```
[Unit]
Description=Synaps Daemon Service
After=network.target

[Service]
ExecStart=/usr/local/bin/synapsd --log-file-level off
Restart=always
User=synaps
Group=synaps

[Install]
WantedBy=multi-user.target
```
**Note:** *You can remove the `--log-file-level off` option if you want to log to `/var/log/synaps`. 
However, you need to set the corresponding permissions for the user.*

Active and start the service:
```commandline
sudo systemctl daemon-reload
sudo systemctl enable synapsd.service
sudo systemctl start synapsd.service
```
To manually debug, you can run the service as `synaps` user:
```commandline
sudo -u synaps /usr/local/bin/synapsd
```
To read the service logs in the journal:
```commandline
 journalctl -u synapsd
```

## Synaps Control CLI
Execute `synaps --help` to see the available commands. This CLI utility communicates with the `synapsd` service.
The service must be running when a command is executed.

**Note:** *If the service runs under a different user than the one executing `synaps`, then the current user must be added
to the same group as the primary group of the service user. For example, if the service runs as the `synaps` user
with the `synaps` group, then add the current user to the same group:*
```commandline
sudo usermod -a -G synaps $USER
```
*After adding the user to the group, the user needs to log out and log back in for the group changes to take effect.*

### Subcommands

#### SEN0395
The sen0395 subcommand group provides commands for controlling the DFRobot mmWave presence sensor SEN0395.
All subcommands accept the following option:
- `--name NAME`: The name of the specific sensor to execute the command on. If not provided, the command is executed for all registered sensors.

`start`\
Start scanning with the SEN0395 sensor(s).

`stop`\
Stop scanning with the SEN0395 sensor(s).

`reset`\
Send a reset command to the SEN0395 sensor(s).

`latency DETECTION_DELAY DISAPPEARANCE_DELAY`\
Configure the detection and disappearance latencies for the SEN0395 sensor(s).

`detrange PARA_S PARA_E [PARB_S] [PARB_E] [PARC_S] [PARC_E] [PARD_S] [PARD_E]`\
Configure the detection range segments for the SEN0395 sensor(s).

`status`\
Print the status of the SEN0395 sensor(s).

`enable`\
Start reading and processing data from the SEN0395 sensor(s).

`disable`\
Stop reading and processing data from the SEN0395 sensor(s).

#### SEN0311
The sen0311 subcommand group provides commands for controlling the DFRobot ultrasonic distance sensor SEN0311.

`status`
Print the status of the SEN0311 sensor(s). Use the `--name` option to specify a particular sensor.

**Note**: More commands to be added...
