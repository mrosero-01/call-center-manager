# Checklist de pruebas MVP

Usa este checklist para validar el flujo completo antes de pasar a una prueba
mas seria con telefonos reales.

## 1. Sesion y permisos

- [ ] Entrar con usuario superadmin.
- [ ] Ver menu `Administracion`.
- [ ] Cerrar sesion.
- [ ] Confirmar que volver atras no deja entrar al panel.
- [ ] Entrar con usuario admin de tenant.
- [ ] Confirmar que no ve `Administracion`.
- [ ] Confirmar que solo ve call centers de su tenant.
- [ ] Entrar con usuario operador si existe.
- [ ] Confirmar que ve horarios en modo solo lectura.

## 2. Estado Asterisk

- [ ] Ir a `Administracion`.
- [ ] Revisar tarjeta `Asterisk AMI`.
- [ ] Confirmar que muestra conectado, host, puerto y latencia.
- [ ] Pulsar `Revisar AMI`.
- [ ] Si falla, revisar `.env`, `manager.conf`, `permit/deny`, usuario y clave.

## 3. Inventario e importacion

- [ ] Pulsar `Revisar servidor`.
- [ ] Confirmar que la tabla principal solo muestra familias con horario AstDB.
- [ ] Desplegar `Ver contextos sin horario`.
- [ ] Confirmar que los contextos sin `/horario` no estorban el flujo principal.
- [ ] Seleccionar una o varias familias con horario.
- [ ] Pulsar `Vista previa`.
- [ ] Revisar cuantas locaciones se crean, actualizan o restauran.
- [ ] Pulsar `Confirmar importacion`.
- [ ] Confirmar mensaje de importacion completa.
- [ ] Confirmar que el call center aparece en `Registrados`.
- [ ] Pulsar `Abrir` en el call center importado.

## 4. Horarios

- [ ] Confirmar que el call center importado aparece en `Horarios`.
- [ ] Revisar que los dias y franjas coincidan con AstDB.
- [ ] Pulsar `Comparar con Asterisk`.
- [ ] Confirmar si Django y Asterisk estan alineados.
- [ ] Pulsar `Leer desde Asterisk`.
- [ ] Confirmar que Django se actualiza con el horario real del servidor.

## 5. Guardado y sincronizacion

- [ ] Modificar una franja.
- [ ] Escribir motivo obligatorio.
- [ ] Guardar.
- [ ] Confirmar mensaje `Horario guardado y sincronizado con Asterisk`.
- [ ] Confirmar en Asterisk:

```bash
asterisk -rx "database show horario"
```

- [ ] Confirmar que `Jobs AstDB` no queda con pendientes inesperados.

## 6. Auditoria

- [ ] Revisar panel `Ultimos cambios`.
- [ ] Confirmar usuario, fecha, motivo y dias modificados.
- [ ] Confirmar que el motivo escrito aparece correctamente.

## 7. Ocultar/restaurar call centers

- [ ] En `Administracion`, ocultar un call center de prueba.
- [ ] Confirmar que desaparece de `Horarios`.
- [ ] Restaurarlo.
- [ ] Confirmar que vuelve a aparecer en `Horarios`.

## 8. Pruebas de error

- [ ] Probar con AMI apagado o clave incorrecta en entorno de prueba.
- [ ] Confirmar que la UI muestra error entendible.
- [ ] Confirmar que el horario queda guardado en Django si falla sincronizacion.
- [ ] Confirmar que el job queda fallido y puede reintentarse.

## 9. Comandos utiles

Ver horarios en Asterisk:

```bash
asterisk -rx "database show horario"
```

Procesar jobs manualmente:

```bash
cd backend
python manage.py process_schedule_sync_jobs --retry-failed
```

Revisar inventario desde consola:

```bash
cd backend
python manage.py inspect_asterisk
```

Limpiar jobs sincronizados antiguos en simulacion:

```bash
cd backend
python manage.py prune_schedule_sync_jobs --older-than-days 90 --dry-run
```
