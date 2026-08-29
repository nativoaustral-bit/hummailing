# 🚀 Hummailing — Plataforma Multiempresa de Email Marketing & Oportunidades

**Hummailing** (anteriormente Humm Campaigns) es una plataforma web integral, multiusuario y multiempresa desarrollada por **Humm** para potenciar las campañas de comunicación, marketing y prospección comercial de emprendedores y empresas de su ecosistema.

---

## 🎨 1. Identidad Visual y Marca

- **Nombre Oficial:** **Hummailing — Una herramienta de Humm**
- **Logotipo:** Ubicado en [`static/img/logo.svg`](file:///Users/rmerinog/PLATAFORMAS/CAMPAIGNS/static/img/logo.svg) (avión de papel atravesando el isotipo de la marca).
- **Paleta de Colores Oficial (Extraída del vector SVG):**
  - **Azul Noche / Primario Estructural (`#173960` / `#0F243E`):** Barras de navegación, encabezados principales, paneles de control y títulos.
  - **Azul Cyan / Acción y Botones (`#0C6FAC` / `#1E9CD3` / `#24A7DB`):** Botones de acción principal (CTA), enlaces activos, estados de selección y botones de guardado.
  - **Naranja Acento (`#F59A29` / `#D7955A`):** Insignias de conversión, alertas destacadas, oportunidades comerciales y estela del avión.
  - **Superficies y Fondos (`#F8FAFC`, `#FFFFFF`, `#EFEAE1`):** Fondos limpios y tarjetas de alto contraste y legibilidad.

---

## 🏛️ 2. Arquitectura Multiempresa y Aislamiento de Datos

La plataforma está diseñada con una estricta separación de datos mediante **Organizaciones (Espacios de Trabajo Privados)**:

```
                  ┌───────────────────────────────────────────────────────────┐
                  │                 Panel Master Admin Humm                   │
                  │  - Creación de Organizaciones y Asignación de Límites     │
                  │  - Creación de Usuarios con Clave Temporal                │
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

## 👑 3. Panel Master Humm: Administración Exclusiva de Clientes

El panel del **Administrador Master Humm** está 100% enfocado en la gestión de clientes y servicios:

### Módulos del Administrador Master:
* **🏢 Gestión de Organizaciones:** Creación de nuevas empresas clientes, configuración de razones sociales, RUT, datos de contacto, límites máximos de contactos, límites mensuales de envíos, switch interactivo de activación/suspensión y botón de eliminación permanente.
* **👥 Gestión de Usuarios y Accesos:** Creación de usuarios asignados a clientes con contraseñas temporales autogeneradas seguras, switch de activación/desactivación de cuentas, reseteo administrativo de claves y eliminación de usuarios.
* **📢 Comunicados Masivos a Clientes:** Módulo especial para que Humm redacte y envíe avisos oficiales o notificaciones de servicio por correo a todas las empresas clientes activas.
* **📜 Auditoría y Registro de Actividad:** Historial de inicios de sesión, cambios de límites, creación de cuentas y acciones de seguridad.
* **🛠️ Modo Soporte a Clientes (Impersonación):** Si Humm necesita revisar o configurar las campañas de un cliente específico, el administrador puede presionar **"Soporte ↗"** en la ficha del cliente para ingresar a su espacio de trabajo y salir con un solo clic. Si Humm desea enviar sus propias campañas, lo hace a través de su propia organización ("Humm Ecosistema").

---

## ✉️ 4. Motor de Campañas y Editor Visual

* **Configuración Previa de Paleta y Estilo:** Antes de agregar bloques, el usuario define la identidad cromática global de la campaña (Color de Encabezado, Color de Botones y Fondo del Correo).
* **Sugerencia Automática de Armonía de Color:** Al elegir o escribir un color para el encabezado, el sistema propone automáticamente los colores armónicos y de alto contraste para botones, textos y enlaces, además de ofrecer combinaciones oficiales en 1 clic (Humm Navy, Humm Naranja, Cyan, Esmeralda, Slate y Blanco Minimalista).
* **Editor por Bloques:** Construcción visual arrastrable y ordenable (Encabezado con Logo, Títulos, Textos, Imágenes, Botones CTA y Pie de página con desuscripción), donde el encabezado y botones heredan automáticamente el estilo global de la campaña.
* **Personalización Dinámica:** Reemplazo en tiempo real de etiquetas como `{{ first_name }}` y `{{ company }}`.
* **Pruebas y Programación:** Enlace directo para enviar un correo de prueba a un email específico antes del despacho general, o programar el envío para una fecha/hora futura.
* **Infraestructura Asíncrona:** Celery 5.x + Broker Redis + API de Resend para despachos masivos sin congelar el servidor web.

---

## 🎯 5. Captación de Leads y Oportunidades Comerciales

* **Conversión por Clic:** Los botones de correo configurados como tipo **"Conversión"** generan automáticamente un **Lead / Oportunidad Comercial** cuando el destinatario hace clic en el enlace.
* **Gestión de Leads:** Módulo con filtros de estado (*Nueva, Por contactar, Contactado, En conversación, Propuesta enviada, Ganada, Perdida*), asignación de ejecutivos responsables, prioridad y bitácora de notas.
* **Gestión de Bajas:** Enlace de desuscripción funcional que incorpora al contacto en la lista de exclusiones (`SuppressionEntry`) para evitar futuros envíos accidentales.

---

## 📂 6. Estructura de Aplicaciones y Módulos

```
CAMPAIGNS/
├── config/                  # Ajustes globales, middleware de aislamiento y Celery
├── organizations/           # Módulo multiempresa, administración Humm y auditoría
├── core/                    # Modelo User personalizado, dashboard y cambio de contraseña
├── contacts/                # Gestión de contactos, etiquetas, segmentos e importador CSV/Excel
├── campaigns/               # Editor visual, enlaces con tracking y tareas asíncronas
├── opportunities/           # Módulo de Leads generados por clics de conversión
├── static/img/logo.svg      # Logotipo oficial de Hummailing
├── templates/               # Plantillas responsivas con Tailwind y Alpine.js
├── start.sh                 # Script de arranque en un solo paso
├── INSTRUCCIONES_ARRANQUE.txt# Manual de uso y credenciales
└── RESUMEN_PLATAFORMA.md    # Este documento
```

---

## ⚡ 7. Puesta en Marcha y Accesos Rápidos

### Iniciar la plataforma:
Desde la terminal en la raíz del proyecto:
```bash
./start.sh
```
Abre en el navegador: [http://localhost:8000](http://localhost:8000)

### Cuentas de Acceso Configuradas:
1. **👑 Administrador Master Humm:**
   - **Usuario:** `admin` | **Contraseña:** `admin`
   - **Panel de Control Master:** [http://localhost:8000/humm-admin/](http://localhost:8000/humm-admin/)
2. **🏢 Cliente 1 (Acme Soluciones Digitales):**
   - **Usuario:** `acme.admin` | **Contraseña:** `acme1234`
3. **🌿 Cliente 2 (BioNativa Cosmética):**
   - **Usuario:** `bionativa.admin` | **Contraseña:** `bionativa1234`

---

## 🧪 8. Pruebas Automatizadas

Para validar la integridad del sistema y el aislamiento multiempresa:
```bash
source venv/bin/activate
python manage.py test
```
*Suite de 7 pruebas unitarias aprobadas al 100% que validan aislamiento de datos, cambio forzado de clave, generación de oportunidades por clic y permisos administrativos.*
