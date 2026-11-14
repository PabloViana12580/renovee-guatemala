# Controles de seguridad y calidad

Qué protege esta aplicación, dónde está implementado, cómo se verifica y cómo se relaciona con los
marcos que sigue el proyecto. «Relacionado con» significa que el control contribuye a ese
requisito o práctica; no es una declaración de cumplimiento ni de certificación, que aplican a
organizaciones y requieren una auditoría.

Objetivo: **OWASP ASVS 5.0 nivel 1**, más los requisitos de nivel 2 indicados abajo. Los
identificadores de requisitos vienen de la exportación oficial de ASVS 5.0.0 (github.com/OWASP/ASVS).
NIST SSDF = prácticas de SP 800-218 v1.1; NIST CSF = subcategorías de CSF 2.0; ISO 27002 =
controles de ISO/IEC 27002:2022. Los identificadores y nombres de archivos, pruebas y requisitos se
mantienen en inglés.

## Controles

| # | Control | Implementación | Verificado por | ASVS 5.0 | SSDF | CSF 2.0 | ISO 27002 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | Configuración segura por defecto: DEBUG apagado salvo que se active, clave secreta obligatoria, hosts desde el entorno | `config/settings.py` | `core/tests/test_settings.py`, CI `check --deploy` | V13.4.2 | PW.9 | PR.PS-01 | 8.9 |
| C2 | Secretos solo en variables de entorno; repositorio revisado | `.env` (ignorado por git), `.env.example` | CI gitleaks, secret scanning de GitHub con push protection | V13.3.2 | PS.1 | PR.DS-01 | 5.17, 8.4 |
| C3 | Conexiones cifradas a la base de datos (TLS obligatorio salvo localhost) | `database_from_env()` | `test_settings.DatabaseConfigTests`, `manage.py dbcheck` | V12.3.1 | PW.9 | PR.DS-02 | 8.24, 8.20 |
| C4 | Seguridad a nivel de fila en todas las tablas (sin acceso directo a los datos por API) | `core/rls.py` (después de cada migrate) | `core/tests/test_database.py`, `dbcheck` | V8.3.1 | PW.9 | PR.AA-05 | 8.3, 5.23 |
| C5 | Una base de datos por proyecto (aislamiento) | verificación de aislamiento de `dbcheck` | `test_database.DbcheckCommandTests` | V8.2.2 | PO.5 | PR.IR-01 | 8.31 |
| C6 | Contraseñas: mínimo 12 caracteres, lista de contraseñas comunes, sin reglas de composición, hash Argon2id | `AUTH_PASSWORD_VALIDATORS`, `PASSWORD_HASHERS` | `test_auth.PasswordStorageTests` | V6.2.1, V6.2.4, V6.2.5, V6.2.9, V11.4.2 | PW.5 | PR.AA-01 | 5.17, 8.5 |
| C7 | Protección contra fuerza bruta: bloqueo por usuario y dirección | configuración de django-axes, `registration/locked_out.html` | `test_auth.LoginTests.test_lockout_after_repeated_failures` | V6.3.1, V6.1.1 | PW.5 | PR.AA-03 | 8.5 |
| C8 | Errores de acceso genéricos (no revelan si una cuenta existe) | `AuthenticationForm` de Django | `test_auth...test_wrong_password_gives_one_generic_message` | V6.3.8 (L3) | PW.5 | PR.AA-03 | 8.5 |
| C9 | Acceso en dos pasos (TOTP) para el personal cuando se guardan datos personales; códigos de un solo uso; restablecimiento solo por un administrador | `core/mfa.py`, `core/account_views.py`, `StaffMFAMiddleware`, `StaffAdminSite`, `reset_mfa` | `core/tests/test_mfa.py` | V6.3.3, V6.5.1, V6.5.3, V6.5.5, V6.4.4 | PW.5 | PR.AA-03 | 8.5, 8.2 |
| C10 | Sesiones: sesión nueva al iniciar, 30 min de inactividad, 12 h como máximo, fin al cerrar sesión o desactivar la cuenta | `SESSION_*`, `SessionLifetimeMiddleware`, `StaffLogoutView` | `test_auth.SessionLifetimeTests`, `LogoutTests` | V7.2.4, V7.3.1, V7.3.2, V7.4.1, V7.4.2 | PW.5 | PR.AA-03 | 8.5 |
| C11 | Cookies: Secure, HttpOnly, SameSite=Lax, prefijo `__Host-` en producción | `SESSION_COOKIE_*`, `CSRF_COOKIE_*` | `test_settings.ProductionSettingsTests` | V3.3.1, V3.3.2, V3.3.3, V3.3.4 | PW.9 | PR.DS-02 | 8.24 |
| C12 | Protección CSRF en todos los formularios, cierre de sesión solo por POST | middleware CSRF de Django | `test_auth.LogoutTests`, pruebas del formulario del CRM | V3.5.1 | PW.5 | PR.DS-02 | 8.26 |
| C13 | Solo HTTPS: redirección, HSTS de 1 año con subdominios | `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*` | `test_headers` | V3.4.1, V4.1.2, V12.2.1 | PW.9 | PR.DS-02 | 8.24 |
| C14 | Content Security Policy solo `'self'`, sin código en línea, frame-ancestors none, reporte de violaciones | django-csp, Bootstrap y fuentes servidos desde el sitio, `core.views.csp_report` | `test_headers.SecurityHeaderTests` | V3.4.3, V3.4.6, V3.2.1 | PW.5 | PR.PS-01 | 8.26 |
| C15 | Otros encabezados: nosniff, Referrer-Policy same-origin, COOP, X-Frame-Options DENY, Permissions-Policy | configuración, `PermissionsPolicyMiddleware` | `test_headers` | V3.4.4, V3.4.5 | PW.9 | PR.PS-01 | 8.26 |
| C16 | Borrado de datos del navegador al cerrar sesión | `Clear-Site-Data` en `StaffLogoutView` | `test_auth...test_logout_tells_the_browser_to_clear_site_data` | V14.3.1 | PW.5 | PR.DS-10 | 8.12 |
| C17 | Codificación de salida: escape automático de Django; códigos QR como SVG en línea sin scripts | plantillas, `core/mfa.py` | `test_mfa...test_qr_code_is_inline_svg_without_scripts`, escape en el CRM | V1.2.1, V3.2.2 | PW.5 | PR.DS-10 | 8.28 |
| C18 | Contra automatización en formularios públicos: campo trampa, tiempo mínimo de llenado, límites por dirección | `core/spam.py` | `core/tests/test_spam.py`, pruebas del formulario del CRM | V2.4.1 | PW.5 | DE.CM-09 | 8.16 |
| C19 | Dirección del cliente confiable detrás de proxies (sin falsear bloqueos ni límites) | `core/net.py`, `DJANGO_TRUSTED_PROXY_COUNT` | `test_spam.ClientIpTests` | V15.3.4 | PW.9 | PR.PS-01 | 8.20 |
| C20 | Registro de eventos de seguridad (accesos, fallos, bloqueos, dos pasos, CSP, spam), horas UTC, sin secretos | `core/signals.py`, `LOGGING`, `core/logformat.py` | `test_operations.SecurityLogTests` | V16.3.1, V16.3.3, V16.2.1, V16.2.2, V16.2.5, V16.4.1 | RV.1 | PR.PS-04, DE.CM-09 | 8.15, 8.16 |
| C21 | Páginas de error genéricas sin detalles; página 500 independiente | `templates/4xx-5xx.html`, `error_base.html` | `test_operations.ErrorPageTests` | V16.5.1, V16.5.3 | PW.9 | PR.PS-01 | 8.26 |
| C22 | Sondas de salud y disponibilidad | `/healthz`, `/readyz` | `test_operations.ProbeTests` | V16.5.2 | PW.9 | DE.CM-09 | 8.16 |
| C23 | Datos ocultos eliminados de las imágenes (ubicación, cámara, autor, comentarios, credenciales C2PA), en los originales del repositorio y en las copias publicadas | `core/imagemeta.py`, `optimize_images` | `test_images`, incluida `test_committed_images_carry_no_hidden_data` | V14.2.3 | PW.5 | PR.DS-01 | 5.34 |
| C24 | Dependencias fijadas con hash; actualizaciones semanales; auditoría de vulnerabilidades en CI | `requirements*.txt` (pip-tools), Dependabot, pip-audit | CI | V15.1.1, V15.2.1 | PW.4, RV.1 | ID.RA-01, PR.PS-02 | 8.8 |
| C25 | Lista de componentes de software (SBOM) por compilación | pip-audit CycloneDX | artefacto `sbom` de CI | V15.1.2 | PS.3 | ID.AM-08 | 8.8 |
| C26 | Análisis estático y de código | ruff (con reglas de seguridad), bandit, CodeQL | CI, code scanning de GitHub | - | PW.7 | ID.RA-01 | 8.29 |
| C27 | Pruebas automáticas y cobertura mínima sobre PostgreSQL | `manage.py test`, coverage `fail_under` | CI | - | PW.8 | PR.PS-06 | 8.29 |
| C28 | Rama principal protegida (sin force-push ni borrado), acciones de CI fijadas, token de CI con mínimos privilegios | ruleset de GitHub, `.github/workflows/ci.yml` | configuración de GitHub | - | PS.1, PO.3 | PR.PS-06 | 8.4, 8.32 |
| C29 | Divulgación de vulnerabilidades y plazos de corrección | `SECURITY.md`, reporte privado de vulnerabilidades | configuración de GitHub | V15.1.1 | RV.1, RV.2 | ID.RA-08 | 8.8, 5.24 |
| C30 | Procedimientos de cambio, publicación, incidentes, copias y rotación de secretos | plantilla de PR, `CHANGELOG.md`, etiquetas, `docs/operations/RUNBOOK.md` | Revisión | - | PO.1 | RS.MA-01, RC.RP-01, PR.DS-11 | 8.32, 5.26, 8.13 |
| C31 | Modelo de amenazas e inventario de datos | `docs/security/THREAT_MODEL.md` | Revisión en cada cambio de módulo | V14.1.1 | PW.1 | ID.AM-07 | 5.34, 8.26 |

