#!/bin/bash
set -e

echo "=========================================================="
echo "🚀 Iniciando despliegue de Hummailing para mailing.humm.cl"
echo "=========================================================="

# 1. Crear entorno virtual
if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual Python..."
    python3 -m venv venv
fi

# 2. Activar entorno virtual
source venv/bin/activate

# 3. Instalar dependencias
echo "📥 Instalando dependencias del proyecto..."
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# 4. Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    echo "⚙️ Generando archivo .env con variables de producción..."
    SECRET_KEY_GEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    cat <<EOF > .env
DEBUG=False
SECRET_KEY=${SECRET_KEY_GEN}
ALLOWED_HOSTS=mailing.humm.cl,humm.cl,www.humm.cl,127.0.0.1,localhost
RESEND_API_KEY=\${RESEND_API_KEY:-re_your_resend_api_key_here}
EOF
fi

# 5. Ejecutar migraciones de base de datos
echo "🗄️ Ejecutando migraciones..."
python manage.py migrate

# 6. Crear datos iniciales si es primera instalación
echo "👤 Creando usuarios y organizaciones base..."
python create_demo_data.py || true

# 7. Recolectar archivos estáticos
echo "🎨 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# 8. Directorio de logs
mkdir -p logs

# 9. Iniciar Gunicorn en puerto interno 8025
echo "🔄 Iniciando servidor de aplicaciones Gunicorn en puerto 8025..."
fuser -k 8025/tcp 2>/dev/null || true
nohup gunicorn config.wsgi:application \
    --bind 127.0.0.1:8025 \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log >/dev/null 2>&1 &

echo "=========================================================="
echo "✅ ¡Hummailing desplegado y activo para mailing.humm.cl!"
echo "=========================================================="
