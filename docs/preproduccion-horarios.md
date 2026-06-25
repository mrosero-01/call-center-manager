# Preproduccion: control de horarios

Esta guia resume el flujo actual para revisarlo antes de probar con telefonos reales.

## Mapa del flujo

1. Angular arma bloques de operacion por dias y franjas.
2. La API valida permisos multi-tenant.
3. El caso de uso normaliza y valida reglas de horario.
4. Django guarda el horario, crea auditoria y encola un `ScheduleSyncJob`.
5. `process_schedule_sync_jobs` publica el job en AstDB mediante AMI.
6. El dialplan de Asterisk lee `/horario/<astdb_family>/<Dia>`.

## Archivos que conviene entender en orden

1. `backend/control_horarios/models.py`
   - `Tenant`: cliente o contratista.
   - `CallCenterLocation`: unidad operativa que Asterisk consulta.
   - `OperationSchedule`: horario vigente.
   - `ScheduleChangeLog`: auditoria.
   - `ScheduleSyncJob`: outbox de sincronizacion hacia Asterisk.

2. `backend/control_horarios/permissions.py`
   - Define que puede ver/modificar cada usuario.

3. `backend/control_horarios/application/use_cases.py`
   - Orquesta el cambio de horario sin depender de Django ni Asterisk.

4. `backend/control_horarios/infrastructure/django/repositories.py`
   - Guarda horario, auditoria y job pendiente en una transaccion.

5. `backend/control_horarios/infrastructure/asterisk/schedule_publisher.py`
   - Traduce jobs a acciones AMI `DBPut` o `DBDel`.

6. `frontend/src/app/features/dashboard/dashboard.component.ts`
   - Convierte bloques visuales a payload de API.

## Checklist antes de probar telefonos

```bash
cd backend
source ../.venv/bin/activate
python manage.py check
python manage.py test control_horarios
python manage.py check_ami
```

```bash
cd frontend
source ~/.nvm/nvm.sh
npm audit --audit-level=high
npm run build -- --configuration production
npx ng test --watch=false --browsers=ChromeHeadless
```

## Prueba funcional segura

1. Entrar con usuario admin tenant.
2. Cambiar solo un dia.
3. Usar `Vista previa AstDB`.
4. Guardar con motivo claro.
5. Confirmar estado `Pendiente`.
6. Procesar outbox:

```bash
python manage.py process_schedule_sync_jobs --retry-failed
```

7. Confirmar en Asterisk:

```asterisk
database show horario
```

8. Confirmar que el estado queda `Sincronizado`.

## Configuracion minima de produccion

```env
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=una-clave-larga-y-aleatoria
DJANGO_ALLOWED_HOSTS=tu-dominio.com
COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
DB_ENGINE=postgresql
ASTERISK_AMI_ENABLED=true
```

## Riesgos controlados por el diseno actual

- Si AMI falla, el horario no se pierde: queda guardado y el job queda `failed`.
- Si se guarda un cambio mas reciente, un job viejo no debe sobrescribir el estado del horario.
- El frontend no decide permisos; el backend valida tenant y rol.
- La auditoria no se puede borrar desde Django admin.
