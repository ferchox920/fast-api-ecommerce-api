# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.api.routers import (
    admin,
    admin_promotions,
    analytics,
    auth,
    brands,
    categories,
    cart,
    engagement,
    exposure,
    notifications,
    payments,
    promotions,
    product_questions,
    products,
    scoring,
    orders,
    loyalty,
    purchases,
    reports,
    users,
    variants,
)

# --- Models registration (necesario para que Alembic los detecte) ---
import app.models.product        # noqa: F401
import app.models.inventory      # noqa: F401
import app.models.supplier       # noqa: F401
import app.models.purchase       # noqa: F401
import app.models.order          # noqa: F401
import app.models.cart           # noqa: F401
import app.models.product_question  # noqa: F401
import app.models.notification      # noqa: F401
import app.models.engagement        # noqa: F401
import app.models.promotion         # noqa: F401
import app.models.loyalty           # noqa: F401

# --- Metadatos de la API para la documentación ---
TAGS_METADATA = [
    {"name": "auth", "description": "Autenticacion, tokens y gestion de sesiones."},
    {"name": "users", "description": "Operaciones del perfil de usuario."},
    {"name": "admin", "description": "Operaciones de administracion de usuarios."},
    {"name": "admin-promotions", "description": "Gestion de promociones (administracion)."},
    {"name": "products", "description": "Gestion y consulta del catalogo de productos."},
    {"name": "categories", "description": "Gestion de categoriasias de productos."},
    {"name": "brands", "description": "Gestion de marcas."},
    {"name": "variants", "description": "Gestion de variantes de productos (SKU, stock, etc.)."},
    {"name": "purchases", "description": "Gestion de proveedores y ordenes de compra."},
    {"name": "orders", "description": "Ordenes de venta del cliente."},
    {"name": "payments", "description": "Pagos y preferencias de checkout."},
    {"name": "notifications", "description": "Centro de notificaciones en tiempo real."},
    {"name": "product-questions", "description": "Preguntas y respuestas sobre productos."},
    {"name": "engagement", "description": "Registro de eventos y metricas de interaccion."},
    {"name": "exposure", "description": "Motor de exposicion equilibrada de productos."},
    {"name": "promotions", "description": "Promociones dinamicas."},
    {"name": "loyalty", "description": "Sistema de fidelizacion."},
    {"name": "analytics", "description": "Paneles y metricas administrativas."},
    {"name": "cart", "description": "Carritos de compra para usuarios e invitados."},
    {"name": "reports", "description": "Metricas y reportes de negocio."},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description=(
        "API de E-Commerce modular y escalable.\n\n"
        "- **Auth**: Login, refresh tokens y verificación de email.\n"
        "- **Users**: Gestión de perfiles de usuario.\n"
        "- **Products**: Catálogo completo con variantes, imágenes y filtros.\n"
        "- **Purchases**: Ciclo de abastecimiento con proveedores y órdenes de compra.\n"
        "- **Reports**: Metricas de negocio basadas en el historial de ventas.\n\n"
        "Usa el botón **Authorize** para probar los endpoints protegidos."
    ),
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    },
)

# --- Middlewares ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ajustar en producción para mayor seguridad
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(admin_promotions.router, prefix=settings.API_V1_STR)
app.include_router(categories.router, prefix=settings.API_V1_STR)
app.include_router(brands.router, prefix=settings.API_V1_STR)
app.include_router(engagement.router, prefix=settings.API_V1_STR)
app.include_router(exposure.router, prefix=settings.API_V1_STR)
app.include_router(cart.router, prefix=settings.API_V1_STR)
app.include_router(products.router, prefix=settings.API_V1_STR)
app.include_router(variants.router, prefix=settings.API_V1_STR)
app.include_router(product_questions.router, prefix=settings.API_V1_STR)
app.include_router(promotions.router, prefix=settings.API_V1_STR)
app.include_router(payments.router, prefix=settings.API_V1_STR)
app.include_router(loyalty.router, prefix=settings.API_V1_STR)
app.include_router(purchases.router, prefix=settings.API_V1_STR)
app.include_router(orders.router, prefix=settings.API_V1_STR)
app.include_router(scoring.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)


# --- Configuración personalizada de OpenAPI ---
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=TAGS_METADATA,
    )

    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }

    comps = openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    comps["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Pega tu access token aquí. Formato: `Bearer <token>`",
    }
    
    # Define que los endpoints usarán BearerAuth por defecto
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# --- Endpoint raíz ---
@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "docs_url": "/docs", "redoc_url": "/redoc"}




