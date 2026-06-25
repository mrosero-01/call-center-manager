# Despliegue de produccion

Esta guia deja el sistema listo para operar con PostgreSQL, Gunicorn, systemd, worker de sincronizacion y backups.

## 1. Preparar `.env`

Usar valores reales, no los de ejemplo:

```env
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=clave-larga-aleatoria
DJANGO_ALLOWED_HOSTS=panel.tudominio.com
CSRF_TRUSTED_ORIGINS=https://panel.tudominio.com
COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
TRUST_PROXY_SSL_HEADER=true

DB_ENGINE=postgresql
DB_NAME=call_center_manager
DB_USER=call_center_manager
DB_PASSWORD=clave-larga-db
DB_HOST=127.0.0.1
DB_PORT=5432

ASTERISK_AMI_ENABLED=true
ASTERISK_AMI_HOST=IP_ASTERISK
ASTERISK_AMI_PORT=5038
ASTERISK_AMI_USERNAME=siptic_scheduler
ASTERISK_AMI_PASSWORD=clave-larga-ami
```

## 2. PostgreSQL

```sql
CREATE USER call_center_manager WITH PASSWORD 'clave-larga-db';
CREATE DATABASE call_center_manager OWNER call_center_manager;
```

Luego:

```bash
cd /home/miguel/Siptic-p/call-center-manager
source .venv/bin/activate
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 3. Checks antes de encender servicios

```bash
python manage.py check --deploy
python manage.py check_ami
python manage.py process_schedule_sync_jobs --retry-failed
```

Frontend:

```bash
cd frontend
source ~/.nvm/nvm.sh
npm ci
npm audit --audit-level=high
npm run build -- --configuration production
```

## 4. systemd

Copiar unidades:

```bash
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

Activar API:

```bash
sudo systemctl enable --now call-center-manager.service
sudo systemctl status call-center-manager.service
```

Activar worker de horarios:

```bash
sudo systemctl enable --now call-center-schedule-sync.timer
systemctl list-timers | grep call-center
```

Activar backup diario:

```bash
sudo systemctl enable --now call-center-postgres-backup.timer
systemctl list-timers | grep postgres-backup
```

Logs:

```bash
journalctl -u call-center-manager.service -f
journalctl -u call-center-schedule-sync.service -f
```

## 5. Nginx y HTTPS

La API Django debe quedar detras de Nginx/HTTPS. Gunicorn escucha local:

```text
127.0.0.1:8000
```

Nginx debe servir:

- `/api/` hacia Gunicorn.
- `/admin/` hacia Gunicorn.
- frontend Angular desde `frontend/dist/siptic-call-center-manager/browser`.
- `/static/` desde `backend/staticfiles`.

Plantilla incluida:

```bash
sudo cp deploy/nginx/call-center-manager.conf /etc/nginx/sites-available/call-center-manager.conf
sudo ln -s /etc/nginx/sites-available/call-center-manager.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Antes de usarla, cambiar `panel.tudominio.com` por el dominio real y configurar HTTPS.

## 6. AMI restringido

En `/etc/asterisk/manager.conf`:

```ini
[siptic_scheduler]
secret=clave-larga-ami
deny=0.0.0.0/0.0.0.0
permit=IP_SERVIDOR_DJANGO/255.255.255.255
read=system
write=system
```

Recargar:

```bash
asterisk -rx "manager reload"
```

El puerto `5038` no debe estar abierto a internet. Permitir solo IP del servidor Django.

## 7. Backup y restauracion

Backup manual:

```bash
./scripts/backup_postgres.sh
```

Restaurar en una base vacia:

```bash
pg_restore --clean --if-exists --dbname=call_center_manager archivo.dump
```

La restauracion debe probarse antes de produccion real.

## 8. Prueba funcional final

1. Entrar con superadmin.
2. Crear tenant.
3. Crear location con `astdb_family`.
4. Crear admin tenant.
5. Entrar con admin tenant.
6. Usar `Vista previa AstDB`.
7. Guardar horario.
8. Confirmar estado `Pendiente`.
9. Esperar worker o correr:

```bash
python manage.py process_schedule_sync_jobs --retry-failed
```

10. Confirmar estado `Sincronizado`.
11. En Asterisk:

```asterisk
database show horario
```

12. Probar llamada abierta/cerrada.
