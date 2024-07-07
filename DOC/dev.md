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
