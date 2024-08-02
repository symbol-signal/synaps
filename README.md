# Sensord
The distribution package consists of two main components.

**Sensor Service**
- Executable: `sensord`
- Manages IoT devices and sensors using the [Sensation library](https://github.com/symbol-signal/sensation).
- Runs as a background process.
- Handles communication and data processing for connected sensors.
- Sends sensor data and events to external systems according to configured endpoints (MQTT, etc.)

**Sensor Control CLI**
- Executable: `sensorctl`
- Provides a command-line tool for controlling and interacting with the Sensor Service.
- Allows users to start, stop, configure, and monitor sensors through the command line.
- Offers a convenient way to manage the Sensor Service and connected devices.

## Table of Contents
- [Installation](#installation)
  - [Installing for a given user](#installing-for-a-given-user)
  - [Installing system-wide](#installing-system-wide)
- [Sensord service](#sensord-service)
  - [Configuration Directory](#configuration-directory)
  - [Sensors](#sensors)
    - [Configuration](#configuration)
    - [SEN0395](#sen0395)
      - [Mandatory fields](#mandatory-fields)
      - [Optional fields](#optional-fields)
      - [Section [[sensor.mqtt]]](#section-sensormqtt-optional)
      - [Section [[sensor.ws]]](#section-sensorws-optional)
  - [MQTT](#mqtt)
    - [Broker Configuration](#broker-configuration)
    - [Payload](#payload)
    - [Sensor Configuration](#sensor-configuration)
  - [WebSocket](#websocket)
    - [Endpoint Configuration](#endpoint-configuration)
    - [Payload](#payload-1)
    - [Sensor Configuration](#sensor-configuration-1)
  - [Systemd](#systemd)
- [Sensor Control CLI](#sensor-control-cli)
  - [Subcommands](#subcommands)
    - [SEN0395](#sen0395-1)

## Installation
The recommended way of installing this service is using [pipx](https://pipx.pypa.io/stable/), 
since this is a Python application. See [this manual](https://pipx.pypa.io/stable/installation/) about how to install
pipx if it is not already on your system.

### Installing for a given user
```commandline
pipx install sensord
```

### Installing system-wide
If your pipx is installed system-wide, you can also install this service globally.
```commandline
sudo pipx --global install sensord
```
This makes `sensord` available for all users in the system, which can be convenient, for example, if you plan to
run it as a systemd service by a dedicated user.

## Sensord service
Execute by: `sensord` command or run [as a systemd service](#systemd)
> Never run more than one instance of the service at the same time. Especially, do not run simultaneously 
> under a super user and a normal user.

### Configuration Directory
All service configuration files must be placed in the `sensord` directory located in one of the configuration paths 
according to the [XDG specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html):
- For a given user: `~/.config/sensord` or `$XDG_CONFIG_HOME/sensord`
- For all users: `/etc/xdg/sensord` or `/etc/sensord`

### Sensors
#### Configuration
All sensors are configured in the configuration file `sensors.toml` which must be placed in the configuration directory. 
See the [example configuration file](examples/sensors.toml).

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

### MQTT
#### Broker Configuration
Presence change events of a sensor can be sent as an MQTT message to an MQTT broker. For this, a broker must first be
defined in the `mqtt.toml` configuration file. See the [example configuration file](examples/mqtt.toml).

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
For this, an endpoint must first be defined in the `ws.toml` configuration file. See the [example configuration file](examples/ws.toml).

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
sudo useradd -r -s /usr/sbin/nologin sensord
sudo usermod -a -G dialout sensord
```
**Note:** *`dialout` group is required for reading serial port on Raspberry Pi OS*

Create the service file `/etc/systemd/system/sensord.service`:
```
[Unit]
Description=Sensor Daemon Service
After=network.target

[Service]
ExecStart=/usr/local/bin/sensord --log-file-level off
Restart=always
User=sensord
Group=sensord

[Install]
WantedBy=multi-user.target
```
**Note:** *You can remove the `--log-file-level off` option if you want to log to `/var/log/sensord`. 
However, you need to set the corresponding permissions for the user.*

Active and start the service:
```commandline
sudo systemctl daemon-reload
sudo systemctl enable sensord.service
sudo systemctl start sensord.service
```
To manually debug, you can run the service as `sensord` user:
```commandline
sudo -u sensord /usr/local/bin/sensord
```
To read the service logs in the journal:
```commandline
 journalctl -u sensord
```

## Sensor Control CLI
Execute `sensorctl --help` to see the available commands. This CLI utility communicates with the `sensord` service.
The service must be running when a command is executed.

**Note:** *If the service runs under a different user than the one executing `sensorctl`, then the current user must be added
to the same group as the primary group of the service user. For example, if the service runs as the `sensord` user
with the `sensord` group, then add the current user to the same group:*
```commandline
sudo usermod -a -G sensord $USER
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
