#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "  The environment is missing. Run ./install.command first."
  read -r _; exit 1
fi
".venv/bin/python" -m qwenstudio.app
