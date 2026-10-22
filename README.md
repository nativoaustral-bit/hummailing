# 🚀 Hummailing — Plataforma de Email Marketing & Pipeline Comercial

**Hummailing** es una plataforma SaaS multi-tenant de email marketing, automatización y captación de leads desarrollada por **Humm**, diseñada para que emprendedores y empresas gestionen, diseñen y despachen campañas profesionales de alto impacto y conviertan interacciones en oportunidades comerciales.

---

## ✨ Características Principales

* 🏢 **Arquitectura Multi-Tenant:**
  * Aislamiento estricto de contactos, etiquetas, campañas, métricas y registros de actividad por cliente/organización.
  * Límites y cuotas configurables por organización desde el panel de control.

* 👑 **Panel de Administración Master Humm:**
  * Supervisión global de organizaciones clientes (activar, suspender, gestionar cuotas y credenciales).
  * Registro de auditoría centralizado (`ActivityLog`) y comunicados oficiales.

* 📡 **Motor de Envíos Masivos con Resend Broadcasts:**
  * **Uso exclusivo de `/broadcasts`** para campañas masivas (soporta listas de marketing de hasta 1.000 contactos en plan gratuito).
  * **Sincronización automática de audiencia:** Vinculación de contactos con propiedades personalizadas (`first_name`, `company`) y asignación a segmentos dinámicos de Resend.
  * **Gestión inteligente de cuota de segmentos:** Detección de la cuota máxima (3/3) con liberación automática del segmento más antiguo antes de generar uno nuevo.
  * **Separación estricta de tráfico:** `/broadcasts` para despachos masivos y `/emails` exclusivamente para correos transaccionales (recuperación de clave, notificaciones del sistema y pruebas individuales de diseño).
  * **Idempotencia y anti-duplicados:** Registro de `broadcast_id` previo al despacho para prevenir reenvíos accidentales.

* ⚡ **Despacho Asíncrono Híbrido y Resiliente:**
  * **Modo cPanel / Phusion Passenger:** Despacho en hilos independientes en segundo plano (`threading.Thread`) con aislamiento de conexiones de base de datos cuando `CELERY_TASK_ALWAYS_EAGER = True`. La petición web responde en **< 100 ms**, eliminando bloqueos y timeouts de gateway (504/404).
  * **Modo Celery + Redis:** Despacho distribuido a colas de trabajo Celery 5.x cuando se cuenta con daemons dedicados.
  * **Auto-actualización reactiva en UI:** Monitoreo visual de campañas en estado `Enviando...` con refresco automático de estado a `Enviada`.

* 🔔 **Ingesta de Eventos en Tiempo Real (Resend Webhooks):**
  * Endpoint integrado en `/campaigns/webhooks/resend/`.
  * Procesamiento automático de eventos: entregas (`delivered`), aperturas (`opened`), clics (`clicked`), rebotes (`bounced`), quejas de spam (`complained`) y desuscripciones (`unsubscribed`).
  * Lista global y por organización de exclusiones (`SuppressionEntry`) para proteger la reputación del dominio remitente.

* 🎨 **Editor Visual de Campañas por Bloques:**
  * Paletas cromáticas armónicas y detección de contrastes accesibles.
  * Subida de logotipos e imágenes con reescalado y compresión automática vía Pillow (máx. 200 KB).
  * Bloques configurables: Cabecera institucional, Título, Texto con formato, Imágenes, Botones CTA y Pie con enlace obligatorio de baja.
  * Enlaces de redirección y seguimiento (`/t/<hash>/`) para atribución comercial.

* 🎯 **Módulo de Oportunidades & Pipeline:**
  * Conversión automática de clics en leads calificados dentro del pipeline de ventas.
  * Gestión interactiva del estado de leads con opción de eliminación segura de prospectos descartados o de prueba.

