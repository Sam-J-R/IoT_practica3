"""Backend P3: Alexa -> vinculacion DynamoDB -> IoT Thing Shadow.

La funcion fue desplegada y verificada en AWS mediante eventos directos de
Lambda: vinculacion, consultas, comandos, cambio y desvinculacion. La prueba
extremo a extremo con la Skill y el ESP32 fisico se documenta por separado.
No fija un Thing para todos los usuarios: lo resuelve por userId en cada
solicitud.
"""

import json
import logging
import os
import re
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


class BindingRepository:
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

    def request_cover(self, thing_name, position):
        if position not in ("abierta", "cerrada"):
            raise ValueError("Estado de cubierta no válido")
        payload = {"state": {"desired": {"cubierta": position}}}
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


def _slot(handler_input, slot_name):
    request = handler_input.request_envelope.request
    intent = getattr(request, "intent", None)
    slots = getattr(intent, "slots", {}) or {}
    value = getattr(slots.get(slot_name), "value", None)
    return value.strip() if isinstance(value, str) else ""


def _thing_from_spoken(raw):
    """Resuelve alias configurables; no fija un único Thing en el servicio.

    THING_ALIASES_JSON ejemplo (incluye variantes observadas en Alexa):
    {"tendedero inteligente":"tendedero-inteligente",
     "prueba dos":"tendedero-prueba2", "prueba 2":"tendedero-prueba2",
     "tendedero prueba dos":"tendedero-prueba2",
     "tendedero prueba 2":"tendedero-prueba2"}
    """
    phrase = re.sub(r"\s+", " ", raw.strip()).casefold()
    aliases = json.loads(os.getenv("THING_ALIASES_JSON", "{}"))
    for spoken, real in aliases.items():
        if phrase == re.sub(r"\s+", " ", spoken.strip()).casefold():
            return real
    # Acepta el identificador exacto escrito, validado luego por DescribeThing.
    if re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", raw):
        return raw
    # Fallback para nombre simple hablado, sin asumir que sea un Thing real.
    candidate = re.sub(r"\s+", "-", phrase)
    if re.fullmatch(r"[a-z0-9:_-]{1,128}", candidate):
        return candidate
    raise ValueError("Identificador de Thing no válido")


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
        return _answer(handler_input, "No pude completar la solicitud. Revisa el identificador, la conexión y los permisos de AWS.")


class LaunchHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        return _answer(handler_input, "Bienvenido al tendedero inteligente. Puedes vincular tu objeto, consultar el agua o abrir y cerrar la cubierta.")


class VincularHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("VincularThingIntent")(handler_input)
                or ask_utils.is_intent_name("CambiarThingIntent")(handler_input))

    def handle(self, handler_input):
        def work():
            raw = _slot(handler_input, "thing_name")
            if not raw:
                return _answer(handler_input, "Dime el identificador del objeto que quieres vincular.")
            thing_name = _thing_from_spoken(raw)
            try:
                ShadowService().assert_thing_exists(thing_name)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
                    raise
                return _answer(handler_input, "Ese identificador no corresponde a un objeto registrado. Revisa el alias e inténtalo de nuevo.")
            BindingRepository().bind(_user_id(handler_input), thing_name)
            return _answer(handler_input, "He vinculado tu cuenta con el objeto {}. Ahora puedes consultar o controlar la cubierta.".format(thing_name))
        return _run_safe(handler_input, work)


class DesvincularHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("DesvincularThingIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            repo = BindingRepository()
            user_id = _user_id(handler_input)
            if not repo.find(user_id):
                return _answer(handler_input, "No tienes ningún objeto vinculado.")
            repo.unbind(user_id)
            return _answer(handler_input, "He eliminado la vinculación de tu objeto.")
        return _run_safe(handler_input, work)


class ComandoCubiertaHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("AbrirCubiertaIntent")(handler_input)
                or ask_utils.is_intent_name("CerrarCubiertaIntent")(handler_input))

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, "Primero vincula tu objeto. Puedes decir: vincula mi objeto con su identificador.")
            name = handler_input.request_envelope.request.intent.name
            position = "abierta" if name == "AbrirCubiertaIntent" else "cerrada"
            ShadowService().request_cover(thing_name, position)
            return _answer(handler_input, "He solicitado que la cubierta quede {}. Espera la confirmación del dispositivo.".format(position))
        return _run_safe(handler_input, work)


class ConsultarAguaHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarAguaIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, "No tienes un objeto vinculado. Vincúlalo primero.")
            reported = ShadowService().read(thing_name).get("reported", {})
            detectada = reported.get("agua_detectada")
            if not isinstance(detectada, bool):
                return _answer(handler_input, "Todavía no hay una clasificación de agua disponible en AWS.")
            return _answer(handler_input, "El sensor detecta agua." if detectada else "El sensor no detecta agua.")
        return _run_safe(handler_input, work)


class ConsultarCubiertaHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarCubiertaIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _bound_thing(handler_input)
            if not thing_name:
                return _answer(handler_input, "No tienes un objeto vinculado. Vincúlalo primero.")
            state = ShadowService().read(thing_name)
            actual = state.get("reported", {}).get("cubierta")
            desired = state.get("desired", {}).get("cubierta")
            if not actual:
                return _answer(handler_input, "La cubierta todavía no ha reportado su estado.")
            phrase = "Según el último reporte, la cubierta está {}.".format(actual)
            if desired and desired != actual:
                phrase += " Existe una orden pendiente para dejarla {}.".format(desired)
            return _answer(handler_input, phrase)
        return _run_safe(handler_input, work)


class HelpHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        return _answer(handler_input, "Puedes vincular, cambiar o desvincular tu objeto, preguntar por el agua, abrir o cerrar la cubierta y consultar su estado.")


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
builder.add_request_handler(ComandoCubiertaHandler())
builder.add_request_handler(ConsultarAguaHandler())
builder.add_request_handler(ConsultarCubiertaHandler())
builder.add_request_handler(HelpHandler())
builder.add_request_handler(StopHandler())
builder.add_request_handler(FallbackHandler())
builder.add_exception_handler(ErrorHandler())

lambda_handler = builder.lambda_handler()

