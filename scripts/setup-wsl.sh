#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "${script_dir}/.." && pwd)"
cd "${project_dir}"

sudo apt-get update
sudo apt-get install -y build-essential gdb git pkg-config libsparsehash-dev python3 python3-venv python3-pip

python3 -m venv "${PWD}/.venv"
"${PWD}/.venv/bin/python" -m pip install --upgrade pip
"${PWD}/.venv/bin/python" -m pip install -r requirements.txt

echo "Environment ready. In VS Code, run 'Remote-WSL: Reopen Folder in WSL' and then build from Tasks."