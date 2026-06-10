import json

SAMPLE_ITEMS = [
    {"product_id": "P001", "product_name": "Test Widget", "product_price": 9.99, "quantity": 2},
    {"product_id": "P002", "product_name": "Test Gadget", "product_price": 4.49, "quantity": 3},
]
from app.db import db
from app.models.order import Order
from app.models.line_item import LineItem


# ─── POST /orders/ ────────────────────────────────────────────────────────────

def test_create_order_returns_201_and_persists(client, sns_mock):
    # Act
    response = client.post("/orders/", json={"user_id": 1})
    order_id = response.get_json()["id"]
    order = db.session.get(Order, order_id)

    # Assert
    assert response.status_code == 201
    assert order is not None
    assert order.user_id == 1


def test_create_order_returns_correct_response_body(client, sns_mock):
    # Act
    response = client.post("/orders/", json={"user_id": 42})
    body = response.get_json()

    # Assert
    assert body["user_id"] == 42
    assert "id" in body
    assert body["items"] == []


def test_create_order_missing_user_id_returns_400(client, sns_mock):
    # Act
    response = client.post("/orders/", json={})

    # Assert
    assert response.status_code == 400


def test_create_order_with_items_returns_201_and_persists(client, sns_mock):
    # Act
    response = client.post("/orders/", json={"user_id": 1, "items": SAMPLE_ITEMS})
    body = response.get_json()
    order = db.session.get(Order, body["id"])

    # Assert
    assert response.status_code == 201
    assert len(body["items"]) == 2
    assert {item["product_name"] for item in body["items"]} == {"Test Widget", "Test Gadget"}
    assert order is not None
    assert len(order.items) == 2
    assert {item.product_name for item in order.items} == {"Test Widget", "Test Gadget"}


# ─── GET /orders/ ─────────────────────────────────────────────────────────────

def test_get_all_orders_returns_empty_list(client):
    # Act
    response = client.get("/orders/")

    # Assert
    assert response.status_code == 200
    assert response.get_json() == []


def test_get_all_orders_returns_all_orders(client, two_orders_with_items):
    # Act
    response = client.get("/orders/")

    # Assert
    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_get_all_orders_returns_correct_data(client, two_orders_with_items):
    # Act
    body = client.get("/orders/").get_json()

    # Assert
    assert {o["user_id"] for o in body} == {1, 2}

# ─── GET /orders/?user_id=<id> ────────────────────────────────────────────────

def test_get_orders_by_user_id_returns_200(client, two_orders_with_items):
    response = client.get("/orders/", query_string={"user_id": 1})

    assert response.status_code == 200


def test_get_orders_by_user_id_returns_only_matching_orders(client, two_orders_with_items):
    response = client.get("/orders/", query_string={"user_id": 1})
    body = response.get_json()

    assert len(body) == 1
    assert body[0]["user_id"] == 1


def test_get_orders_by_user_id_excludes_other_users_orders(client, two_orders_with_items):
    response = client.get("/orders/", query_string={"user_id": 1})
    body = response.get_json()

    assert all(order["user_id"] == 1 for order in body)


def test_get_orders_by_user_id_returns_empty_list_when_no_match(client, two_orders_with_items):
    response = client.get("/orders/", query_string={"user_id": 999})

    assert response.status_code == 200
    assert response.get_json() == []


def test_get_orders_by_user_id_returns_all_orders_for_that_user(client, app):
    # Arrange: two orders for user 5, one for user 7
    order1 = Order(user_id=5)
    order2 = Order(user_id=5)
    order3 = Order(user_id=7)
    db.session.add_all([order1, order2, order3])
    db.session.commit()

    # Act
    response = client.get("/orders/", query_string={"user_id": 5})
    body = response.get_json()

    # Assert
    assert len(body) == 2
    assert all(order["user_id"] == 5 for order in body)



# ─── GET /orders/<id> ─────────────────────────────────────────────────────────

def test_get_single_order_returns_200(client, one_order_with_items):
    # Act
    response = client.get(f"/orders/{one_order_with_items['id']}")

    # Assert
    assert response.status_code == 200


def test_get_single_order_returns_correct_data(client, one_order_with_items):
    # Act
    response = client.get(f"/orders/{one_order_with_items['id']}")
    body = response.get_json()

    # Assert
    assert body["id"] == one_order_with_items["id"]
    assert body["user_id"] == one_order_with_items["user_id"]
    assert len(body["items"]) == 2
    for item in body["items"]:
        assert "product_id" in item
        assert "product_name" in item
        assert "product_price" in item
        assert "quantity" in item


def test_get_single_order_not_found_returns_404(client):
    # Act
    response = client.get("/orders/999999")

    # Assert
    assert response.status_code == 404


def test_get_single_order_invalid_id_returns_400(client):
    # Act
    response = client.get("/orders/banana")

    # Assert
    assert response.status_code == 400


# ─── PUT /orders/<id> ─────────────────────────────────────────────────────────

def test_update_order_returns_204_and_persists(client, one_order_with_items):
    # Arrange
    order_id = one_order_with_items["id"]

    # Act
    response = client.put(f"/orders/{order_id}", json={"user_id": 99})
    order = db.session.get(Order, order_id)

    # Assert
    assert response.status_code == 204
    assert order.user_id == 99


def test_update_order_not_found_returns_404(client):
    # Act
    response = client.put("/orders/999999", json={"user_id": 1})

    # Assert
    assert response.status_code == 404


def test_update_order_invalid_id_returns_400(client):
    # Act
    response = client.put("/orders/banana", json={"user_id": 1})

    # Assert
    assert response.status_code == 400


# ─── DELETE /orders/<id> ──────────────────────────────────────────────────────

def test_delete_order_returns_204_and_removes_order_and_items(client, one_order_with_items):
    # Arrange
    order_id = one_order_with_items["id"]

    # Act
    response = client.delete(f"/orders/{order_id}")
    order = db.session.get(Order, order_id)
    orphaned_items = db.session.scalars(
        db.select(LineItem).where(LineItem.order_id == order_id)
    ).all()

    # Assert
    assert response.status_code == 204
    assert order is None
    assert orphaned_items == []


def test_delete_order_not_found_returns_404(client):
    # Act
    response = client.delete("/orders/999999")

    # Assert
    assert response.status_code == 404


def test_delete_order_invalid_id_returns_400(client):
    # Act
    response = client.delete("/orders/banana")

    # Assert
    assert response.status_code == 400