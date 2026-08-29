# 🚀 Hummailing — Plataforma Multiempresa de Email Marketing & Oportunidades

**Hummailing** (anteriormente Humm Campaigns) es una plataforma web integral, multiusuario y multiempresa desarrollada por **Humm** para potenciar las campañas de comunicación, marketing y prospección comercial de emprendedores y empresas de su ecosistema.

---

## 🌐 1. Enlaces y Entornos

* **Producción (HostGator):** [https://mailing.humm.cl](https://mailing.humm.cl)
* **Repositorio en GitHub:** [https://github.com/nativoaustral-bit/hummailing](https://github.com/nativoaustral-bit/hummailing)
* **Despliegue Continuo (CI/CD):** Flujo automatizado con GitHub Actions en `.github/workflows/deploy.yml`.

---

## 🎨 2. Identidad Visual y Marca

- **Nombre Oficial:** **Hummailing — Una herramienta de Humm**
- **Logotipo:** Ubicado en [`static/img/logo.svg`](file:///Users/rmerinog/PLATAFORMAS/CAMPAIGNS/static/img/logo.svg) (avión de papel atravesando el isotipo de la marca).
- **Paleta de Colores Oficial (Extraída del vector SVG):**
  - **Azul Noche / Primario Estructural (`#173960` / `#0F243E`):** Barras de navegación, encabezados principales, paneles de control y títulos.
  - **Azul Cyan / Acción y Botones (`#0C6FAC` / `#1E9CD3` / `#24A7DB`):** Botones de acción principal (CTA), enlaces activos, estados de selección y botones de guardado.
  - **Naranja Acento (`#F59A29` / `#D7955A`):** Insignias de conversión, alertas destacadas, oportunidades comerciales y estela del avión.
  - **Superficies y Fondos (`#F8FAFC`, `#FFFFFF`, `#EFEAE1`):** Fondos limpios y tarjetas de alto contraste y legibilidad.

---

## 🏛️ 3. Arquitectura Multiempresa y Aislamiento de Datos

La plataforma está diseñada con una estricta separación de datos mediante **Organizaciones (Espacios de Trabajo Privados)**:

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
   │  - Oportunidades (Leads)  │                                 │  - Oportunidades (Leads)  │
   └───────────────────────────┘                                 └───────────────────────────┘
```

### Principios de Aislamiento:
1. **Bases de Contactos Privadas:** `Contact.email` es único **únicamente dentro de su organización** (`unique_together = ('organization', 'email')`). Dos clientes de Humm pueden tener registrado al mismo contacto sin interferir ni visualizar la información del otro.
2. **Consultas Aisladas:** Todas las vistas, consultas a la base de datos y tareas asíncronas filtran obligatoriamente por la organización del usuario autenticado.

---

## 👑 4. Panel Master Humm: Administración Exclusiva de Clientes

El panel del **Administrador Master Humm** está 100% enfocado en la gestión de clientes y servicios:

### Módulos del Administrador Master:
* **🏢 Gestión de Organizaciones:** Creación de nuevas empresas clientes, configuración de razones sociales, RUT, datos de contacto, límites máximos de contactos, límites mensuales de envíos, switch interactivo de activación/suspensión y botón de eliminación permanente.
* **👥 Gestión de Usuarios y Accesos:** Creación de usuarios con contraseñas temporales autogeneradas seguras (sin caracteres ambiguos como `0`/`O` o `1`/`l`/`I`), URLs de acceso dinámicas (`https://mailing.humm.cl`), switch de activación/desactivación de cuentas, reseteo administrativo de claves y eliminación de usuarios.
* **📢 Comunicados Masivos a Clientes:** Módulo especial para que Humm redacte y envíe avisos oficiales o notificaciones de servicio por correo a todas las empresas clientes activas.
* **📜 Auditoría y Registro de Actividad:** Historial de inicios de sesión, cambios de límites, creación de cuentas y acciones de seguridad.
* **🛠️ Modo Soporte a Clientes (Impersonación):** El administrador puede presionar **"Soporte ↗"** en la ficha del cliente para ingresar a su espacio de trabajo y salir con un solo clic.

---

## ✉️ 5. Motor de Campañas y Diseñador Visual

* **Configuración Previa de Paleta y Estilo:** Antes de agregar bloques, el usuario define la identidad cromática global de la campaña (Color de Encabezado, Color de Botones y Fondo del Correo).
* **Sugerencia Automática de Armonía de Color:** Al elegir un color para el encabezado, el sistema propone automáticamente los colores armónicos y de alto contraste para botones, textos y enlaces, además de ofrecer 6 combinaciones oficiales en 1 clic (Humm Navy, Humm Naranja, Cyan, Esmeralda, Slate y Blanco Minimalista).
* **Subida y Optimización de Logos (Máx 200 KB):** Carga directa de imágenes corporativas con validación estricta de peso (máximo 200 KB) y redimensionamiento automático de alta calidad (LANCZOS máx 600×200 px).
* **Editor de Bloques y Previsualización Amplia:** Canvas centrado de 600px con scroll fluido independiente para revisar encabezado, cuerpo y pie de página cómodamente.
* **Personalización Dinámica:** Reemplazo en tiempo real de etiquetas como `{{ first_name }}` y `{{ company }}`.
* **Pruebas y Programación:** Botón **"Enviar Campaña"** con opciones para despacho masivo inmediato, programación por fecha/hora o envío de prueba instantáneo a un correo específico.

---

## 🎯 6. Captación de Leads y Oportunidades Comerciales

* **Conversión por Clic:** Los botones de correo configurados como tipo **"Conversión"** generan automáticamente un **Lead / Oportunidad Comercial** cuando el destinatario hace clic en el enlace.
* **Gestión de Leads:** Módulo con filtros de estado (*Nueva, Por contactar, Contactado, En conversación, Propuesta enviada, Ganada, Perdida*), asignación de ejecutivos responsables, prioridad y bitácora de notas.
* **Gestión de Bajas:** Enlace de desuscripción funcional que incorpora al contacto en la lista de exclusiones (`SuppressionEntry`) para evitar futuros envíos accidentales.

---

## 📂 7. Estructura del Proyecto

```
CAMPAIGNS/
├── .github/workflows/deploy.yml # Pipeline de despliegue automático a HostGator
├── config/                      # Ajustes globales, middleware de aislamiento y Celery
├── organizations/               # Módulo multiempresa, administración Humm y auditoría
├── core/                        # Modelo User personalizado, dashboard y contraseñas
├── contacts/                    # Contactos, etiquetas, segmentos e importador CSV/Excel
├── campaigns/                   # Editor visual, optimizador de imágenes y despachos
├── opportunities/               # Leads generados por clics de conversión
├── static/img/logo.svg          # Logotipo oficial de Hummailing
├── templates/                   # Plantillas responsivas con Tailwind y Alpine.js
├── deploy.sh                    # Script local de sincronización a producción
├── start.sh                     # Script de arranque en desarrollo local
└── RESUMEN_PLATAFORMA.md        # Documentación de la plataforma
```

---

## 🔄 8. Despliegue y Actualizaciones

### Flujo Automático vía GitHub (Recomendado):
Cada vez que se suben cambios a GitHub, **GitHub Actions** actualiza el servidor de HostGator automáticamente:
```bash
git add .
git commit -m "Descripción de las mejoras"
git push origin main
```

### Despliegue Manual desde Mac (Alternativo):
```bash
./deploy.sh
```

---

## ⚡ 9. Cuentas de Acceso

* **👑 Administrador Master Humm:**
  - **Usuario:** `admin`
  - **Acceso:** [https://mailing.humm.cl/accounts/login/](https://mailing.humm.cl/accounts/login/)
  - **Panel de Control Master:** [https://mailing.humm.cl/humm-admin/](https://mailing.humm.cl/humm-admin/)
* **🏢 Clientes de Prueba Creados:**
  - **Acme Soluciones Digitales:** `acme.admin`
  - **BioNativa Cosmética:** `bionativa.admin`
  - **The Seed:** `benja`

---

## 🧪 10. Pruebas Automatizadas

Para validar la integridad del sistema y el aislamiento multiempresa:
```bash
source venv/bin/activate
python manage.py test
```
*Suite de pruebas unitarias aprobadas que validan aislamiento de datos, cambio forzado de clave, generación de oportunidades por clic y permisos administrativos.*
