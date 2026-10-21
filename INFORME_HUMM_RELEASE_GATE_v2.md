# INFORME HUMM RELEASE GATE v2 & ADDENDUM v2.1
## Auditoría Técnica, Seguridad, Integridad y Preparación Operacional

---

### 📋 1. Identificación de la Aplicación y Entorno

* **Nombre del Producto:** **Hummailing — Una herramienta de Humm Co-Creation**
* **Slogan:** *"Convierte cada correo en una oportunidad"*
* **Repositorio:** [nativoaustral-bit/hummailing](https://github.com/nativoaustral-bit/hummailing) (Rama `main`)
* **Ubicación Local:** `/Users/rmerinog/PLATAFORMAS/CAMPAIGNS`
* **Entorno de Producción:** HostGator Shared Hosting (cPanel / CloudLinux / Passenger WSGI)
* **URL Pública:** [https://mailing.humm.cl](https://mailing.humm.cl)
* **Framework:** Django 6.0.7 / Python 3.14 / SQLite 3 / Tailwind CSS (vía CDN en landing) / Alpine.js
* **Fecha de Evaluación:** 11 de Septiembre de 2026
* **Marco Metodológico:** **HUMM RELEASE GATE v2** complementado con **ADDENDUM v2.1** (OWASP ASVS 5.0 Nivel 2 adaptado, OWASP Top 10, NIST SSDF).

---

### 🎯 2. Etapa del Producto y Pilot Envelope

#### Etapa Evaluada: **ETAPA A — MVP / PILOTO CONTROLADO**

* **Justificación:** La plataforma se encuentra lista para iniciar validaciones con las primeras organizaciones y empresas del ecosistema Humm. Aún no existe volumen transaccional masivo externo ni dependencia contractual crítica de cientos de clientes.
* **Pilot Envelope (Condiciones de Operación del Piloto):**
  * **Organizaciones simultáneas:** Hasta 5 a 8 empresas controladas.
  * **Contactos totales por empresa:** Hasta 5.000 contactos.
  * **Volumen de envío mensual:** Hasta 20.000 correos/mes mediante Resend API.
  * **Supervisión:** Acompañamiento directo por parte del Administrador Master Humm (`contacto@humm.cl`).

---

### 🧩 3. Perfil de Complejidad de la Aplicación

| Dimensión | Nivel | Justificación Técnica |
| :--- | :---: | :--- |
| **Autenticación y Sesiones** | **MEDIA** | Django Auth integrado, usuarios personalizados (`core.User`), reseteo de claves vía token temporal y cookies HTTPOnly. |
| **Roles y Autorización** | **MEDIA-ALTA** | 4 niveles de roles (`humm_admin`, `org_admin`, `campaign_editor`, `viewer`) con comprobación estricta en Backend. |
| **Multitenancy (Aislamiento)** | **ALTA** | Múltiples organizaciones con segregación forzosa en Contactos, Etiquetas, Segmentos, Campañas, Oportunidades y Leads. |
| **Información Personal / PII** | **MEDIA** | Nombres, correos, teléfonos y empresas de contactos comerciales. No almacena datos bancarios ni tarjetas de crédito. |
| **Subida de Archivos** | **MEDIA** | Carga de logotipos y recursos para campañas; validación de formato raster vía Pillow y magic bytes. |
| **Integraciones Externas** | **MEDIA** | Resend API (vía SDK HTTP y fallback SMTP TLS 587) para despacho de campañas y correos transaccionales. |
| **Procesos en Segundo Plano** | **MEDIA** | Modo Celery Eager para hosting compartido + fallback multihilo asíncrono + `CampaignSchedule` para envíos periódicos. |
| **Persistencia y Backups** | **MEDIA** | Base de datos SQLite estructurada con comandos dedicados de backup con checksum SHA-256 y restauración aislada. |

---

### 🚦 4. VEREDICTO OFICIAL

#### Para MVP / Piloto Controlado:
# 🟢 APTO PARA PILOTO CONTROLADO

#### Para Operación Comercial Masiva:
# 🟡 APTO CON CONDICIONES *(Ver Disparadores de Escalamiento en Sección 8)*

---

### 📊 5. Resumen Ejecutivo de la Auditoría

| Métrica | Estado | Detalle |
| :--- | :---: | :--- |
| **P0 (Bloqueadores Críticos Activos)** | **0** | Ninguna vulnerabilidad P0 activa tras remediaciones y validaciones. |
| **P1 (Riesgos Altos Mitigados)** | **0 Activos** | 4 mitigados y blindados con pruebas automatizadas. |
| **Deuda Técnica Aceptada (DT)** | **3** | Documentadas y compatibles con el Pilot Envelope. |
| **Disparadores de Escalamiento (ESC)** | **2** | Identificados para la futura transición a Etapa B/C. |
| **Suite de Pruebas Automatizadas** | **20 / 20 (100%)** | `Ran 20 tests in 21.968s — OK` sin fallas ni advertencias. |
| **Aislamiento Multitenant** | **VERIFICADO** | Cero fugas horizontales demostradas entre organizaciones. |
| **Frontera de Confianza Backend** | **VERIFICADO** | Todas las mutaciones son validadas en servidor con rechazo 403/404. |
| **Copias de Seguridad e Integridad** | **VERIFICADO** | Manifiestos con SHA-256 de base de datos y media; restauración en dry-run aislada comprobada. |

---

### 🛡️ 6. Matriz de Controles (HUMM RELEASE GATE v2 & v2.1)

| Control / Dimensión | Estado | Evidencia y Mecanismo de Verificación |
| :--- | :---: | :--- |
| **1. Frontera Backend / Frontend (Addendum A)** | **APROBADO** | Los roles y el ID de tenant se extraen de la sesión del usuario (`request.user.organization`). Requests HTTP manipulados directamente intentando editar o borrar recursos ajenos son rechazados con 403/404. |
| **2. Contraseñas Universales y Backdoors (Addendum B)** | **APROBADO** | No existen contraseñas maestras, credenciales hardcodeadas ni bypasses administrativos. Hashes PBKDF2/SHA256 con validadores nativos de Django. |
| **3. Aislamiento Multitenant (OWASP ASVS V4.1)** | **APROBADO** | Comprobado en `test_cross_tenant_isolation_rejections`. Un usuario de una empresa no puede leer, mutar, eliminar ni asignar contactos, campañas u oportunidades de otra empresa. |
| **4. Jerarquía de Roles y Mutaciones (Addendum C)** | **APROBADO** | Comprobado en `test_viewer_role_blocked_on_all_mutations` y `test_campaign_editor_role_boundaries`. El rol `viewer` tiene bloqueado el 100% de los POSTs mutantes (403). `campaign_editor` solo puede editar campañas sin alterar contactos ni borrar campañas. |
| **5. Subida Segura de Archivos (OWASP Top 10 A04)** | **APROBADO** | Comprobado en `test_image_upload_security_svg_rejection_and_raster_validation`. Archivos SVG son bloqueados tajantemente con HTTP 400 (prevención de XSS almacenado). Archivos camuflados con doble extensión o sin firmas válidas de Pillow son rechazados. Límite forzado a 2MB. |
| **6. Rate Limiting y Anti-Abuso (Addendum F)** | **APROBADO** | Comprobado en `test_concurrent_rate_limiting_on_lead_capture`. Endpoint `/captar-lead/` cuenta con rate limiting por IP (máximo 5 solicitudes/hora) implementado con `FileBasedCache` y bloqueo de concurrencia atómico mediante `fcntl.flock` anti-race condition. Solicitud 6+ rechazada con HTTP 429. |
| **7. Enlaces de Desuscripción Criptográficos** | **APROBADO** | Comprobado en `test_tampered_or_cross_org_unsubscribe_token_rejected`. Tokens firmados criptográficamente mediante `TimestampSigner(salt=UNSUB_SALT)` con expiración a 30 días. Verificación cruzada forzosa en BD entre `contact_id` y `organization_id`. |
| **8. Backups Consistentes y Verificación Aislada** | **APROBADO** | Comprobado en `test_backup_and_restore_isolated_cycle`. Comando `backup_data` genera archivo ZIP con SQLite consistente (`PRAGMA integrity_check`), compresión de `media/`, cálculo de hashes SHA-256 independientes y manifiesto con conteo de registros. Comando `restore_data` valida checksums e integridad sin alterar producción en modo `--isolated --dry-run`. |
| **9. Protección de Despliegue y Persistencia** | **APROBADO** | El script `deploy.sh` y el archivo `.gitignore` protegen estrictamente `db.sqlite3`, el directorio `media/` y `.env`, impidiendo que un despliegue sobreescriba datos reales. |
| **10. Protección de Secretos y Configuración Web** | **APROBADO** | Variables críticas en `.env` (fuera del repositorio). Archivo `.htaccess` bloquea el acceso HTTP a `.env`, archivos SQLite (`.sqlite3`), logs y directorios privados con regla `Require all denied`. |
| **11. Páginas de Error y Ocultamiento de Stack Trace** | **APROBADO** | Plantillas personalizadas `templates/404.html` y `templates/500.html` operativas. `DEBUG=False` configurado para producción. |
| **12. Protección CSRF y Encabezados de Seguridad** | **APROBADO** | Middleware `CsrfViewMiddleware` activo en todas las operaciones POST de la plataforma. `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN` configurados en `.htaccess` y `settings.py`. |

---

### 🔍 7. Registro de Hallazgos y Deuda Técnica Aceptada

#### Deuda Técnica Aceptada para el Piloto (DT):
* **DT-01: Almacenamiento Local de Archivos Multimedia (`media/` en disco)**
  * *Estado:* Aceptado para MVP.
  * *Impacto:* Los logotipos y adjuntos se guardan en el sistema de archivos del servidor compartido de HostGator.
  * *Mitigación:* Se respalda automáticamente en el ZIP de backup generado por `backup_data`.
  * *Umbral de cambio:* Migrar a Amazon S3 o Cloudflare R2 si el almacenamiento supera los 5 GB o se migra a servidores efímeros (Docker/Kubernetes).
* **DT-02: Base de Datos SQLite en Servidor Compartido**
  * *Estado:* Aceptado para MVP.
  * *Impacto:* SQLite no soporta escrituras de alta concurrencia masiva simultánea.
  * *Mitigación:* Se configuró `timeout: 20` segundos en la conexión Django para evitar bloqueos transitorios; la concurrencia de lectura es excelente y el volumen del piloto es bajo.
  * *Umbral de cambio:* Ver disparador ESC-01.
* **DT-03: Despacho Asíncrono de Campañas vía Fallback Multihilo / Eager**
  * *Estado:* Aceptado para MVP.
  * *Impacto:* HostGator compartido no permite demonios persistentes Redis ni Celery Workers permanentes.
  * *Mitigación:* Se habilitó `CELERY_TASK_ALWAYS_EAGER = True` con procesamiento por lotes asíncrono en hilos secundarios de Python (`threading.Thread`) y soporte de reprogramación en `CampaignSchedule`.

---

### 🚀 8. Disparadores de Escalamiento (ESC)

No se debe incurrir en costos prematuros de infraestructura empresarial mientras la plataforma se mantenga dentro del **Pilot Envelope**. Se recomienda ejecutar la transición cuando se alcance alguno de los siguientes eventos medibles:

1. **ESC-01 (Migración de SQLite a PostgreSQL Administrado):**
   * *Disparador:* Superar las **10 empresas clientes activas**, o cuando la base de contactos global supere los **50.000 registros**, o si se detectan errores recurrentes de contención `database is locked`.
2. **ESC-02 (Infraestructura Dedicada con Redis + Celery Workers Reales):**
   * *Disparador:* Envíos masivos que superen los **15.000 correos en una sola campaña** o requerimiento de webhooks en tiempo real con alta tasa de eventos simultáneos de apertura y clics.

---

### 🧹 9. Candidatos a Limpieza Post-Remediación

Los siguientes elementos temporales generados durante las pruebas locales de auditoría pueden depurarse sin afectar el funcionamiento del sistema:
* `tmp/cache/*` (archivos de caché y locks de prueba generados por el test de concurrencia).
* `tmp/backups/*` (archivos de backup creados en pruebas manuales locales).
* *Nota:* **No eliminar** `core/management/commands/backup_data.py`, `core/management/commands/restore_data.py`, `core/security.py` ni la suite en `core/tests.py`.

---

### ✍️ 10. Pregunta Final y Declaración de Cierre

> **¿Autorizarías personalmente que esta aplicación sea utilizada por los primeros usuarios reales bajo las condiciones del Pilot Envelope definido?**

# SÍ — APTO PARA PILOTO

#### Fundamentación Técnica:
1. **Seguridad probada:** No existe exposición de datos entre organizaciones; la frontera de autorización en el backend rechaza intentos de manipulación de identificadores y roles.
2. **Integridad de datos:** Las operaciones críticas cuentan con validación criptográfica, sanitización estricta de imágenes y protección de archivos productivos ante despliegues.
3. **Continuidad operativa:** La plataforma cuenta con herramientas funcionales y verificadas de respaldo integral y restauración de emergencia probadas al 100%.
4. **Validación empírica:** Los 20 casos de prueba de la suite automatizada pasaron exitosamente sin errores.

---
*Fin del informe oficial HUMM RELEASE GATE v2.*
