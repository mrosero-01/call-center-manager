# Frontend Siptic Control Horarios

## Requisitos

Instala Node.js antes de ejecutar Angular.

Este proyecto apunta a Angular 22. Segun la tabla oficial de Angular, Angular
22 requiere una de estas familias de Node:

```text
^22.22.3 || ^24.15.0 || ^26.0.0
```

Compruebalo con:

```bash
node -v
npm -v
```

## Arranque local

Si ya intentaste instalar dependencias y fallo, limpia primero desde
`frontend/`:

```bash
rm -rf node_modules package-lock.json
npm install
```

No ejecutes `npm audit fix --force` en este MVP. Puede cambiar Angular a
versiones incompatibles entre si. Si `npm audit` muestra advertencias,
primero revisalas y corrige paquete por paquete.

En una terminal:

```bash
cd backend
../.venv/bin/python manage.py runserver
```

En otra terminal:

```bash
cd frontend
npm install
npm start
```

Angular levanta en:

```text
http://127.0.0.1:4200/
```

El proxy `proxy.conf.json` redirige `/api` hacia Django:

```text
http://127.0.0.1:8000/api
```

## Flujo

La app usa sesiones de Django:

```text
GET /api/auth/csrf/
POST /api/auth/login/
GET /api/me/
GET /api/locations/
GET /api/locations/{id}/schedule/
PUT /api/locations/{id}/schedule/
GET /api/locations/{id}/schedule-changes/
POST /api/auth/logout/
```