## Controles de los módulos

| # | Control | Implementación | Verificado por | ASVS 5.0 | SSDF | CSF 2.0 | ISO 27002 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CRM-1 | CRM: validación y límites del formulario de contacto (longitudes, formato del correo) | `crm/forms.py` | `crm/tests/test_contact_form.py` | V2.2.1 | PW.5 | PR.DS-10 | 8.26 |
| CRM-2 | CRM: inyección de fórmulas neutralizada en las exportaciones CSV | `crm/exports.py` | `crm/tests/test_admin.py` | V1.2.10 (L3) | PW.5 | PR.DS-10 | 8.28 |
| CRM-3 | CRM: consentimiento de publicidad registrado con fecha y origen; exportación de datos por persona para solicitudes de acceso | `crm/models.py`, `crm/exports.py` | `crm/tests/test_services.py`, `test_admin.py` | V14.2.4 | PW.1 | ID.AM-07 | 5.34 |
| CRM-4 | CRM: inyección en encabezados de correo prevenida; una caída del correo nunca pierde un mensaje | `core/notifications.py`, `crm/services.py` | `crm/tests/test_services.py` | V16.5.2 | PW.5 | PR.DS-01 | 8.26 |
| CRM-5 | CRM: las exportaciones requieren el permiso de lectura y quedan registradas | `crm/admin.py` | `crm/tests/test_admin.py` | V8.2.1, V16.3.3 | PW.5 | PR.AA-05 | 5.15, 8.15 |

