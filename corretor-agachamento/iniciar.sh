#!/usr/bin/env bash
# Corretor de Agachamento - inicia o app no Linux ou macOS:  ./iniciar.sh
set -e
cd "$(dirname "$0")"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python não encontrado. Instale o Python 3.10 ou mais recente." >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Criando ambiente virtual..."
  "$PY" -m venv .venv
fi

if [ ! -f .venv/instalado.ok ]; then
  echo "Instalando dependências (só na primeira vez)..."
  .venv/bin/python -m pip install --upgrade pip -q
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/instalado.ok
fi

echo
echo "Abrindo o Corretor de Agachamento no navegador... (Ctrl+C para encerrar)"
exec .venv/bin/python app.py "$@"
