# Comandos simples de operacion

Esta guia separa dos ideas que pueden confundirse:

| Negocio | Django | Asterisk / AstDB |
| --- | --- | --- |
| Cliente o contratista | `Tenant` | No aplica directo |
| Call center | `CallCenterLocation` | Normalmente un contexto o familia AstDB |
| Nombre tecnico del call center | `astdb_family` | `/horario/<astdb_family>/<dia>` |
| Horario del lunes | `OperationScheduleDay` | `/horario/callcenter_principal/Mon` |
| Guardar desde la web | `ScheduleSyncJob` | `DBPut` o `DBDel` por AMI |

## 1. La idea clave

Un contexto de Asterisk no tiene horario automaticamente.

Ejemplo de contexto:

```ini
[callcenter_principal]
```

Ejemplo de horario en AstDB:

```text
/horario/callcenter_principal/Mon : 08:00-12:00|14:00-18:00
```

La relacion existe porque el dialplan lee esa clave. Por orden y claridad,
usamos esta convencion:

```text
CallCenterLocation.astdb_family = nombre tecnico usado en AstDB
```

Idealmente el contexto de Asterisk y la familia AstDB se llaman igual:

```text
Contexto:      callcenter_principal
AstDB family:  callcenter_principal
Ruta AstDB:    /horario/callcenter_principal/Mon
```

## 2. Levantar el proyecto

Backend:

```bash
source .venv/bin/activate
cd backend
python manage.py runserver
```

Frontend, en otra terminal:

```bash
cd frontend
npm start
```

URLs:

```text
Angular:      http://localhost:4200/
Django Admin: http://127.0.0.1:8000/admin/
```

## 3. Comandos diarios

Ver que hay en Asterisk:

```bash
cd backend
python manage.py inspect_asterisk
```

Este comando muestra dos cosas:

- Contextos del dialplan.
- Familias de horarios encontradas en `/horario`.

Ver solo horarios AstDB:

```bash
python manage.py inspect_asterisk --horario
```

Ver solo contextos:

```bash
python manage.py inspect_asterisk --contexts
```

Probar conexion AMI:

```bash
python manage.py check_ami
```

Hace una escritura temporal en AstDB, la lee y luego la borra.

## 4. Importar horarios desde Asterisk a Django

Primero simular:

```bash
python manage.py import_astdb_schedules --tenant-code pas --tenant-name "PAS" --dry-run
```

Esto no guarda nada. Solo muestra que importaria.

Importar una familia concreta:

```bash
python manage.py import_astdb_schedules --tenant-code pas --tenant-name "PAS" --family callcenter_principal
```

Importar todo lo encontrado bajo `/horario`:

```bash
python manage.py import_astdb_schedules --tenant-code pas --tenant-name "PAS"
```

Regla practica: en servidores reales, primero usar siempre `--dry-run`.

## 5. Ver lo que ya existe en Django

Ver call centers:

```bash
python manage.py shell -c "from control_horarios.models import CallCenterLocation; [print(l.id, l.name, l.astdb_family, l.tenant.code) for l in CallCenterLocation.objects.select_related('tenant')]"
```

Ver clientes:

```bash
python manage.py shell -c "from control_horarios.models import Tenant; [print(t.id, t.name, t.code) for t in Tenant.objects.all()]"
```