Al quitar un módulo, elimine sus filas; al agregar uno, agregue las filas del módulo.

## Otros marcos

| Marco | Cómo aplica aquí |
| --- | --- |
| CIS Benchmarks | Solo las partes aplicables: las recomendaciones de TLS y acceso del CIS PostgreSQL Benchmark (C3, C4; en producción se recomienda un rol con privilegios mínimos) y las de código fuente, dependencias y pipeline de la CIS Software Supply Chain Security Guide (C24-C28). Los benchmarks de sistema operativo y contenedores aplican a la plataforma de alojamiento, no a este repositorio. |
| ISO/IEC 25010:2023 | Seguridad: C6-C21. Fiabilidad (ausencia de fallos, disponibilidad, recuperabilidad): C22, C27, C30. Mantenibilidad (modularidad, capacidad de prueba y de análisis): estructura de módulos, C26, C27. Capacidad de interacción: accesibilidad básica en las plantillas (etiquetas, foco, enlace para saltar al contenido, contraste). Compatibilidad y flexibilidad: configuración independiente de la plataforma, `Procfile`, `Dockerfile`. |
| ITIL 4 | Habilitación de cambios: plantilla de PR con riesgo y reversión, control de CI. Gestión de publicaciones: etiquetas SemVer, `CHANGELOG.md`, publicaciones de GitHub. Gestión de incidentes y de seguridad de la información: `RUNBOOK.md`, `SECURITY.md`. Gestión de la configuración: `.starter.json`, dependencias fijadas. |
| NIST CSF 2.0 Govern | Los roles y políticas corresponden al dueño; este repositorio aporta la evidencia técnica (este archivo, el modelo de amenazas y el manual de operación). |

## Brechas conocidas y decisiones

| Requisito | Estado |
| --- | --- |
| ASVS V6.2.12 (L2) verificar contraseñas filtradas | No implementado: requiere un servicio externo; la lista de contraseñas comunes (C6) cubre el nivel 1. |
| ASVS V12.3.2 (L2) validar el certificado del servidor de base de datos | Recomendado según el proveedor: `DB_SSLMODE=verify-full` con `DB_SSLROOTCERT` (archivo de la CA del proveedor, o `system`). Por defecto `require`. |
| ASVS V13.3.1 (L2) bóveda de secretos | Los secretos viven en las variables de entorno cifradas de la plataforma de alojamiento. |
| ASVS V16.4.3 (L2) registros enviados a un sistema separado | Los registros salen por stdout; conecte el drenaje de registros de la plataforma en cada despliegue. |
| ASVS V7.4.5 / V7.5.2 (L2) listar y terminar sesiones individuales | Desactivar una cuenta termina todas sus sesiones (C10); no hay gestión por sesión. |
| ASVS V3.4.3 report-uri de CSP | Usa `report-uri` (ampliamente compatible) en lugar de la Reporting API más reciente. |
