# Manual de operación

Pasos prácticos para operar el sitio: publicaciones, copias de seguridad, incidentes y secretos.
Las horas de los registros están en UTC.

## Publicaciones y cambios

1. Trabaje en una rama y abra una solicitud de cambio con la plantilla (cambio, riesgo, cómo
   revertirlo, comprobaciones).
2. La integración continua debe pasar. Fusione en `main`.
3. Actualice `CHANGELOG.md`, etiquete la versión (`git tag v0.2.0 && git push --tags`) y cree la
   publicación de GitHub desde la etiqueta.
4. Despliegue y luego ejecute `python manage.py migrate` en el servidor.
5. Compruebe que `/readyz` responde `ready` e inicie sesión en la administración.

Para revertir: vuelva a desplegar la etiqueta anterior. Si la versión ejecutó una migración que
eliminó o cambió datos, restaure la copia tomada antes (ver abajo).

## Copias de seguridad y restauración

Antes de cualquier migración que elimine o cambie datos, y al menos cada semana:

```bash
pg_dump --format=custom --no-owner --file=backup-$(date +%Y%m%d).dump "$DATABASE_URL"
```

Guarde el archivo en un lugar privado (contiene datos personales de clientes), nunca en el
repositorio. Para restaurar en una base de datos vacía:

```bash
pg_restore --no-owner --dbname="$TARGET_DATABASE_URL" backup-YYYYMMDD.dump
```

Después ejecute `python manage.py migrate` (se vuelve a aplicar la seguridad a nivel de fila) y
`python manage.py dbcheck`. Revise también las copias de su proveedor (por ejemplo, el plan
gratuito de Supabase no tiene recuperación a un momento dado, y los proyectos gratuitos se pausan
tras una semana sin actividad: se reanudan desde el panel).

## Incidentes

1. **Detectar**: `/readyz` falla, errores en los registros de la plataforma, líneas del registro
   `security` (muchos `auth.login_failed` / `auth.locked_out`, `csp.violation`, `spam.rejected`)
   o un aviso de alguien.
2. **Contener**: si una cuenta puede estar comprometida, desactívela en la administración (sus
   sesiones terminan de inmediato) y ejecute `python manage.py reset_mfa <usuario>`. Si se filtró
   un secreto, rótelo (ver abajo). Si el sitio está bajo ataque, póngalo en mantenimiento desde la
   plataforma.
3. **Recuperar**: corrija, publique con el proceso normal y restaure datos de una copia si hace
   falta.
4. **Aprender**: abra un issue (plantilla de error o incidente) con la cronología, la causa y las
   acciones pendientes. Si se expusieron datos personales, el dueño puede tener obligaciones
   legales de aviso; documente qué datos, de quién y cuándo.

## Rotación de secretos

| Secreto | Cómo rotarlo | Efecto |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Genere un valor aleatorio nuevo, configúrelo en la plataforma y vuelva a desplegar. | Se cierran todas las sesiones; los tokens de los formularios se renuevan. |
| Contraseña de la base de datos | Cámbiela en el proveedor, actualice `DATABASE_URL` y vuelva a desplegar. | Breve interrupción mientras la aplicación reinicia. |
| Contraseña o clave del correo | Cree una nueva en el proveedor de correo, actualice la variable, vuelva a desplegar y revoque la anterior. | Ninguno. |
| Contraseña del personal | La persona la cambia en la administración (arriba a la derecha). | Se cierran sus otras sesiones. |
| Teléfono de autenticación perdido | `python manage.py reset_mfa <usuario>` después de confirmar quién lo pide. | Vuelve a configurar el acceso en dos pasos en su próximo inicio de sesión. |

## Personal bloqueado

Los bloqueos vencen después de `LOGIN_LOCKOUT_MINUTES` (por defecto 15). Para desbloquear antes,
elimine los intentos de acceso de ese usuario en la administración (Seguridad de acceso > Intentos
de acceso).
