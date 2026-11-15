"""Backend P4: Alexa -> DynamoDB (dispositivos y vinculaciones) -> IoT Thing Shadow.

El usuario vincula su tendedero con el codigo numerico de la etiqueta. Ese
codigo se busca en la tabla de dispositivos para obtener el Thing; no hay
nombres de Things en variables de entorno ni en el codigo. En las demas
solicitudes el Thing se resuelve por userId en la tabla de vinculaciones.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
import ask_sdk_core.utils as ask_utils
from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

REGION = os.getenv("AWS_REGION", "us-east-2")
IOT_ENDPOINT = os.getenv("IOT_ENDPOINT", "")
BINDINGS_TABLE = os.getenv("DDB_BINDINGS_TABLE", "tendedero_vinculaciones")
DEVICES_TABLE = os.getenv("DDB_DEVICES_TABLE", "tendedero_dispositivos")
DEVICES_CODE_INDEX = os.getenv("DDB_DEVICES_CODE_INDEX", "codigoVinculacion-index")

POSICIONES = ("expuesto", "resguardado")
# Palabras que puede decir el usuario -> condicion que entiende el ESP32.
CONDICIONES = {
    "seco": "seco", "seca": "seco", "sin agua": "seco", "en seco": "seco",
    "mojado": "mojado", "mojada": "mojado", "humedo": "mojado", "húmedo": "mojado",
    "con agua": "mojado", "agua": "mojado",
}


class BindingRepository:
    """Vinculaciones usuario de Alexa -> Thing."""

    def __init__(self):
        self._table = boto3.resource("dynamodb", region_name=REGION).Table(BINDINGS_TABLE)

    def find(self, user_id):
        item = self._table.get_item(Key={"userId": user_id}, ConsistentRead=True).get("Item")
        return item.get("thingName") if item else None

    def bind(self, user_id, thing_name):
        self._table.put_item(Item={
            "userId": user_id,
            "thingName": thing_name,
            "fechaVinculacion": datetime.now(timezone.utc).isoformat(),
        })

    def unbind(self, user_id):
        self._table.delete_item(Key={"userId": user_id})


class DeviceRepository:
    """Ficha de cada tendedero: thingName (clave) y su codigo de vinculacion."""

    def __init__(self):
        self._table = boto3.resource("dynamodb", region_name=REGION).Table(DEVICES_TABLE)

    def find_thing(self, codigo):
        """Devuelve el Thing que tiene ese codigo, o None si no existe."""
        items = self._table.query(
            IndexName=DEVICES_CODE_INDEX,
            KeyConditionExpression="codigoVinculacion = :codigo",
            ExpressionAttributeValues={":codigo": codigo},
        ).get("Items", [])
        if not items:
            return None
        if len(items) > 1:
            # Error de alta: dos tendederos no pueden compartir codigo.
            raise ValueError("Código de vinculación duplicado")
        return items[0]["thingName"]


class ShadowService:
    def __init__(self):
        if not IOT_ENDPOINT:
            raise RuntimeError("Falta la variable IOT_ENDPOINT")
        self._control = boto3.client("iot", region_name=REGION)
        self._data = boto3.client("iot-data", region_name=REGION, endpoint_url="https://" + IOT_ENDPOINT)

    def assert_thing_exists(self, thing_name):
        # Lanza ClientError si no existe o el rol carece de DescribeThing.
        self._control.describe_thing(thingName=thing_name)

    def read(self, thing_name):
        try:
            response = self._data.get_thing_shadow(thingName=thing_name)
            doc = json.loads(response["payload"].read())
            return doc.get("state", {})
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("ResourceNotFoundException", "ResourceNotFound"):
                return {}
            raise

    def request_position(self, thing_name, position):
        if position not in POSICIONES:
            raise ValueError("Posición del tendedero no válida")
        self._update_desired(thing_name, {"posicion": position})

    def request_calibration(self, thing_name, condicion):
        """Pide al ESP32 medir el sensor en la condicion indicada.

        El id (hora en milisegundos) distingue cada pedido: sin el, repetir la
        misma condicion no cambiaria desired y el dispositivo no recibiria delta.
        """
        if condicion not in ("seco", "mojado"):
            raise ValueError("Condición de calibración no válida")
        pedido = {"condicion": condicion, "id": int(time.time() * 1000)}
        self._update_desired(thing_name, {"calibracion_solicitada": pedido})

    def _update_desired(self, thing_name, desired):
        payload = {"state": {"desired": desired}}
        self._data.update_thing_shadow(
            thingName=thing_name,
            payload=json.dumps(payload).encode("utf-8"),
        )


def _user_id(handler_input):
    envelope = handler_input.request_envelope
    context = getattr(envelope, "context", None)
    system = getattr(context, "system", None)
    user = getattr(system, "user", None)
    if user is None:
        session = getattr(envelope, "session", None)
        user = getattr(session, "user", None)
    value = getattr(user, "user_id", None)
    if not value:
        raise ValueError("No se recibió userId de Alexa")
    return value


def _slot_object(handler_input, slot_name):
    request = handler_input.request_envelope.request
    intent = getattr(request, "intent", None)
    slots = getattr(intent, "slots", {}) or {}
    return slots.get(slot_name)


def _slot(handler_input, slot_name):
    value = getattr(_slot_object(handler_input, slot_name), "value", None)
    return value.strip() if isinstance(value, str) else ""


def _codigo(handler_input):
    """Codigo de vinculacion de 6 digitos, o cadena vacia si no es valido."""
    digits = re.sub(r"\D", "", _slot(handler_input, "codigo"))
    return digits if re.fullmatch(r"[1-9][0-9]{5}", digits) else ""


def _condicion(handler_input):
    """Normaliza el slot a "seco" o "mojado"; cadena vacia si no se entiende."""
    slot = _slot_object(handler_input, "condicion")
    try:
        # Si Alexa resolvio un sinonimo, entrega el id del valor del tipo.
        for authority in slot.resolutions.resolutions_per_authority:
            if authority.values:
                resolved = authority.values[0].value.id
                if resolved in ("seco", "mojado"):
                    return resolved
    except (AttributeError, TypeError):
        pass
    phrase = re.sub(r"\s+", " ", _slot(handler_input, "condicion")).casefold()
    return CONDICIONES.get(phrase, "")


def _answer(handler_input, message, keep_open=True):
    builder = handler_input.response_builder.speak(message)
    if keep_open:
        builder.ask("¿Quieres hacer algo más?")
    return builder.response


def _bound_thing(handler_input):
    return BindingRepository().find(_user_id(handler_input))


def _run_safe(handler_input, operation):
    try:
        return operation()
    except (ClientError, ValueError, RuntimeError, json.JSONDecodeError):
        LOG.exception("Falló la operación del tendedero")
        return _answer(handler_input, "No pude completar la solicitud. Revisa el código, la conexión y los permisos de AWS.")


SIN_VINCULO = "No tienes un tendedero vinculado. Di: vincula mi tendedero con el código, seguido de los seis dígitos de la etiqueta."


class LaunchHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        return _answer(handler_input, "Bienvenido al tendedero inteligente. Puedes vincular tu tendedero, consultar el agua, exponer o resguardar la ropa y calibrar el sensor.")


class VincularHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("VincularThingIntent")(handler_input)
                or ask_utils.is_intent_name("CambiarThingIntent")(handler_input))

    def handle(self, handler_input):
        def work():
            codigo = _codigo(handler_input)
            if not codigo:
                return _answer(handler_input, "Dime el código de seis dígitos que está en la etiqueta de tu tendedero.")
            thing_name = DeviceRepository().find_thing(codigo)
            if not thing_name:
                return _answer(handler_input, "No encontré un tendedero con ese código. Revisa la etiqueta e inténtalo de nuevo.")
            try:
                ShadowService().assert_thing_exists(thing_name)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
                    raise
                return _answer(handler_input, "Ese código corresponde a un tendedero que ya no está registrado.")
            BindingRepository().bind(_user_id(handler_input), thing_name)
            return _answer(handler_input, "He vinculado tu tendedero. Ahora puedes consultar el agua, moverlo o calibrar el sensor.")
        return _run_safe(handler_input, work)


class DesvincularHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("DesvincularThingIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            repo = BindingRepository()
            user_id = _user_id(handler_input)
            if not repo.find(user_id):
                return _answer(handler_input, "No tienes ningún tendedero vinculado.")
            repo.unbind(user_id)
            return _answer(handler_input, "He eliminado la vinculación de tu tendedero.")
        return _run_safe(handler_input, work)


class ComandoPosicionHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("ExponerTendederoIntent")(handler_input)
                or ask_utils.is_intent_name("ResguardarTendederoIntent")(handler_input))

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, SIN_VINCULO)
            name = handler_input.request_envelope.request.intent.name
            position = "expuesto" if name == "ExponerTendederoIntent" else "resguardado"
            ShadowService().request_position(thing_name, position)
            return _answer(handler_input, "He solicitado que el tendedero quede {}. Espera la confirmación del dispositivo.".format(position))
        return _run_safe(handler_input, work)


class ConsultarAguaHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarAguaIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, SIN_VINCULO)
            reported = ShadowService().read(thing_name).get("reported", {})
            detectada = reported.get("agua_detectada")
            if not isinstance(detectada, bool):
                return _answer(handler_input, "Todavía no hay una clasificación de agua disponible en AWS.")
            return _answer(handler_input, "El sensor detecta agua." if detectada else "El sensor no detecta agua.")
        return _run_safe(handler_input, work)


class ConsultarPosicionHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarPosicionIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, SIN_VINCULO)
            state = ShadowService().read(thing_name)
            actual = state.get("reported", {}).get("posicion")
            desired = state.get("desired", {}).get("posicion")
            if not actual:
                return _answer(handler_input, "El tendedero todavía no ha reportado su posición.")
            phrase = "Según el último reporte, el tendedero está {}.".format(actual)
            if desired and desired != actual:
                phrase += " Existe una orden pendiente para dejarlo {}.".format(desired)
            return _answer(handler_input, phrase)
        return _run_safe(handler_input, work)


class CalibrarSensorHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("CalibrarSensorIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, SIN_VINCULO)
            condicion = _condicion(handler_input)
            if not condicion:
                return _answer(handler_input, "Dime en qué condición está el sensor. Puedes decir: calibra el sensor seco, o calibra el sensor mojado.")
            ShadowService().request_calibration(thing_name, condicion)
            # No se espera al dispositivo: la respuesta guia el paso siguiente.
            if condicion == "seco":
                return _answer(handler_input, "He solicitado la calibración en seco. Mantén el sensor seco unos segundos. Después moja la superficie del sensor y di: calibra el sensor mojado.")
            return _answer(handler_input, "He solicitado la calibración con agua. Mantén el sensor mojado unos segundos. Para saber el resultado, pregunta: cómo está la calibración.")
        return _run_safe(handler_input, work)


class ConsultarCalibracionHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarCalibracionIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, SIN_VINCULO)
            state = ShadowService().read(thing_name)
            reported = state.get("reported", {})
            pedido = state.get("desired", {}).get("calibracion_solicitada") or {}
            atendido = reported.get("calibracion_solicitada") or {}
            # El ESP32 repite en reported el pedido que ya atendio.
            if pedido.get("id") and pedido.get("id") != atendido.get("id"):
                return _answer(handler_input, "La calibración en {} todavía está pendiente. Verifica que el tendedero esté encendido y conectado.".format(pedido.get("condicion", "curso")))
            estado = (reported.get("calibracion") or {}).get("estado")
            condicion = atendido.get("condicion", "")
            if estado == "aplicada":
                return _answer(handler_input, "La última calibración, con el sensor {}, se aplicó correctamente.".format(condicion))
            if estado == "rechazada":
                return _answer(handler_input, "La última calibración, con el sensor {}, fue rechazada porque las lecturas en seco y con agua quedaron demasiado parecidas. Se conservan los valores anteriores. Revisa la condición del sensor y repítela.".format(condicion))
            if estado == "caducada":
                return _answer(handler_input, "La última calibración llegó tarde al tendedero y no se aplicó. Repítela con el tendedero encendido y conectado.")
            if estado == "fabrica":
                return _answer(handler_input, "El sensor usa la calibración de fábrica. Puedes decir: calibra el sensor seco.")
            return _answer(handler_input, "El tendedero todavía no ha reportado su calibración.")
        return _run_safe(handler_input, work)


class HelpHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        return _answer(handler_input, "Puedes vincular, cambiar o desvincular tu tendedero con su código, preguntar por el agua, exponer o resguardar la ropa, consultar su posición y calibrar el sensor seco o mojado.")


class StopHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)
                or ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input))

    def handle(self, handler_input):
        return _answer(handler_input, "Hasta luego.", keep_open=False)


class FallbackHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        return _answer(handler_input, "No entendí. Di ayuda para conocer las órdenes disponibles.")


class ErrorHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        LOG.error("Error inesperado: %s", exception, exc_info=True)
        return _answer(handler_input, "Ocurrió un problema con la Skill. Inténtalo de nuevo.")


builder = SkillBuilder()
builder.add_request_handler(LaunchHandler())
builder.add_request_handler(VincularHandler())
builder.add_request_handler(DesvincularHandler())
builder.add_request_handler(ComandoPosicionHandler())
builder.add_request_handler(ConsultarAguaHandler())
builder.add_request_handler(ConsultarPosicionHandler())
builder.add_request_handler(CalibrarSensorHandler())
builder.add_request_handler(ConsultarCalibracionHandler())
builder.add_request_handler(HelpHandler())
builder.add_request_handler(StopHandler())
builder.add_request_handler(FallbackHandler())
builder.add_exception_handler(ErrorHandler())

lambda_handler = builder.lambda_handler()
