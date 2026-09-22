#!/bin/bash
cd /d/QwenStudio
for c in "actual" "TE int8" "TE nf4"; do
  ./.venv/Scripts/python.exe -u bench.py "$c" >> bench_resultados.txt 2>&1
  sleep 5
done
echo "TODOS LISTOS" >> bench_resultados.txt
