#!/bin/bash

echo "🚀 Iniciando Humm Campaigns..."

# Activar entorno virtual
source venv/bin/activate

# Matar cualquier proceso de Celery que haya quedado huérfano
pkill -f "celery -A config worker"

# Iniciar Celery en segundo plano y guardar logs en celery.log
echo "📦 Iniciando trabajador de correos en segundo plano (Celery)..."
celery -A config worker --loglevel=info > celery.log 2>&1 &

echo "✅ Trabajador de correos iniciado."
echo "🌐 Levantando servidor web..."
echo "👉 Abre http://localhost:8000 en tu navegador"
echo "Para detener todo, presiona Control + C"

# Iniciar Django (queda en primer plano)
python manage.py runserver

# Cuando el usuario presione Ctrl+C y Django se detenga, detenemos también a Celery
pkill -f "celery -A config worker"
echo "🛑 Servidor y trabajador de correos detenidos."
