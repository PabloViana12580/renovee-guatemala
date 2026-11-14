# Modelo de amenazas

Un modelo ligero (STRIDE) para este sitio web. Revíselo cada vez que se agregue un módulo o se
guarde un tipo de dato nuevo.

## Qué protegemos (inventario de datos)

| Dato | Dónde | Quién lo ve | Sensibilidad |
| --- | --- | --- | --- |
| Cuentas del personal (usuario, hash Argon2id de la contraseña, secreto de autenticación) | `auth_user`, `otp_totp_totpdevice` | Administradores | Alta |
| Sesiones e intentos de acceso (direcciones, usuarios) | `django_session`, `axes_*` | Administradores | Media |
| Datos de contacto y mensajes de clientes (CRM) | `crm_*` | Personal con permisos del CRM | Datos personales |
| Contenido e imágenes del sitio | repositorio (`templates/`, `static/`, `src/images/`) | Público | Público |
| Secretos (clave secreta, contraseñas de base de datos y correo) | entorno de la plataforma, `.env` local | Desarrolladores, plataforma | Alta |

## Límites de confianza

1. Navegador del visitante > sitio web (páginas públicas, formulario de contacto): entrada no confiable.
2. Navegador del personal > administración: autenticado con contraseña y verificación en dos pasos.
3. Sitio web > proveedor de PostgreSQL: TLS, credenciales desde el entorno.
4. Sitio web > proveedor de correo: TLS, credenciales desde el entorno.
5. Desarrollador > GitHub > plataforma de alojamiento: revisión de código, controles de integración
   continua, secretos nunca en el repositorio.
6. Sitio web > WhatsApp: los enlaces abren una conversación fuera del sitio; el sitio no envía datos.

## Amenazas y mitigaciones

| STRIDE | Amenaza | Mitigación (ver CONTROLS.md) |
| --- | --- | --- |
| Suplantación | Adivinar contraseñas o usar contraseñas filtradas contra cuentas del personal | C6 contraseñas, C7 bloqueo, C9 dos pasos, C20 registro |
| Suplantación | Falsear la dirección del cliente para evitar el bloqueo y los límites | C19 cantidad de proxies de confianza |
| Manipulación | Falsificación de solicitudes (CSRF) en acciones del personal | C12 CSRF, C11 cookies SameSite |
| Manipulación | Código malicioso inyectado en las páginas (XSS) | C17 escape automático, C14 CSP sin código en línea |
| Repudio | Acciones del personal sin rastro | Historial de la administración de Django, C20 registro de seguridad |
| Divulgación | Base de datos accesible por la API HTTP del proveedor | C4 seguridad a nivel de fila, C5 aislamiento |
| Divulgación | Datos interceptados en tránsito | C3 TLS de base de datos, C13 HTTPS y HSTS, C11 cookies |
| Divulgación | Secretos o datos personales subidos al repositorio público | C2 búsqueda de secretos, reglas de AGENTS.md |
| Divulgación | Metadatos de fotos que revelan ubicaciones, equipos o autores | C23 eliminación de datos ocultos de originales y copias |
| Divulgación | Páginas de error que muestran detalles internos | C21 errores genéricos, C1 DEBUG apagado |
| Denegación de servicio | Saturar el formulario de contacto o los registros | C18 límites de frecuencia, límites de reportes CSP |
| Elevación de privilegios | Personas sin rol de personal, o personal sin verificar, entrando a la administración | `StaffAdminSite`, C9 control de dos pasos |
| Cadena de suministro | Dependencias vulnerables o alteradas, acciones de CI comprometidas | C24 versiones fijadas con hash y auditorías, C25 SBOM, C28 acciones fijadas |

## Supuestos

- La plataforma de alojamiento termina el TLS y envía `X-Forwarded-Proto` / `X-Forwarded-For`
  (configure `DJANGO_TRUSTED_PROXY_COUNT`).
- El personal guarda en privado su teléfono de autenticación y su contraseña; el dueño revisa las
  cuentas cuando alguien deja la empresa (desactivando la cuenta).
- El proveedor de PostgreSQL cifra los datos en reposo y mantiene sus propias copias.
