## FastAPI E-Commerce Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-orange)
![Alembic](https://img.shields.io/badge/Migrations-Alembic-lightgrey)
![Pytest](https://img.shields.io/badge/Tests-Pytest-blueviolet)

Backend modular para un e-commerce moderno construido con **FastAPI**. El proyecto cubre catalogo, inventario, ordenes, promociones, fidelizacion y analiticas, apoyado en pruebas automaticas y migraciones reproducibles.

---

### Caracteristicas principales

#### Catalogo y stock
- CRUD de productos, variantes, imagenes, marcas y categorias.
- Gestion de inventario con movimientos (`receive`, `reserve`, `release`, `sale`, `adjust`) y auditoria.
- Alertas de reposicion segun `reorder_point` / `reorder_qty`.

#### Abastecimiento y ordenes
- Proveedores con ordenes de compra (`draft`, `placed`, `received`, `cancelled`).
- Recepciones que afectan el inventario automaticamente.
- Conversion de datos de reposicion en compras sugeridas.

#### Rate View & Engagement
- Colector de eventos (`view`, `click`, `add_to_cart`, `purchase`) con deduplicacion y buckets horarios.
- Agregados diarios por producto y cliente (`product_engagement_daily`, `customer_engagement_daily`).
- Calculo horario de **scoring** con decaimiento exponencial para:
  - `popularity_score`, `cold_score`, `profit_score`, `freshness_score`.
  - `exposure_score` configurable (70 % popularidad / 30 % estrategia).

#### Exposure Engine
- Endpoint `/exposure` para generar mixes balanceados (home, category, personalized).
- Reglas para limitar repeticiones, impulsar productos frios con stock y respetar caps por categoria.
- Cache hibrida (Redis + fallback in-memory) con TTL; persistencia en `exposure_slots`.
- Notas de integracion para badges, pinning temporal y consumo via WebSocket.

#### Promociones dinamicas
- CRUD administrativo (`/admin/promotions`), activacion/desactivacion con eventos `promotion_start` / `promotion_end`.
- Evaluacion de elegibilidad segun `scope`, segmentos, nivel de fidelizacion y ticket minimo.
- `promotions` expone promociones activas y endpoint `/eligibility` para checkout/personalizacion.

#### Fidelizacion
- Perfiles en `loyalty_profile` con niveles (`loyalty_levels`) y puntos.
- Procesamiento automatico en compras, upgrades con eventos `loyalty_upgrade` y redenciones (`/loyalty/redeem`).
- Notificaciones y perks disponibles en `perks_json` para integraciones posteriores.

#### Pagos y pedidos
- Modelo de ordenes completo con pagos (`Payment`) y envios (`Shipment`).
- Integracion inicial con Mercado Pago (preferencias, webhook) y notificaciones a usuarios/admin.

#### Notificaciones
- Canal centralizado (`notifications`) compatible con WebSocket y correo.
- Eventos de preguntas, ordenes, promociones y fidelizacion.

#### Analiticas
- `/admin/analytics/overview` resume ingresos, mix de exposicion y distribucion por niveles.
- Servicios auxiliares para dashboards y futuros reportes.

#### Observabilidad y seguridad
- Métricas Prometheus para `/events` (latencia, descartes por rate limit), `/exposure` (latencia, cache hit ratio, CTR por slot), promociones (revenue lift) y loyalty (tasa de upgrade).
- Logs estructurados JSON con `request_id`, hash de `user_id`, `product_id`, `promotion_id` y metadata clave, enviados al agregador central con protecciones PII.
- Trazas correlacionadas vía OpenTelemetry (W3C Trace Context) entre FastAPI, workers y adaptadores (PostgreSQL, Redis, colas).
- Controles de seguridad: rate limiting IP/usuario en `/events`, auditoría de cambios de promociones, detección de bursts sospechosos y webhooks firmados con mTLS interno.

---

### Arquitectura

- **FastAPI** y **Pydantic v2** para la capa HTTP y validaciones.
- **SQLAlchemy 2.x** + **Alembic** para ORM y migraciones.
- **PostgreSQL** como base de datos principal (tests usan SQLite).
- **Redis** opcional para cache del exposure engine.
- Servicios modulares en `app/services`:
  - `engagement_service`, `scoring_service`, `exposure_service`, `promotion_service`, `loyalty_service`, `analytics_service`, entre otros.
- Bus de eventos simple (`event_bus`) listo para conectarse a adaptadores externos.
- Pruebas con **pytest**, **pytest-asyncio** y **httpx.AsyncClient**.

---

### Endpoints destacados

| Dominio              | Ruta / Metodo                                  | Descripcion breve |
|---------------------|-------------------------------------------------|-------------------|
| Eventos             | `POST /api/v1/events`                           | Ingresa eventos (tracking). |
| Exposure            | `GET /api/v1/exposure`                          | Mix de productos balanceado. |
| Scoring             | `POST /api/v1/internal/scoring/run`             | Ejecuta job de ranking (interno). |
| Promociones admin   | `POST /api/v1/admin/promotions`                 | Crea promocion. |
|                     | `POST /api/v1/admin/promotions/{id}/activate`   | Activa promocion. |
| Promociones public  | `GET /api/v1/promotions/active`                 | Lista promociones activas. |
|                     | `GET /api/v1/promotions/{id}/eligibility`       | Consulta elegibilidad. |
| Fidelizacion        | `GET /api/v1/loyalty/profile`                   | Perfil de puntos/nivel. |
|                     | `POST /api/v1/loyalty/redeem`                   | Redimir recompensa. |
| Ordenes y pagos     | `/api/v1/orders`, `/api/v1/payments`            | Creacion de ordenes y checkout. |
| Preguntas           | `/api/v1/products/{id}/questions`               | Q&A sobre productos (con moderacion). |
| Notificaciones      | `/api/v1/notifications`, `ws`                   | Bandeja y WebSocket. |
| Analiticas          | `GET /api/v1/admin/analytics/overview`          | KPIs generales. |

---

### Migraciones relevantes

| ID (Alembic)              | Descripcion |
|---------------------------|-------------|
| `e1a2b3c4d5f6_orders_module` | Base de ordenes (Order/OrderLine). |
| `f1234567890ab_cart_module`  | Carritos e items. |
| `1abc2def3ghi_product_questions_notifications` | Q&A y notificaciones. |
| `0a1b2c3d4e5f_orders_payments_shipments` | Pagos, envios y metadata de ordenes. |
| `2f6e7a8b9cde_rate_view_system` | Rate View (engagement, rankings, exposure, promociones, loyalty). |

Ejecutar migraciones:
```bash
alembic upgrade head
```

---

### Pruebas

```bash
pytest --maxfail=1 --disable-warnings -q
```

> Los tests utilizan SQLite en memoria mediante overrides de dependencias (`tests/conftest.py`).

---

### Snippet base para exponer mixes

```python
# app/services/exposure_service.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/exposure", tags=["exposure"])

@router.get("")
def get_exposure(context: str, user_id: str | None = None, category_id: str | None = None):
    """
    INTEGRATION: Consumido por FE para renderizar carruseles/listas.
    INTEGRATION: 'reason' y 'badges' guían UI (chips/etiquetas).
    INTEGRATION: Cache TTL coordinado con Redis (ver config.EXPOSURE_TTL_SEC).

    TODO: leer product_rankings (+ ajustes categoría/temporada)
    TODO: aplicar reglas (no repetir, impulso fríos, cap por categoría)
    TODO: mezclar 70/30 (configurable), escribir a exposure_slots, setear TTL
    TODO: instrumentar métricas (latencia, cache_hit, items_served)
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    # stub de respuesta inicial
    return {
        "context": context,
        "mix": [],
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
```

---

### Notas de integracion

- **Eventos**: `POST /events` se alinea con el tracker del frontend (dataLayer/SDK). El backend de checkout emite `purchase`.
- **Exposure**: el frontend respeta `reason` y `badges`; los equipos de producto pueden fijar/unfijar productos temporalmente.
- **Promociones**: checkout aplica `benefits_json` y devuelve `applied_benefits`. Eventos `promotion_start`/`promotion_end` disparan notificaciones.
- **Fidelizacion**: upgrades y redenciones emiten `loyalty_upgrade` y `loyalty_redeem`; los canales de notificacion escuchan estas colas.
- **Pagos**: integracion inicial con Mercado Pago lista para expandirse.

---

### Roadmap inmediato

- **Fase 1 — Ingesta & Métricas**: POST `/events`, cola `events` y agregador horario hacia `product_engagement_daily` con métricas básicas.
- **Fase 2 — Scoring & Exposure básico**: job horario, upsert en `product_rankings`, `/exposure` con cache Redis y reglas mínimas.
- **Fase 3 — Promos**: CRUD + elegibilidad + integración checkout (adapter stub) con auditoría de cambios.
- **Fase 4 — Loyalty**: perfiles, niveles, upgrades automáticos y eventos `loyalty_upgrade`.
- **Fase 5 — Observabilidad + A/B**: dashboards, alertas y experimentos de pesos (70/30 vs variantes) con métricas `exposure_hit_ratio`, `ab_variant_conversion`.

- Comentarios guía para el código:
  - `# TODO(observability): agregar métricas 'exposure_hit_ratio', 'ab_variant_conversion'.`
  - `# INTEGRATION(security): rate limit IP/user en /events; firmar webhooks internos.`
  - `# INTEGRATION(AB): feature flag 'exposure_weights' por cohorte.`

- Conectar el bus de eventos a Kafka/Rabbit para desacoplar adaptadores.
- Obtener margen/stock reales desde ERP para el scoring.
- Agregar dashboards adicionales (promociones, loyalty) en `/admin/analytics/*`.
- Frontend (React/Vue) para carruseles personalizados y centro de notificaciones.
- Automatizar compras a partir de sugerencias en inventario.

---

### Autor

Desarrollado por **Fernando Ramones** como base para un backend de e-commerce modular, escalable y auditable, inspirado en arquitectura limpia, DDD y desarrollo guiado por pruebas.
