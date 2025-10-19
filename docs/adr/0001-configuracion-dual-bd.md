# ADR 0001 - Configuracion dual de motores de base de datos

- **Estado:** Aceptado
- **Fecha:** 2025-10-18

## Contexto
La aplicacion contaba unicamente con una URL de conexion sincronica (`DATABASE_URL`). Esta limitacion complica la adopcion gradual de SQLAlchemy Async, el uso de drivers como `asyncpg` y la reutilizacion de fixtures en pruebas asincronas.

## Objetivo
- Exponer configuracion explicita para motores sincronicos y asincronicos.
- Preparar la infraestructura para migrar modulos a SQLAlchemy Async sin bloquear el modo actual.

## Alcance
- Ajustar `app/core/config.py` para soportar `DATABASE_URL` y `ASYNC_DATABASE_URL`, con derivacion automatica cuando no se provee la version async.
- Incorporar una fabrica de sesiones asincronica en `app/db/async_session.py`.
- Actualizar `requirements.txt` con `asyncpg`, `sqlalchemy[asyncio]`, `greenlet` y `fixtures`.

## Criterios de Done
1. La configuracion expone ambas URLs (`DATABASE_URL`, `ASYNC_DATABASE_URL`) y garantiza valores viables por defecto.
2. Existen factories separadas para sesiones sync y async (`SessionLocal`, `AsyncSessionLocal`) listas para inyectarse en dependencias.
3. Las dependencias necesarias para drivers async y compatibilidad con modo sync estan listadas en `requirements.txt`.
4. Se documenta la decision y sus implicancias para el equipo.

## Decision
Mantener el motor sincronico actual mientras se habilita un motor asincronico paralelo. Cuando el entorno no define `ASYNC_DATABASE_URL`, la configuracion deriva uno compatible a partir de `DATABASE_URL`. Se anade una fabrica de sesiones asincronica con SQLAlchemy 2.x y se incorporan las dependencias minimas (`asyncpg`, `sqlalchemy[asyncio]`, `greenlet`, `fixtures`) para soportar ambos modos durante la transicion.

## Consecuencias
- Simplifica la futura migracion de endpoints y tareas a SQLAlchemy Async.
- Introduce una dependencia explicita de `greenlet` mientras convivan ambos motores.
- Es necesario revisar tests e infraestructura para elegir la factory adecuada segun el contexto (sync vs async).

## Proximos pasos
- Definir estrategia de migracion de modulos criticos a `AsyncSession`.
- Revisar fixtures de tests para alternar entre motores segun la naturaleza del escenario.
- Planificar la eliminacion de `greenlet` una vez completada la transicion asincronica.

## Lecciones de la migracion async parcial
- La serializacion de modelos requiere precargar relaciones (se uso `selectinload` y `refresh` con `attribute_names`) para evitar errores `MissingGreenlet`.
- Las dependencias de pruebas necesitan aislar sesiones async y sync; se actualizo `conftest.py` para limpiar tablas y generar datos unicos.
- La configuracion debe derivar `ASYNC_DATABASE_URL` con cuidado para soportar distintas variantes de PostgreSQL y SQLite.

## Estado actual (iterativo)
- `products`, `variants`, `purchases` operan sobre `AsyncSession` y exponen commits desde los routers.
- `orders`, `loyalty`, `engagement`, `notifications` continúan en modo sync y siguen utilizando `SessionLocal`.
- Las utilidades comunes (`app/db/operations.py`) centralizan la lógica de commit/refresh tanto sync como async para sostener la transición módulo a módulo.
