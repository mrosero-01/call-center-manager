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
