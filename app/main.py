# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.api.routers import auth, users, admin, products, categories, brands

# --- Metadatos / tags ---
TAGS_METADATA = [
    {"name": "auth", "description": "Login local, refresh tokens, verificación por email y OAuth (upsert)."},
    {"name": "users", "description": "Registro, lectura y actualización del perfil."},
    {"name": "admin", "description": "Gestión de usuarios (solo admins)."},
    {"name": "products", "description": "Catálogo público y gestión de productos/variantes (solo admins para escribir)."},
    {"name": "categories", "description": "Listado público y CRUD de categorías (admin)."},
    {"name": "brands", "description": "Listado público y CRUD de marcas (admin)."},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description=(
        "API de E-Commerce.\n\n"
        "- **Auth**: OAuth2 Password, JWT (access/refresh), verificación por email.\n"
        "- **Users**: perfil y dirección.\n"
        "- **Products**: catálogo con variantes (talle/color), imágenes y filtros.\n\n"
        "Usá **Authorize** (Bearer) para probar endpoints protegidos."
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

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # ajusta en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(products.router, prefix=settings.API_V1_STR)
app.include_router(categories.router, prefix=settings.API_V1_STR)
app.include_router(brands.router, prefix=settings.API_V1_STR)

# --- OpenAPI con securitySchemes (Bearer + OAuth2 Password) ---
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

    comps = openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})

    comps["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Pega tu access token. Formato: `Bearer <token>`",
    }

    comps["OAuth2Password"] = {
        "type": "oauth2",
        "flows": {"password": {"tokenUrl": f"{settings.API_V1_STR}/auth/login", "scopes": {}}},
        "description": "OAuth2 Password Flow contra `/auth/login`.",
    }

    # Solo documentación; la protección real la hacen tus Depends.
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# --- Root amigable ---
@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "docs": "/docs", "redoc": "/redoc"}
