#!/bin/bash

VENV_PATH="/mnt/extra-addons/.venv"
ACTIVATE_LINE="source $VENV_PATH/bin/activate"

if [ -d "$VENV_PATH" ] && ! grep -Fxq "$ACTIVATE_LINE" ~/.bashrc; then
    echo "$ACTIVATE_LINE" >> ~/.bashrc
fi