Ver usuarios:

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); [print(u.id, u.username, u.is_superuser, u.is_staff) for u in User.objects.all()]"
```

Nota: si Django muestra `19 objects imported automatically`, eso no significa
que se importaron 19 call centers. Es solo el shell cargando modelos.

## 6. Sincronizar Django hacia Asterisk

Procesar cambios pendientes:

```bash
python manage.py process_schedule_sync_jobs
```

Reintentar trabajos fallidos:

```bash
python manage.py process_schedule_sync_jobs --retry-failed
```

Cuando guardas un horario desde la web, Django queda como fuente de verdad y
crea un `ScheduleSyncJob`. Este comando toma esos jobs y escribe en AstDB por
AMI.

## 7. Comandos directos en Asterisk

Entrar a consola:

```bash
asterisk -rvvvvv
```

Ver horarios:

```bash
database show horario
```

Ver una familia concreta:

```bash
database show horario/callcenter_principal
```

Borrar todos los horarios de prueba:

```bash
asterisk -rx "database deltree horario"
```

Este ultimo comando es destructivo. Usarlo solo en laboratorio o con backup.

## 8. Flujo recomendado

1. Revisar Asterisk:

```bash
python manage.py inspect_asterisk
```

2. Simular importacion:

```bash
python manage.py import_astdb_schedules --tenant-code pas --tenant-name "PAS" --dry-run
```

3. Importar de verdad si todo se ve correcto.

4. Revisar call centers en Django Admin o en la interfaz de superadmin.

5. Editar horarios desde Angular.

6. Procesar sincronizacion:

```bash
python manage.py process_schedule_sync_jobs
```

7. Confirmar en Asterisk:

```bash
asterisk -rx "database show horario"
```

Desde la interfaz de superadmin, el flujo equivalente es:

1. Ir a `Administracion`.
2. Pulsar `Revisar servidor`.
3. Revisar la tabla de inventario:
   - nombre tecnico
   - si existe como contexto
   - si tiene horario AstDB
   - si ya existe en Django
   - accion sugerida
4. Seleccionar las familias con horario.
5. Pulsar `Vista previa seleccionados`.
6. Pulsar `Importar seleccionados`.

Esto evita escribir nombres tecnicos a mano y reduce errores al trabajar con
servidores Asterisk que ya tienen varios contextos y horarios.

Antes de importar, la interfaz exige una vista previa. El boton final queda como
`Confirmar importacion` para evitar cambios accidentales.

## 9. Regla de produccion

Django/PostgreSQL debe ser la fuente de verdad:

- usuarios
- tenants
- permisos
- call centers
- horarios
- auditoria

AstDB debe ser una copia operativa para Asterisk:

- formato simple
- lectura rapida desde dialplan
- una clave por call center y dia

## 10. Limpiar pruebas sin perder historial

No se recomienda borrar call centers que ya tienen horarios, auditoria o jobs.
Esas tablas dejan evidencia de cambios y sincronizaciones.

Para limpiar la interfaz:

1. Entrar como superadmin.
2. Ir a `Administracion`.
3. En `Call centers`, usar `Ocultar`.

Un call center oculto:

- no aparece en la pantalla normal de `Horarios`
- no aparece para admins de tenant
- conserva auditoria, horarios y jobs
- puede restaurarse desde `Administracion`

Si importas desde AstDB una familia que ya existe pero esta oculta, el sistema
la reactiva automaticamente.

## 11. Refrescar un horario desde Asterisk

En la pantalla `Horarios` existe la accion:

```text
Leer desde Asterisk
```

Esa accion lee `/horario/<astdb_family>/*` desde AstDB y actualiza Django con
lo que realmente tiene el servidor en ese momento.

Usarla cuando:

- alguien modifico AstDB fuera de la aplicacion
- quieres comprobar el estado real antes de editar
- acabas de importar horarios y quieres validar una locacion concreta

Si un dia no existe en AstDB, se considera cerrado/no configurado y no se
mantiene una version vieja en Django.

Tambien existe la accion:

```text
Comparar con Asterisk
```

Esa accion no modifica datos. Solo muestra si Django y AstDB tienen el mismo
horario o si hay diferencias por dia.

## 12. Estado AMI y permisos

En `Administracion` se muestra una tarjeta `Asterisk AMI` con:

- estado de conexion
- host y puerto
- latencia aproximada
- mensaje de respuesta o error

Roles actuales:

- `superadmin`: administra todo
- `admin` de tenant: ve y modifica horarios de su tenant
- `operator`: ve horarios de su tenant en modo solo lectura

Cuando un usuario abre un horario y otro usuario lo modifica antes de guardar,
la API rechaza el guardado y pide refrescar. Esto evita sobrescribir cambios
recientes con una version vieja.

## 13. Limpieza segura de jobs

Para revisar cuantos jobs sincronizados antiguos se limpiarian:

```bash
python manage.py prune_schedule_sync_jobs --older-than-days 90 --dry-run
```

Para eliminarlos:

```bash
python manage.py prune_schedule_sync_jobs --older-than-days 90
```

Este comando solo borra jobs `synced` antiguos. No borra pendientes ni fallidos.
