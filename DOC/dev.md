# DEV notes
## Copy project to raspberry
`rsync -avz --delete -e ssh --exclude '.git' --exclude '.idea' --exclude venv . pi@raspberrypi.local:/home/pi/dfrobot-sen0395`

## Install on raspberry in editable mode
`flit install --user --symlink`

## Publish
```commandline
export FLIT_USERNAME=__token__
export FLIT_PASSWORD=
flit publish
```

## Raspberry OS Installation
### Install/upgrade/uninstall with pipx (with pip 20.3.4 from (python 3.9))
```commandline
sudo pip install --system pipx
sudo pipx --global install synaps
sudo pipx --global upgrade synaps
sudo pipx --global uninstall synaps
```

### Install with pipx globally (newest pip version (python 3.11))
```commandline
sudo python3 -m pip install --break-system-packages pipx  # Then logout/login
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install synaps
```
`Note: Use Debian repo pipx when upgraded to a newer version`
