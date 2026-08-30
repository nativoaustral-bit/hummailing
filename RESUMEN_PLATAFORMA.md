# 🚀 Hummailing — Plataforma Multiempresa de Email Marketing & Oportunidades

**Hummailing** es una plataforma web integral, multiusuario y multiempresa desarrollada por **Humm Co-Creation** para potenciar las campañas de comunicación, marketing y prospección comercial de emprendedores y empresas de su ecosistema.

> **Slogan Oficial:** *"Convierte cada correo en una oportunidad"*  
> **Firma Institucional:** *Hummailing — Una herramienta de Humm Co-Creation*

---

## 🌐 1. Enlaces y Entornos

* **Producción (HostGator):** [https://mailing.humm.cl](https://mailing.humm.cl)
* **Repositorio en GitHub:** [https://github.com/nativoaustral-bit/hummailing](https://github.com/nativoaustral-bit/hummailing) (Rama `main`)
* **Despliegue Continuo (CI/CD):** Flujo automatizado con GitHub Actions en `.github/workflows/deploy.yml` y script local optimizado en `deploy.sh`.

---

## 🎨 2. Identidad Visual y Marca

* **Nombre Oficial:** **Hummailing — Una herramienta de Humm Co-Creation**
* **Logotipo:** Ubicado en [`static/img/logo.svg`](file:///Users/rmerinog/PLATAFORMAS/CAMPAIGNS/static/img/logo.svg) (isotipo de la marca atravesado por avión de papel corporativo).
* **Paleta de Colores Oficial (Extraída del vector SVG):**
  * **Azul Noche / Primario Estructural (`#173960` / `#0F243E`):** Barras de navegación, encabezados principales, paneles de control y títulos.
  * **Azul Cyan / Acción y Botones (`#0C6FAC` / `#1E9CD3` / `#24A7DB`):** Botones de acción principal (CTA), enlaces activos, estados de selección y botones de guardado.
  * **Naranja Acento (`#F59A29` / `#D7955A`):** Insignias de conversión, alertas destacadas, oportunidades comerciales y estela del avión.
  * **Superficies y Fondos (`#F8FAFC`, `#FFFFFF`, `#EFEAE1`):** Fondos limpios y tarjetas de alto contraste y legibilidad.

---

## 🏛️ 3. Arquitectura Multiempresa y Aislamiento de Datos

La plataforma opera bajo un estricto modelo de **Organizaciones (Espacios de Trabajo Privados)**:

```
                  ┌───────────────────────────────────────────────────────────┐
                  │                 Panel Master Admin Humm                   │
                  │  - Creación de Organizaciones y Asignación de Límites     │
                  │  - Creación de Usuarios con Clave Temporal No Ambigua     │
                  │  - Modo Soporte (Impersonación Segura con Banner Activo)  │
                  └─────────────────────────────┬─────────────────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
   ┌───────────────────────────┐                                 ┌───────────────────────────┐
   │   Organización Cliente A  │                                 │   Organización Cliente B  │
   │  - Contactos Privados     │                                 │  - Contactos Privados     │
   │  - Etiquetas y Segmentos  │                                 │  - Etiquetas y Segmentos  │
   │  - Campañas y Diseñador   │                                 │  - Campañas y Diseñador   │
   │  - Multi-Programaciones   │                                 │  - Multi-Programaciones   │
   │  - Oportunidades (Leads)  │                                 │  - Oportunidades (Leads)  │
   └───────────────────────────┘                                 └───────────────────────────┘
```

### Principios de Seguridad y Aislamiento:
1. **Bases de Contactos Privadas:** `Contact.email` es único **exclusivamente dentro de cada organización** (`unique_together = ('organization', 'email')`). Dos clientes pueden tener al mismo contacto sin interferencias ni acceso cruzado.
2. **Consultas Aisladas por Contexto:** Todas las vistas, consultas ORM y tareas asíncronas filtran obligatoriamente por la organización activa del usuario autenticado.
3. **Persistencia y Blindaje de Producción:** La base de datos en producción (`db.sqlite3`), los archivos multimedia (`media/`) y las credenciales (`.env`) están 100% aislados y protegidos contra sobreescrituras en cada despliegue.

---

## 👑 4. Panel Master Humm: Administración de Clientes y Onboarding

* **🏢 Gestión de Organizaciones:** Creación de empresas clientes, configuración de razones sociales, RUT, datos de contacto, límites máximos de contactos y envíos mensuales, switch de activación/suspensión y auto-incorporación de `https://` en sitios web.
* **👥 Onboarding Automático de Usuarios:**
  * Al crear un nuevo usuario cliente, el sistema genera una contraseña temporal segura (sin caracteres ambiguos como `0`/`O` o `1`/`l`/`I`).
  * Envío automático de correo transaccional de bienvenida con diseño oficial de Hummailing y botón de acceso directo para definir su contraseña definitiva (`templates/emails/welcome_user.html`).
* **🔑 Restablecimiento de Claves:** Módulo para resetear claves de usuarios clientes con notificación por correo (`templates/emails/reset_user_password.html`).
* **📢 Comunicados Masivos a Clientes:** Módulo especial para que Humm redacte y envíe avisos oficiales por correo a todas las empresas clientes activas.
* **📜 Auditoría y Registro de Actividad (`ActivityLog`):** Historial en tiempo real de inicios de sesión, cambios de límites, creación de cuentas y acciones de despacho.
* **🛠️ Modo Soporte (Impersonación):** El administrador master puede acceder con un clic al espacio de trabajo de cualquier cliente para prestar asistencia técnica inmediata.

---

## ✉️ 5. Motor de Campañas y Diseñador Visual

* **Configuración Previa de Paleta y Estilo:** Definición de identidad cromática global antes de redactar (Color de Encabezado, Botones y Fondo del Correo).
* **Sugerencia Armónica de Color:** El editor propone automáticamente combinaciones de alto contraste y legibilidad, además de 6 presets oficiales en 1 clic.
* **Subida y Optimización de Logos e Imágenes (Hasta 2 MB):**
  * Soporte de archivos PNG, JPG, JPEG, WEBP y SVG de hasta **2 MB**.
  * Carga instantánea con renderizado local en memoria (`FileReader`) y optimización automática en el servidor (redimensionamiento inteligente LANCZOS y compresión para email).
  * Doble opción: Subida directa de archivo o ingreso de URL web externa.
* **Canvas Reactivo y Responsivo:** Ancho estándar de 600px optimizado para teléfonos celulares (iPhone, Android) y clientes de escritorio (Gmail, Outlook, Apple Mail).
* **Personalización Dinámica:** Reemplazo en tiempo real de etiquetas como `{{ first_name }}` y `{{ company }}`.
* **Pruebas Instantáneas:** Modal para enviar un correo de prueba individual idéntico al que recibirán los destinatarios finales.

---

## ⏰ 6. Sistema de Envíos con Multi-Programación (Multi-Schedule)

* **Envíos Inmediatos vs Programados:** Selector claro entre despacho inmediato (`🚀 Enviar Ahora`) y programación horaria (`⏰ Programar Envíos`).
* **Múltiples Fechas y Horas por Campaña (`CampaignSchedule`):** Botón **`➕ Agregar otra fecha y hora`** para configurar tandas de envío escalonadas (ej. Lanzamiento el Lunes a las 09:00, Recordatorio el Jueves a las 15:00).
* **Automatización con Cron en Servidor:** Tarea periódica instalada en HostGator que revisa el sistema **cada 5 minutos** (`process_scheduled_campaigns`) y despacha las campañas automáticamente a través de la API de Resend.
* **Motor Híbrido Resiliente:** Envíos inmediatos y directos con respaldo asíncrono en segundo plano (`threading` / `Celery eager`), garantizando alta velocidad sin bloqueos.
* **Badges Visuales en la Lista:** La tabla de campañas muestra el estado de cada tanda programada y marca con un check (`✓`) las ya completadas.

---

## 🎯 7. Captación de Leads y Oportunidades Comerciales

* **Conversión por Clic:** Los botones tipo **"Conversión"** generan automáticamente un **Lead / Oportunidad Comercial** cuando el destinatario hace clic en el enlace.
* **Gestión de Leads:** Módulo con estados comerciales (*Nueva, Por contactar, Contactado, En conversación, Propuesta enviada, Ganada, Perdida*), asignación de responsables, notas y prioridades.
* **Gestión de Bajas Automática:** Enlace de desuscripción funcional que registra al contacto en `SuppressionEntry` para excluirlo de futuros envíos de forma segura.

---

## 📂 8. Estructura del Proyecto

```
CAMPAIGNS/
├── .github/workflows/deploy.yml   # Pipeline de despliegue automático a HostGator
├── config/                        # Settings Django, Celery, Resend API y URLs globales
├── organizations/                 # Módulo multiempresa, Panel Master Humm y logs de auditoría
├── core/                          # Modelo User personalizado, dashboard y reseteo de claves
├── contacts/                      # Contactos, etiquetas, segmentos e importador CSV/Excel
├── campaigns/                     # Editor visual, optimizador de imágenes, tareas y multi-schedule
│   ├── management/commands/       # Comando process_scheduled_campaigns para ejecución periódica
│   └── migrations/                # Migraciones de base de datos (0006_campaignschedule)
├── opportunities/                 # Leads generados por clics de conversión
├── static/img/logo.svg            # Logotipo oficial de Hummailing
├── templates/                     # Plantillas HTML responsivas con Tailwind CSS y Alpine.js
│   ├── campaigns/                 # Editor visual, modal multi-schedule y listado
│   └── emails/                    # Plantillas transaccionales de bienvenida y reseteo
├── deploy.sh                      # Script de sincronización protegida hacia producción
├── start.sh                       # Script de arranque en desarrollo local
├── INSTRUCCIONES_ARRANQUE.txt     # Guía rápida para encender el entorno local
└── RESUMEN_PLATAFORMA.md          # Documentación general de la plataforma
```

---

## 🔄 9. Despliegue y Mantenimiento

### Flujo Automático vía GitHub (Recomendado):
Al hacer push a `main`, el pipeline de GitHub actualiza el servidor de HostGator automáticamente:
```bash
git add .
git commit -m "Descripción de las mejoras"
git push origin main
```

### Despliegue Directo desde Terminal (Mac):
```bash
./deploy.sh
```
*El script aplica automáticamente migraciones, recolecta estáticos, actualiza permisos y reinicia Passenger WSGI de forma segura.*

---

## ⚡ 10. Cuentas de Acceso

* **👑 Administrador Master Humm:**
  * **Usuario:** `admin`
  * **Correo oficial:** `contacto@humm.cl`
  * **Acceso:** [https://mailing.humm.cl/accounts/login/](https://mailing.humm.cl/accounts/login/)
  * **Panel Master:** [https://mailing.humm.cl/humm-admin/](https://mailing.humm.cl/humm-admin/)
* **🏢 Clientes en Producción:**
  * **Humm Co-Creation y Cia. Ltda.**
  * *Organizaciones creadas por el Administrador Master desde su panel.*

---

## 🧪 11. Pruebas Automatizadas

Para validar la integridad del sistema, los modelos y las vistas:
```bash
source venv/bin/activate
python manage.py test
```
*Suite de pruebas unitarias que valida aislamiento de datos, cambio de claves, generación de leads por clic, procesamiento de campañas y permisos administrativos.*
