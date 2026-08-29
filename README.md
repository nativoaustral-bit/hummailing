# 🚀 Hummailing — Una herramienta de Humm

**Hummailing** es una plataforma SaaS de email marketing y captación de clientes multi-tenant desarrollada por **Humm** para apoyar a emprendedores y empresas en la ejecución y optimización de sus campañas de comunicación.

---

## ✨ Características Principales

* 🏢 **Arquitectura Multi-Tenant:** Aislamiento total de bases de datos, contactos, etiquetas y campañas por cliente/organización con límites asignables.
* 👑 **Panel de Administración Master Humm:** Gestión de clientes (activar/suspender, límites, reseteo de contraseñas), auditoría y comunicados oficiales masivos.
* 🎨 **Editor Visual de Campañas por Bloques:**
  * Configuración previa de paletas cromáticas armónicas y contrastes automáticos.
  * Subida de logotipos e imágenes optimizadas (máx. 200 KB) con reescalado automático via Pillow.
  * Bloques interactivos: Header institucional, Título, Texto, Imagen, Botón CTA y Footer con desuscripción.
* 🎯 **Módulo de Oportunidades & Pipeline:** Conversión automática de clics en leads calificados.
* 📊 **Importador Inteligente de Audiencias:** Carga masiva mediante archivos Excel/CSV con mapeo automático de campos.
* ⚡ **Motor de Envíos Asíncronos:** Celery 5.x + Broker Redis + API de Resend para despachos de alta velocidad.

---

## 🛠️ Requisitos del Sistema

* **Python:** 3.10+
* **Redis Server:** Activo en `localhost:6379` (para colas de envío Celery)
* **API Key de Resend:** Con dominio verificado (ej. `humm.cl`)

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio y configurar el entorno virtual

```bash
git clone <URL_DEL_REPOSITORIO_GITHUB>
cd CAMPAIGNS

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Variables de Entorno

Copia el archivo `.env.example` a `.env` y configura tus credenciales:

```bash
cp .env.example .env
```

### 3. Migraciones y Datos Iniciales

```bash
python manage.py migrate
python create_demo_data.py
```

### 4. Iniciar los Servicios

Puedes iniciar todo con el script automático:

```bash
./start.sh
```

O iniciar cada servicio por separado:

```bash
# Terminal 1: Servidor Django
python manage.py runserver

# Terminal 2: Worker de Celery
celery -A config worker -l info
```

---

## 🔑 Credenciales por Defecto (Entorno de Desarrollo)

* **Administrador Master Humm:**
  * Usuario: `admin` | Contraseña: `adminpassword123`
* **Cliente Corporativo (Tech Solutions):**
  * Usuario: `tech_admin` | Contraseña: `techpassword123`
* **Cliente Emprendedor (Green Energy):**
  * Usuario: `green_admin` | Contraseña: `greenpassword123`

---

## 📄 Licencia

Desarrollado con dedicación para el ecosistema de **Humm**.
