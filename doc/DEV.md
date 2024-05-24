# DEV notes
## Copy project to raspberry
`rsync -avz --delete -e ssh --exclude '.git' --exclude '.idea' --exclude venv . pi@raspberrypi.local:/home/pi/dfrobot-sen0395`

## Install on raspberry in editable mode
`flit install --user --symlink`

## To fix
```
[13:11:22] WARNING  [command_failed] sensor=[sen0395/desk] command=[sensorStop] params=[()] failure=[CommandFailure.NO_COMMAND_CONFIRMATION] outputs=[[$JYBSS,0, , , *,
                    sensorStop, Done]]
```
