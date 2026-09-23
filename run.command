#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "  The environment is missing. Run ./install.command first."
  read -r _; exit 1
fi
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
".venv/bin/python" -m qwenstudio.app
