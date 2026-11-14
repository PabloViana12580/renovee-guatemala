# Guía para desarrolladores

## Arquitectura

Django 5.2 LTS, plantillas renderizadas en el servidor con Bootstrap 5.3 (servido desde el propio
sitio) y PostgreSQL (cualquier proveedor). La app `core` reúne lo compartido: utilidades de
configuración, acceso del personal con bloqueo y verificación en dos pasos, el sitio de
administración, middleware de seguridad, sondas de salud y disponibilidad, protección contra spam,
correo, registros y el sistema de diseño. Los módulos de negocio (listados en `config/modules.py`)
agregan las funciones del sitio:

| Módulo | Apps | Qué hace |
| --- | --- | --- |
| Sitio web | `pages` | Páginas públicas: inicio, sobre nosotros, política de privacidad y términos de uso. Las páginas de productos y servicios aparecerán aquí cuando se agregue Catálogo. |
| CRM | `crm` | Un CRM pequeño: contactos con notas, etiquetas e historial; el formulario de contacto crea clientes potenciales y avisa al dueño por correo; etapas (nuevo, contactado, cotizado, ganado, perdido); tareas de seguimiento con fecha; exportación CSV; registro del consentimiento para publicidad; exportación de los datos de un contacto. Se gestiona desde la administración. Los pedidos y citas de módulos futuros aparecerán en el mismo historial. |

## Instalación local

Requisitos: Python 3.13, Git y una base de datos PostgreSQL (en la nube o local).

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # luego complete DATABASE_URL y los valores SITE_*
.venv/Scripts/python.exe manage.py dbcheck --before-migrate
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser
.venv/Scripts/python.exe manage.py runserver
```

En macOS/Linux use `.venv/bin/python`. La primera vez que una cuenta del personal inicia sesión,
configura una aplicación de autenticación (acceso en dos pasos) si `STAFF_MFA_REQUIRED` está activo.

### Cadenas de conexión a la base de datos

| Proveedor | Dónde encontrarla | Notas |
| --- | --- | --- |
| Supabase | Dashboard > Connect > **Session pooler** > URI | Puerto 5432, usuario `postgres.<project-ref>`. Ni el host directo (solo IPv6) ni el transaction pooler (6543). Los proyectos gratuitos se pausan tras una semana sin actividad. |
| Neon | Dashboard > Connect | Mantenga `sslmode=require&channel_binding=require`; use el host directo (sin pooler). |
| Aiven, Render y otros | La URI de conexión del servicio | Agregue `?sslmode=require` si no la incluye. |
| PostgreSQL local | `postgresql://usuario:contraseña@localhost:5432/basedatos?sslmode=disable` | Los modos TLS débiles solo se aceptan para localhost. |

Codifique los caracteres especiales de la contraseña (`@` > `%40`, `/` > `%2F`, `#` > `%23`).
`manage.py dbcheck` confirma la conexión, el TLS, el permiso para crear la base de pruebas, que la
base no contenga tablas de otro proyecto y (después de `migrate`) que todas las tablas tengan
seguridad a nivel de fila (RLS).

## Variables de entorno

| Variable | Obligatoria | Uso |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Sí, salvo con `DJANGO_DEBUG=true` | Clave de firma. Larga y aleatoria; distinta en cada entorno. |
| `DJANGO_DEBUG` | No | `true` solo en desarrollo local. Desactivado implica cookies seguras, redirección a HTTPS y HSTS. |
| `DJANGO_ALLOWED_HOSTS` | Producción | Nombres de host separados por comas (las plataformas de `config/platforms.py` se agregan solas). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Dominios propios | Orígenes `https://` separados por comas. |
| `DJANGO_TRUSTED_PROXY_COUNT` | Detrás de un proxy | Proxies que agregan a `X-Forwarded-For` (normalmente 1 en una plataforma). Un valor incorrecto permite falsear direcciones para el bloqueo y los límites. |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | No | Por defecto `HTTP_X_FORWARDED_PROTO,https`; `off` si ningún proxy termina el TLS. |
| `DJANGO_SECURE_SSL_REDIRECT` | No | Cambia la redirección a HTTPS (por defecto activa cuando debug está apagado). |
| `DJANGO_HSTS_SECONDS`, `DJANGO_HSTS_INCLUDE_SUBDOMAINS` | No | Política HSTS (por defecto 1 año, con subdominios). |
| `DJANGO_ADMIN_URL` | No | Ruta de la administración (por defecto `admin/`). |
| `DJANGO_TIME_ZONE`, `DJANGO_LANGUAGE_CODE` | No | Zona horaria del negocio e idioma del sitio (por defecto `America/Guatemala` y `es`). |
| `DJANGO_ENV_FILE` | No | Lee este archivo en lugar de `.env` (lo usan las pruebas). |
| `DATABASE_URL` | Sí (o `DB_*`) | URI de PostgreSQL; los parámetros se pasan al controlador. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Alternativa | Datos de conexión por separado. |
| `DB_SSLMODE`, `DB_SSLROOTCERT` | No | Modo TLS (por defecto `require`) y archivo de la CA, o `system` para el almacén del sistema. |
| `DB_CONN_MAX_AGE` | No | Segundos que se reutiliza una conexión (por defecto 60). |
| `SITE_NAME`, `SITE_TAGLINE`, `SITE_URL`, `SITE_EMAIL`, `SITE_PHONE`, `SITE_ADDRESS`, `SITE_HOURS`, `SITE_WHATSAPP` | `SITE_URL` en producción | Identidad y datos de contacto que se muestran en todas las páginas; `SITE_URL` se usa en los enlaces de los correos. El teléfono, WhatsApp y la dirección de Rénovée ya son los valores por defecto en `config/settings.py`; `SITE_EMAIL` vacío no se muestra. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | Para enviar correo | Configuración SMTP. Sin `EMAIL_HOST`, los correos se escriben en el registro. |
| `STAFF_MFA_REQUIRED` | No | Acceso en dos pasos para el personal (activo por defecto cuando un módulo guarda datos personales). |
| `PASSWORD_MIN_LENGTH` | No | Por defecto 12. |
| `LOGIN_FAILURE_LIMIT`, `LOGIN_LOCKOUT_MINUTES` | No | Bloqueo tras esta cantidad de contraseñas incorrectas (por defecto 5) durante este tiempo (por defecto 15). |
| `SESSION_IDLE_TIMEOUT_MINUTES`, `SESSION_ABSOLUTE_TIMEOUT_HOURS` | No | Por defecto 30 minutos de inactividad y 12 horas como máximo. |
| `LOG_LEVEL` | No | Por defecto `INFO`. |

