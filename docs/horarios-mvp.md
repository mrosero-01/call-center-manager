# Horarios MVP

## Formato AstDB

El formato oficial de horarios por dia es:

```text
/horario/{astdb_family}/{day} = HH:MM-HH:MM|HH:MM-HH:MM
```

Ejemplo:

```text
/horario/callcenter_principal/Mon = 08:00-12:00|14:00-18:00
```

Un dia cerrado se representa con una lista vacia desde la API:

```json
{
  "day_of_week": "Sun",
  "ranges": []
}
```

## Locations De Prueba Y Reales

Para no tocar telefonos reales durante pruebas, usa dos `CallCenterLocation`:

```text
Prueba:
name: Django Test
code: django_test
astdb_family: django_test

Real:
name: Callcenter Principal
code: callcenter_principal
astdb_family: callcenter_principal
```

La API escribe en AstDB usando `astdb_family`. Por eso:

```text
django_test
```

sirve para pruebas sin afectar el dialplan real, mientras que:

```text
callcenter_principal
```

afecta el contexto real si `extensions.conf` lee esa familia.

## Importar Horarios Existentes

Para revisar que se importaria desde Asterisk:

```bash
cd backend
../.venv/bin/python manage.py import_astdb_schedules --tenant-code pas --tenant-name PAS --dry-run
```

Para importar:

```bash
../.venv/bin/python manage.py import_astdb_schedules --tenant-code pas --tenant-name PAS
```

El importador ignora claves legacy como:

```text
/horario/callcenter_principal/cierre
```

y solo importa dias validos:

```text
Mon Tue Wed Thu Fri Sat Sun
```
