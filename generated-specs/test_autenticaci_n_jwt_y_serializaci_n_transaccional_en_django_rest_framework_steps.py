"""
pytest-bdd Step Definitions for Autenticación JWT y Serialización Transaccional en Django REST Framework
"""

from pytest_bdd import scenarios, given, when, then, parsers
from fastapi.testclient import TestClient
# from main import app

# scenarios('features/autenticaci-n-jwt-y-serializaci-n-transaccional-en-django-rest-framework.feature')

# client = TestClient(app)


# Scenario: Creación de Pedido con Token JWT Bearer

@given('que un usuario envía credenciales a `/api/token/` y obtiene un `access_token`')
def step_que_un_usuario_env_a_credenciales_a___api_token___y_obtiene_un__access_token_():
    # TODO: Implement step
    pass

@when('realiza un POST a `/api/v1/orders/` enviando el `CreateOrderRequestContract`')
def step_realiza_un_post_a___api_v1_orders___enviando_el__createorderrequestcontract_():
    # TODO: Implement step
    pass

@then('el Serializer de DRF realiza la validación de tipos y de idempotencia')
def step_el_serializer_de_drf_realiza_la_validaci_n_de_tipos_y_de_idempotencia():
    # TODO: Implement step
    pass


