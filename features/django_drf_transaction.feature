# language: es
Característica: Autenticación JWT y Serialización Transaccional en Django REST Framework

  Escenario: Creación de Pedido con Token JWT Bearer
    Dado que un usuario envía credenciales a `/api/token/` y obtiene un `access_token`
    Cuando realiza un POST a `/api/v1/orders/` enviando el `CreateOrderRequestContract`
    Entonces el Serializer de DRF realiza la validación de tipos y de idempotencia
    Y Pytest-django ejecuta la suite de pruebas comprobando el estado HTTP 201 Created
    Y la vista en React mediante `useMutation` actualiza el estado del dashboard
