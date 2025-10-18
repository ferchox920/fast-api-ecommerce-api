import uuid
import pytest
from httpx import AsyncClient


async def _create_product(client: AsyncClient, admin_token: str) -> dict:
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": f"QA-Cat-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": f"QA-Brand-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_brand.status_code == 201
    brand = r_brand.json()

    r_prod = await client.post(
        "/api/v1/products",
        json={
            "title": "Producto QA",
            "price": 999.0,
            "currency": "ARS",
            "category_id": cat["id"],
            "brand_id": brand["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_prod.status_code == 201
    return r_prod.json()


@pytest.mark.asyncio
async def test_question_flow(client: AsyncClient, admin_token: str, user_token: str):
    product = await _create_product(client, admin_token)

    # Usuario crea pregunta
    rq = await client.post(
        f"/api/v1/products/{product['id']}/questions",
        json={"content": "Este producto tiene garantía?"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert rq.status_code == 201, rq.text
    question = rq.json()
    assert question["status"] == "pending"

    # listado publico
    rl = await client.get(f"/api/v1/products/{product['id']}/questions")
    assert rl.status_code == 200
    data = rl.json()
    assert len(data) == 1

    # admin responde
    ra = await client.post(
        f"/api/v1/products/questions/{question['id']}/answer",
        json={"content": "Sí, tiene 1 año de garantía."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ra.status_code == 200, ra.text
    answered = ra.json()
    assert answered["status"] == "answered"
    assert len(answered["answers"]) == 1

    # admin oculta
    rv = await client.patch(
        f"/api/v1/products/questions/{question['id']}/visibility",
        json={"is_visible": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rv.status_code == 200
    question_hidden = rv.json()
    assert question_hidden["is_visible"] is False
    assert question_hidden["status"] == "hidden"

    # admin bloquea
    rb = await client.patch(
        f"/api/v1/products/questions/{question['id']}/block",
        json={"is_blocked": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rb.status_code == 200
    blocked = rb.json()
    assert blocked["is_blocked"] is True
    assert blocked["status"] == "blocked"

    # listado publico sin preguntas visibles
    rl2 = await client.get(f"/api/v1/products/{product['id']}/questions")
    assert rl2.status_code == 200
    assert rl2.json() == []

    # listado admin con ocultas
    rl_admin = await client.get(
        f"/api/v1/products/{product['id']}/questions",
        params={"include_hidden": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rl_admin.status_code == 200
    assert len(rl_admin.json()) == 1
