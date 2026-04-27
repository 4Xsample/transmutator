#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$ROOT_DIR/venv/bin/python"
FRONTEND_DIR="$ROOT_DIR/Pipboy-Transfer"
FRONTEND_BUILD="$FRONTEND_DIR/dist/public/index.html"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Error: no existeix $VENV_PYTHON"
  echo "Executa primer: ./setup_venv.sh"
  exit 1
fi

if [ ! -f "$FRONTEND_BUILD" ]; then
  echo "Error: el frontend web encara no està buildat."
  echo "Executa:"
  echo "  cd $FRONTEND_DIR"
  echo "  npm install"
  echo "  npm run build"
  exit 1
fi

cd "$ROOT_DIR"
exec "$VENV_PYTHON" -m src.web_server
