# Sensord
The distribution package consists of two main components:

**Sensor Service:**
- Executable: `sensord`
- Manages IoT devices and sensors.
- Runs as a background process.
- Handles communication and data processing for connected sensors.

**Sensor Control CLI:**
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
### Sensors Configuration
The service requires `sensors.toml` config file to be available on XDG config path in `sensord` directory.
- For given user it is usually: `~/.config/sensord`
- To access the config globally: `/etc/xdg/sensord`
