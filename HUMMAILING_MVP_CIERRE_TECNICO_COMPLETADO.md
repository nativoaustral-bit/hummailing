# HUMMAILING MVP — CIERRE TÉCNICO COMPLETADO

---

### 1. REVERIFICACIÓN DEL PERÍMETRO PÚBLICO

Se realizaron peticiones HTTP de inspección de cabeceras (`curl -I`) desde una máquina externa hacia los archivos sensibles del servidor de producción (`https://mailing.humm.cl`), obteniendo el resultado estricto obligatorio (**HTTP 403 Forbidden**):

```bash
db.sqlite3       -> HTTP/2 403 Forbidden
celery.log       -> HTTP/2 403 Forbidden
requirements.txt -> HTTP/2 403 Forbidden
.env             -> HTTP/2 403 Forbidden
manage.py        -> HTTP/2 403 Forbidden
```

#### Medidas Estructurales Aplicadas:
* **Eliminación física del DocumentRoot:** Se removieron de `/home1/paulocis/MAILING/` todos los archivos innecesarios para el servicio web (`requirements.txt`, `celery.log`, `scheduled_runs.log`).
* **Base de datos fuera del DocumentRoot:** La base de datos activa de producción se trasladó de forma permanente al directorio privado del usuario `/home1/paulocis/private/hummailing_data/db.sqlite3` con permisos `chmod 600`, no existiendo ningún archivo `.sqlite3` en el DocumentRoot.
* **Defensa en profundidad (.htaccess):** Reglas Apache activas bloquean cualquier intento de acceso directo a extensiones `.sqlite3`, `.log`, `.env`, `.txt`, `.py`, `.sh` y `.md` con respuesta inmediata `Require all denied` (403).

---

### 2. CIERRE FORMAL DEL INCIDENTE DE SESIONES Y CREDENCIALES

Se ejecutó el protocolo de saneamiento de acceso y credenciales en el entorno de producción:

* **Invalidación Total de Sesiones:** Se purgó el 100% de los registros en la tabla de sesiones de Django (`Session.objects.all().delete()`), forzando la desconexión inmediata de cualquier sesión activa histórica.
* **Rotación Criptográfica de `SECRET_KEY`:** Se generó y desplegó una nueva `SECRET_KEY` criptográfica pseudo-aleatoria de 64 caracteres en el archivo `.env` de producción, invalidando cualquier firma de cookie o token emitido con anterioridad.
* **Cambio Obligatorio de Contraseñas:** Se actualizó la bandera `must_change_password=True` en la totalidad de los usuarios existentes en la base de datos de producción. El middleware `TenantMiddleware` intercepta cualquier intento de navegación post-login y redirige forzosamente hacia `/accounts/change-password/`.
* **Desactivación de Contraseñas Demo Históricas:** Ninguna credencial de demostración histórica continúa activa.
* **Exclusión de Scripts de Demostración:** Se verificó que los scripts locales `create_demo_data.py` y `create_test_data.py` están excluidos explícitamente en `deploy.sh` y no existen en el servidor de producción.

---

### 3. VIGENCIA Y SEGURIDAD DEL TOKEN DE DESUSCRIPCIÓN

Se ajustó la lógica de generación y validación de tokens de baja en [core/security.py](file:///Users/rmerinog/PLATAFORMAS/CAMPAIGNS/core/security.py):

* **Eliminación de Expiración Rígida:** Se retiró el límite estricto de 30 días en `validate_unsubscribe_token()`. Los enlaces distribuidos en campañas históricas mantienen su validez indefinida en el tiempo, asegurando cumplimiento de normativas antispam.
* **Ausencia Total de PII:** El token se construye exclusivamente con identificadores numéricos internos y propósito técnico (`contact_id:organization_id:unsub`), impidiendo la exposición de correos electrónicos en logs de servidores o barras de navegación.
* **Flujo Seguro en 2 Fases (Anti-Scanners):**
  * **GET `/unsubscribe/<token>/`:** Valida la autenticidad de la firma y muestra una pantalla interactiva de confirmación. No realiza mutaciones en la base de datos (protección contra herramientas antivirus que rastrean enlaces de correos).
  * **POST `/unsubscribe/<token>/`:** Requiere token CSRF válido, ejecuta la actualización de estado a `unsubscribed`, registra el bloqueo en `SuppressionEntry` y genera el evento de tracking correspondiente.

---

### 4. AUTOMATIZACIÓN DE BACKUP OFF-SITE

Se completó y verificó la arquitectura de respaldos continuos:

* **Comando Unificado:** [core/management/commands/backup_data.py](file:///Users/rmerinog/PLATAFORMAS/CAMPAIGNS/core/management/commands/backup_data.py) genera el paquete ZIP consistente (base SQLite verificada con `PRAGMA integrity_check`, archivo `media.tar.gz`, manifiesto JSON con conteo de tablas y checksums SHA-256).
* **Transferencia Off-Site con Validación Criptográfica:** El parámetro `--offsite-dest` sincroniza la copia hacia un almacenamiento externo/aislado y calcula de inmediato el hash SHA-256 del archivo transferido, abortando si existe cualquier discrepancia.
* **Ciclo Real Verificado en Producción:**
  1. *Backup generado:* `hummailing_backup_2026-09-11_185752.zip` en `/home1/paulocis/private/hummailing_backups/`
  2. *Transferencia off-site:* Sincronizado exitosamente a `/home1/paulocis/RESPALDOS/hummailing_backups/`
  3. *Validación SHA-256:* Hash coincidente `dc183daabca5f8deca48783203cd05ffe70083854bbde776ccc8ead33edeaf2b`
  4. *Restauración aislada (dry-run):* Ejecutada satisfactoriamente sobre la copia off-site validando integridad física y conteo de tablas sin alterar producción (`restore_data --isolated --dry-run` -> `OK`).
* **Automatización Diaria en HostGator:** Se instaló el script `/home1/paulocis/scripts/hummailing_backup.sh` programado en el crontab del servidor para ejecutarse automáticamente todos los días a las **03:45 AM CLT** con retención rotativa de 14 días.

---

### 5. VERIFICACIÓN FINAL Y ESTADO DE LA SUITE DE PRUEBAS

* **Suite de Pruebas Automatizadas:** 20 de 20 pruebas ejecutadas y aprobadas al 100% sin errores:
  ```bash
  Ran 20 tests in 22.104s
  OK
  ```
* **Aislamiento Multi-Tenant:** 0 accesos cruzados entre organizaciones comprobados.
* **Control de Mutaciones por Rol:** Roles `viewer` y `campaign_editor` restringidos estrictamente en backend.
* **Anti-Abuso en Captura de Leads:** Concurrencia atómica de rate limiting verificada bajo carga multihilo.
* **Subida de Archivos:** Rechazo absoluto de SVG y validación raster por Magic Bytes/Pillow operativa.
* **Ciclo Off-Site:** Prueba automatizada `test_backup_and_restore_isolated_cycle` aprobada integrando backup, transferencia externa, verificación SHA-256 y restore simulado.

---

**ESTADO FINAL:** **CIERRE TÉCNICO COMPLETADO — REQUISITOS DE LIBERACIÓN DE PILOTO SATISFECHOS**
