#!/bin/bash
set -e

echo "🚀 Iniciando despliegue de Hummailing a GitHub y Servidor Producción..."

# 1. Enviar cambios locales a GitHub
echo "📦 Enviando cambios a GitHub (nativoaustral-bit/hummailing)..."
git push origin main

# 2. Sincronizar archivos al servidor de producción HostGator (solo código de producción)
echo "🌐 Actualizando servidor de producción (HostGator)..."
rsync -avz \
    --exclude='venv' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='celery.log' \
    --exclude='*.md' \
    --exclude='*.txt' \
    --exclude='start.sh' \
    --exclude='create_demo_data.py' \
    --exclude='create_test_data.py' \
    --exclude='deploy_hostgator.sh' \
    --exclude='deploy.sh' \
    --exclude='.env.example' \
    -e "ssh" ./ humm.cl:/home1/paulocis/MAILING/

# 3. Ejecutar tareas de producción en el servidor
echo "⚡ Ejecutando migraciones, estáticos y permisos en servidor..."
ssh humm.cl "cd /home1/paulocis/MAILING && source venv/bin/activate && python manage.py migrate && python manage.py collectstatic --noinput && chmod 755 passenger_wsgi.py manage.py"

echo "✅ ¡Despliegue completado con éxito! Hummailing disponible en https://mailing.humm.cl/"
