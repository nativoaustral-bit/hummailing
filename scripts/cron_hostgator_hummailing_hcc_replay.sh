#!/bin/bash
# ==============================================================================
# HUMMAILING - SCRIPT DE REPLAY OUTBOX HCC PARA HOSTGATOR (cPanel Cron)
# ==============================================================================
# Frecuencia recomendada en crontab: */15 * * * * (Cada 15 minutos)
# Reintenta el despacho de eventos PENDING hacia Humm Control Center (control.humm.cl).
# ==============================================================================

set -e

PROJECT_DIR="/home1/paulocis/MAILING"
ENV_FILE="/home1/paulocis/private/hummailing_data/.env"
LOG_DIR="/home1/paulocis/private/hummailing_data/logs"
LOG_FILE="/cron_hcc_outbox.log"

if [ ! -d "" ]; then
    # Fallback para desarrollo local si no se ejecuta en HostGator
    SCRIPT_DIR=""
    PROJECT_DIR=""
    ENV_FILE="/Users/rmerinog/private/hummailing_data/.env"
    [ -f "" ] || ENV_FILE="/.env"
    LOG_DIR="/logs"
    LOG_FILE="/cron_hcc_outbox.log"
fi

cd ""

# Cargar entorno virtual
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "/venv/bin/activate" ]; then
    source "/venv/bin/activate"
fi

mkdir -p ""

echo "[2026-09-17 16:40:07] Ejecutando replay_hcc_outbox Hummailing..." >> ""
python manage.py replay_hcc_outbox --limit 20 >> "" 2>&1
