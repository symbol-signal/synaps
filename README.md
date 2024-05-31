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
Configuration fields to be added here...

### MQTT
#### Broker Configuration
Presence change events of a sensor can be sent as an MQTT message to an MQTT broker. For this, a broker must first be
defined in the `mqtt.toml` configuration file. See the [example configuration file](examples/mqtt.toml).

#### Payload
The schema of the MQTT message payload is defined in the [presence-mqtt-schema.json](doc/presence-mqtt-schema.json) file.
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

### Systemd
To run this service as a systemd service, follow the steps below.

*You can create a dedicated user for the service and add the user to the required groups (optional):*
```commandline
sudo useradd -r -s /usr/sbin/nologin sensord
sudo usermod -a -G dialout sensord
```
**Note**: `dialout` group is required for reading serial port on Raspberry Pi OS

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
**Note**: You can remove the `--log-file-level off` option if you want to log to `/var/log/sensord`. 
However, you need to set the corresponding permissions for the user.

Active and start the service:
```commandline
sudo systemctl daemon-reload
sudo systemctl enable sensord.service
sudo systemctl start sensord.service
```
To manually debug, you can run the service as `systemd` user:
```commandline
sudo -u sensord /usr/local/bin/sensord
```
