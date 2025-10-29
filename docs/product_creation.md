# Procedimiento de creación de productos (entorno dev)

Este documento resume las relaciones que intervienen al crear un `Product` y describe los distintos caminos posibles (con y sin dependencias). También detalla el seed de desarrollo incluido en `scripts/seed_dev_products.py`.

## Relaciones clave del modelo
- **Product**: campos base (título, precio, slug opcional, material, etc.).
- **Category** (`product.category_id`): opcional. Se crea con `category_service.create_category`. Se asigna con `UUID` o se deja en `None` para productos sin categoría.
- **Brand** (`product.brand_id`): opcional. Se crea con `brand_service.create_brand`. Si no se indica, el producto queda sin marca.
- **ProductVariant**: describe SKU, talle, color, stock y política de reposición. Aunque el modelo permite listas vacías, en práctica se recomienda al menos una variante para que el catálogo sea comercializable.
- **Supplier** (`variant.primary_supplier_id`): opcional. Se genera con `purchase_service.create_supplier`. Permite asociar un proveedor preferido para la variante y habilita los flujos de compras/reposición.
- **ProductImage**: opcional. Se añade junto al producto; si se proporcionan URLs que no apuntan a Cloudinary ya configurado, el servicio intenta subir la imagen automáticamente.

## Caminos de creación
1. **Producto mínimo (sin relaciones)**  
   - No se envían `category_id`, `brand_id` ni imágenes.  
   - Las variantes pueden omitirse (el servicio acepta lista vacía), pero se aconseja al menos una variante con `sku`, `size_label`, `color_name` y `stock_on_hand`.

2. **Producto con clasificación (categoría + marca)**  
   1. Crear o reutilizar la categoría (`category_service.create_category`).  
   2. Crear o reutilizar la marca (`brand_service.create_brand`).  
   3. Llamar a `product_service.create_product` con los `UUID` de categoría y marca convertidos a `str` (el `ProductCreate` los parsea a `UUID`).  

3. **Producto completo con proveedores y stock**  
   1. Crear el proveedor con `purchase_service.create_supplier`.  
   2. Crear la categoría y la marca (opcional según negocio).  
   3. Definir variantes con `primary_supplier_id` apuntando al proveedor anterior y configurar `reorder_point`/`reorder_qty`.  
   4. Añadir imágenes (opcional).  
   5. Ejecutar `product_service.create_product` con toda la estructura.

### Campos que aceptan `NULL`
- `category_id`, `brand_id`: dejan el producto sin clasificación asociada.  
- `primary_supplier_id`: la variante queda sin proveedor preferido.  
- `ProductImage` y lista de variantes: opcionales (aunque recomendadas).  
- `material`, `care`, `gender`, `season`, `fit`: metadatos libres, pueden omitirse.

## Seed de referencia (`scripts/seed_dev_products.py`)
- Crea categorías, marcas y proveedores de ejemplo si no existen.  
- Inserta tres productos de muestra que cubren los casos anteriores:  
  - Producto con categoría, marca, dos variantes y múltiples imágenes.  
  - Producto con categoría, marca y variante con proveedor y `allow_backorder=True`.  
  - Producto sin categoría/marca, variantes sin proveedor y sin imágenes (caso mínimo).  
- Uso: `.\.venv\Scripts\python.exe scripts\seed_dev_products.py` (requiere la base dev configurada en `.env`).  
- El script reutiliza los servicios de dominio, por lo que respeta el mismo flujo de validaciones y subida de imágenes que la API.
- Para poblar relaciones adicionales (preguntas, deseos, reposiciones, promociones) ejecuta `.\.venv\Scripts\python.exe scripts\seed_product_relationships.py`.
- Para eliminar productos de prueba ajenos al set curado y re-sincronizar los existentes, usa `.\.venv\Scripts\python.exe scripts\normalize_products.py`.

## Tips adicionales
- Si se envían URLs que no pertenecen a Cloudinary, asegúrate de tener variables de Cloudinary configuradas; de lo contrario, usa URLs ya alojadas en Cloudinary para evitar re-subidas.  
- Al probar manualmente, ejecuta el seed de usuarios (`scripts/seed_dev_users.py`) para contar con un admin y acceder al panel/admin API.  
- Después de crear productos vía shell o scripts, ejecutar `alembic upgrade head` garantiza que la base dev tenga el schema actualizado antes de probar nuevas semillas.