Los módulos agregan sus propias variables a `.env.example` (sección «Business modules»).
`CRM_NOTIFY_EMAILS` define quién recibe un correo por cada mensaje del formulario; por defecto,
`SITE_EMAIL`. Mientras esté vacío, los mensajes solo se guardan en el CRM.

## Pruebas

```bash
.venv/Scripts/python.exe manage.py test --noinput
.venv/Scripts/coverage.exe run manage.py test --noinput && .venv/Scripts/coverage.exe report
```

Las pruebas cubren las funciones del núcleo y de cada módulo. Necesitan un rol de PostgreSQL que
pueda crear bases de datos: Django crea `test_<basedatos>` en el servidor configurado y la elimina
al terminar (`config/test_runner.py` usa `WITH (FORCE)` porque los poolers mantienen una conexión
abierta). Si el rol no puede crear bases de datos, ejecute las pruebas contra un PostgreSQL local.

Las pruebas usan la interfaz en inglés aunque el sitio esté en español (también lo define
`config/test_runner.py`), para que las comprobaciones de textos de la interfaz valgan para
cualquier sitio. Una prueba sobre una traducción elige su idioma con
`override_settings(LANGUAGE_CODE=...)`.

La integración continua (`.github/workflows/ci.yml`) se ejecuta en cada push: lint y formato con
ruff, revisión de migraciones, `check --deploy` con configuración de producción, pruebas con
cobertura (mínimo en `pyproject.toml`) en un contenedor de PostgreSQL 17, bandit, pip-audit, un
SBOM CycloneDX y una búsqueda de secretos con gitleaks.

## Despliegue

Sirve cualquier plataforma que ejecute Python o contenedores; el despliegue es un paso aparte.

- Construcción: `pip install --require-hashes -r requirements.txt && python manage.py collectstatic --noinput`
  (o el `Dockerfile`).
- Inicio: `gunicorn config.wsgi:application -c gunicorn.conf.py` (también en `Procfile`). Mantenga
  un solo worker con hilos (`WEB_CONCURRENCY=1`, `GUNICORN_THREADS=4`) para que los límites en
  memoria sean exactos.
- Paso de publicación: `python manage.py migrate` (antes o justo después de iniciar la nueva versión).
- Sondas: vida `/healthz` (sin base de datos), disponibilidad `/readyz` (con base de datos). Ambas
  responden por HTTP.
- Entorno: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `SITE_URL`, configuración de correo,
  `DJANGO_TRUSTED_PROXY_COUNT`, y `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` salvo
  que la plataforma esté en `config/platforms.py`. Nunca active `DJANGO_DEBUG` en producción.
- Después del primer despliegue: cree la cuenta del dueño (`createsuperuser`), inicie sesión y
  configure el acceso en dos pasos.

`docs/operations/RUNBOOK.md` cubre copias de seguridad, incidentes y rotación de secretos.

## Imágenes y fuentes

Coloque los originales del dueño en `src/images/` y ejecute `manage.py optimize_images`:

- quita los datos ocultos de los originales sin volver a codificar la imagen (ubicación GPS,
  cámara, autor, comentarios y credenciales de contenido C2PA), porque el repositorio es público;
- escribe copias WebP en `static/img/` (máximo 2000 px de ancho, orientación corregida, sin
  metadatos) y las lista en `static/img/CREDITS.md`;
- con `src/images/crops.json` publica solo una región de un original (por ejemplo, la foto dentro
  de un diseño para redes sociales con marco y teléfono). Ver `src/images/README.md`.

La prueba `test_committed_images_carry_no_hidden_data` falla si una imagen del repositorio
conserva datos ocultos.

Las fuentes se sirven desde el propio sitio: Bodoni Moda (títulos y logotipo) y Archivo (texto),
archivos `.woff2` y su licencia OFL en `static/fonts/`, reglas `@font-face` en
`static/css/fonts.css` y los tokens `--font-*` en `static/css/app.css`. El sillón del encabezado
(`static/img/sillon-renovee.webp`) se extrajo del logotipo del negocio.

## Traducciones

El sitio tiene un idioma (`LANGUAGE_CODE`, español). Los textos compartidos de la interfaz usan
las funciones de traducción de Django (catálogos en `core/locale`, `pages/locale` y `crm/locale`);
los mensajes propios de Django ya están traducidos. El contenido de las páginas se escribe
directamente en español.

## Dependencias

Los paquetes de ejecución están en `requirements.in`, fijados con hashes en `requirements.txt`
(pip-tools); las herramientas de desarrollo, en `requirements-dev.in` / `requirements-dev.txt`.
Después de editar un `.in`, vuelva a compilarlo (comando en CLAUDE.md) y suba ambos archivos.
Dependabot abre solicitudes de actualización cada semana; la integración continua debe pasar antes
de fusionarlas.