* 📊 **Importador y Gestor de Audiencias:**
  * Carga masiva mediante archivos Excel/CSV con mapeo automático de campos.
  * Selector rápido de audiencia por etiqueta objetivo (`Tag`) o contacto directo.
  * Duplicador rápido de campañas conservando el diseño base con nueva audiencia asignable.

---

## 🛠️ Requisitos del Sistema

* **Python:** 3.10, 3.11 o 3.12+
* **Base de Datos:** SQLite (desarrollo / entornos estándar) o PostgreSQL
* **API Key de Resend:** Con permisos para `Emails`, `Contacts`, `Segments` y `Broadcasts` en un dominio verificado (ej. `humm.cl`).
* **Redis Server:** (Opcional, únicamente si se utiliza el worker tradicional de Celery en lugar del modo de hilos en segundo plano).

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio y configurar el entorno virtual

```bash
git clone https://github.com/nativoaustral-bit/hummailing.git
cd hummailing

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Variables de Entorno

Copia el archivo de plantilla `.env.example` a `.env` y ajusta tus credenciales:

```bash
cp .env.example .env
```

Parámetros clave en `.env`:

```ini
DEBUG=False
SECRET_KEY=tu-clave-secreta-de-produccion
ALLOWED_HOSTS=mailing.tudominio.cl,localhost,127.0.0.1

# Resend API
RESEND_API_KEY=re_1234567890abcdef
DEFAULT_FROM_EMAIL=Hummailing <hola@tudominio.cl>

# Modo de despacho asíncrono
# True = Despacho en segundo plano vía hilos Python (recomendado en cPanel/Passenger)
# False = Despacho distribuido requiriendo daemon Celery + Redis
CELERY_TASK_ALWAYS_EAGER=True
```

### 3. Migraciones y Datos Iniciales

```bash
python manage.py migrate
python create_demo_data.py
```

### 4. Iniciar en Desarrollo Local

```bash
# Servidor de desarrollo Django
python manage.py runserver
```

*(Opcional si `CELERY_TASK_ALWAYS_EAGER=False`)*:
```bash
# Terminal adicional con Redis activo
celery -A config worker -l info
```

---

## ⏰ Campañas Programadas (Cron)

Para ejecutar de manera automática las campañas configuradas con fecha y hora futura:

```bash
python manage.py process_scheduled_campaigns
```

Se recomienda configurar una tarea periódica en Cron (por ejemplo, cada 5 o 10 minutos):

```cron
*/5 * * * * /home/usuario/MAILING/venv/bin/python /home/usuario/MAILING/manage.py process_scheduled_campaigns >> /home/usuario/MAILING/logs/cron.log 2>&1
```

---

## 🧪 Pruebas Automatizadas

La plataforma cuenta con cobertura de pruebas unitarias y de integración para validar el motor de Broadcasts, la gestión de cuotas de segmentos, la idempotencia y las respuestas asíncronas:

```bash
python manage.py test campaigns
```

---

## 🌐 Configuración de Webhooks en Resend

Para registrar aperturas, clics, entregas y bajas en tiempo real:

1. Ve a tu panel de **Resend → Webhooks → Add Webhook**.
2. **Endpoint URL:** `https://mailing.tudominio.cl/campaigns/webhooks/resend/`
3. **Eventos a seleccionar:**
   * `Email Sent`
   * `Email Delivered`
   * `Email Bounced`
   * `Email Complained`
   * `Email Clicked`
   * `Email Opened`
   * `Contact Unsubscribed`

---

## 🔑 Credenciales de Prueba (Entorno de Desarrollo)

* **Administrador Master Humm:**
  * Usuario: `admin` | Contraseña: `adminpassword123`
* **Cliente Corporativo (Tech Solutions):**
  * Usuario: `tech_admin` | Contraseña: `techpassword123`
* **Cliente Emprendedor (Green Energy):**
  * Usuario: `green_admin` | Contraseña: `greenpassword123`

---

## 📄 Licencia y Créditos

Desarrollado con dedicación por y para el ecosistema de **Humm Co-Creation**.
