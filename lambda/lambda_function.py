"""Backend P4: Alexa -> DynamoDB (dispositivos y vinculaciones) -> IoT Thing Shadow.

P4: la voz convive con la logica automatica del ESP32 (reglas R1 y R5):
- Toda orden de posicion se escribe con origen "voz"; las del LED, con
  origen_led "voz" (RF12).
- En modo automatico con agua detectada, "exponer" se rechaza con una
  explicacion; en automatico con sensor de luz, la luz tampoco se controla
  por voz. En manual, la voz manda siempre.
- La voz cambia el modo (manual / automatico) y los minutos de espera de la
  regla R2 (minutos_reexponer), como pide RF14.

El usuario vincula cada tendedero con el codigo numerico de la etiqueta y le
da un nombre ("patio", "terraza"). El codigo se busca en la tabla de
dispositivos para obtener el Thing; no hay nombres de Things en variables de
entorno ni en el codigo.

Un usuario puede tener varios tendederos (clave userId + thingName en la tabla
de vinculaciones). Cada orden se dirige asi:
1. Con un solo tendedero, a ese; no hace falta decir el nombre.
2. Con varios, al que se nombra en la frase ("resguarda el tendedero del
   patio"). Si la frase no nombra ninguno, Alexa pregunta cual (Dialog.ElicitSlot
   sobre el slot nombre) y retoma la misma orden con la respuesta.
No hay un tendedero "activo" guardado: nunca se actua sobre uno que el usuario
no eligio en esa orden. Con varios, la respuesta empieza con el nombre del
tendedero para confirmar sobre cual se actuo.
"""

import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
import ask_sdk_core.utils as ask_utils
from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model.dialog import ElicitSlotDirective


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

REGION = os.getenv("AWS_REGION", "us-east-2")
IOT_ENDPOINT = os.getenv("IOT_ENDPOINT", "")
BINDINGS_TABLE = os.getenv("DDB_BINDINGS_TABLE", "tendedero_vinculaciones")
DEVICES_TABLE = os.getenv("DDB_DEVICES_TABLE", "tendedero_dispositivos")
DEVICES_CODE_INDEX = os.getenv("DDB_DEVICES_CODE_INDEX", "codigoVinculacion-index")

POSICIONES = ("expuesto", "resguardado")
MODOS = ("manual", "automatico")
ESTADOS_LED = ("encendido", "apagado")
# Rango de minutos_reexponer aceptado por el ESP32 (config.h). Menos de 15 minutos
# expone la ropa con la superficie aun mojada y con probabilidad de otro chubasco.
MINUTOS_MIN, MINUTOS_MAX = 15, 240
# Palabras que puede decir el usuario -> modo que entiende el ESP32.
MODOS_HABLADOS = {
    "manual": "manual", "a mano": "manual", "modo manual": "manual",
    "automatico": "automatico", "automático": "automatico", "auto": "automatico",
    "modo automatico": "automatico", "modo automático": "automatico",
}
# Palabras que puede decir el usuario -> condicion que entiende el ESP32.
CONDICIONES = {
    "seco": "seco", "seca": "seco", "sin agua": "seco", "en seco": "seco",
    "mojado": "mojado", "mojada": "mojado", "humedo": "mojado", "húmedo": "mojado",
    "con agua": "mojado", "agua": "mojado",
}


# Tope de tendederos por usuario: acota la Query de cada solicitud y la lista
# que Alexa lee al preguntar en cual actuar.
MAX_TENDEDEROS = 10
# Nombre que recibe el primer tendedero si el usuario no dijo ninguno.
NOMBRE_POR_DEFECTO = "principal"
# Palabras que Alexa puede incluir en el slot y que no forman parte del nombre.
_RELLENO_NOMBRE = re.compile(r"^(?:(?:mi|el|la|los|las|del|de|al|en|tendedero|tendederos)\s+)+")


def _ahora():
    return datetime.now(timezone.utc).isoformat()


class BindingRepository:
    """Vinculaciones usuario de Alexa -> sus tendederos.

    Clave de particion userId y de ordenamiento thingName: un usuario tiene
    varios tendederos y no puede vincular dos veces el mismo. Cada item guarda
    el nombre que le dio el usuario, para distinguirlos por voz.
    """

    def __init__(self):
        self._table = boto3.resource("dynamodb", region_name=REGION).Table(BINDINGS_TABLE)

    def list(self, user_id):
        """Todos los tendederos del usuario (una Query por particion)."""
        return self._table.query(
            KeyConditionExpression="userId = :u",
            ExpressionAttributeValues={":u": user_id},
            ConsistentRead=True,
        ).get("Items", [])

    def bind(self, user_id, thing_name, nombre, fecha_vinculacion=None):
        """Crea la vinculacion o, si ya existia, le cambia el nombre."""
        self._table.put_item(Item={
            "userId": user_id,
            "thingName": thing_name,
            "nombre": nombre,
            "fechaVinculacion": fecha_vinculacion or _ahora(),
        })

    def unbind(self, user_id, thing_name):
        self._table.delete_item(Key={"userId": user_id, "thingName": thing_name})


def clave_nombre(nombre):
    """Forma de comparar nombres: sin tildes, mayusculas ni espacios de mas."""
    sin_tildes = unicodedata.normalize("NFKD", nombre or "")
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes).strip().casefold()


def limpiar_nombre(texto):
    """'el tendedero del Patio' -> 'patio'. Conserva las tildes para que Alexa lo pronuncie bien."""
    nombre = re.sub(r"\s+", " ", texto or "").strip().casefold()
    return _RELLENO_NOMBRE.sub("", nombre).strip()


def buscar_por_nombre(vinculos, nombre):
    clave = clave_nombre(nombre)
    return next((v for v in vinculos if clave_nombre(v.get("nombre")) == clave), None)


def lista_hablada(vinculos, conjuncion="y"):
    """['patio', 'terraza', 'azotea'] -> 'patio, terraza y azotea' (o '... o azotea')."""
    nombres = sorted(v.get("nombre") or v["thingName"] for v in vinculos)
    if len(nombres) == 1:
        return nombres[0]
    return ", ".join(nombres[:-1]) + " " + conjuncion + " " + nombres[-1]


def tus_tendederos(vinculos):
    if len(vinculos) == 1:
        return "Tu tendedero se llama {}.".format(lista_hablada(vinculos))
    return "Tus tendederos son: {}.".format(lista_hablada(vinculos))


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
        # El origen distingue en el historico las ordenes de voz (RF12).
        self._update_desired(thing_name, {"posicion": position, "origen": "voz"})

    def request_mode(self, thing_name, modo):
        if modo not in MODOS:
            raise ValueError("Modo de operación no válido")
        self._update_desired(thing_name, {"modo": modo})

    def request_wait(self, thing_name, minutos):
        if not MINUTOS_MIN <= minutos <= MINUTOS_MAX:
            raise ValueError("Minutos de espera fuera de rango")
        self._update_desired(thing_name, {"minutos_reexponer": minutos})

    def request_led(self, thing_name, estado):
        if estado not in ESTADOS_LED:
            raise ValueError("Estado de la luz no válido")
        self._update_desired(thing_name, {"led": estado, "origen_led": "voz"})

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


def _modo(handler_input):
    """Normaliza el slot a "manual" o "automatico"; cadena vacia si no se entiende."""
    slot = _slot_object(handler_input, "modo")
    try:
        for authority in slot.resolutions.resolutions_per_authority:
            if authority.values:
                resolved = authority.values[0].value.id
                if resolved in MODOS:
                    return resolved
    except (AttributeError, TypeError):
        pass
    phrase = re.sub(r"\s+", " ", _slot(handler_input, "modo")).casefold()
    return MODOS_HABLADOS.get(phrase, "")


def _minutos(handler_input):
    """Entero del slot minutos, o None si no es un numero."""
    digits = re.sub(r"\D", "", _slot(handler_input, "minutos"))
    return int(digits) if digits else None


def _nombre(handler_input):
    """Nombre del tendedero dicho en la frase, limpio; cadena vacia si no hay."""
    return limpiar_nombre(_slot(handler_input, "nombre"))


def _answer(handler_input, message, keep_open=True):
    # Con varios tendederos, _destino deja el nombre para encabezar la respuesta.
    prefijo = handler_input.attributes_manager.request_attributes.get("prefijo", "")
    builder = handler_input.response_builder.speak(prefijo + message)
    if keep_open:
        builder.ask("¿Quieres hacer algo más?")
    return builder.response


class SinDestino(Exception):
    """No se puede actuar: el mensaje explica por que."""


class PedirNombre(Exception):
    """Hay varios tendederos y la frase no dice cual: Alexa debe preguntarlo."""

    def __init__(self, vinculos, pregunta="¿En cuál tendedero? Tienes {}."):
        super().__init__(pregunta)
        self.vinculos = vinculos
        self.pregunta = pregunta


def _preguntar_nombre(handler_input, vinculos, pregunta):
    """Pide el slot nombre y conserva el intent con sus demas slots.

    Alexa hace la pregunta, el usuario responde ("el del patio") y la Lambda
    recibe de nuevo el mismo intent, ahora con el nombre completado.
    """
    texto = pregunta.format(lista_hablada(vinculos, "o"))
    intent = handler_input.request_envelope.request.intent
    return (handler_input.response_builder.speak(texto).ask(texto)
            .add_directive(ElicitSlotDirective(slot_to_elicit="nombre", updated_intent=intent))
            .response)


def _destino(handler_input):
    """Thing sobre el que actua la solicitud.

    Un solo tendedero: ese. Varios: el nombrado en la frase; si no nombra
    ninguno, se pregunta (PedirNombre).
    """
    vinculos = BindingRepository().list(_user_id(handler_input))
    if not vinculos:
        raise SinDestino(SIN_VINCULO)
    nombre = _nombre(handler_input)
    if nombre:
        vinculo = buscar_por_nombre(vinculos, nombre)
        if not vinculo:
            raise SinDestino("No tienes un tendedero llamado {}. {}".format(nombre, tus_tendederos(vinculos)))
    elif len(vinculos) == 1:
        vinculo = vinculos[0]
    else:
        raise PedirNombre(vinculos)
    if len(vinculos) > 1:
        handler_input.attributes_manager.request_attributes["prefijo"] = "Tendedero {}: ".format(
            vinculo.get("nombre") or vinculo["thingName"])
    return vinculo["thingName"]


def _run_safe(handler_input, operation):
    try:
        return operation()
    except SinDestino as exc:
        return _answer(handler_input, str(exc))
    except PedirNombre as exc:
        return _preguntar_nombre(handler_input, exc.vinculos, exc.pregunta)
    except (ClientError, ValueError, RuntimeError, json.JSONDecodeError):
        LOG.exception("Falló la operación del tendedero")
        return _answer(handler_input, "No pude completar la solicitud. Revisa el código, la conexión y los permisos de AWS.")


SIN_VINCULO = "No tienes un tendedero vinculado. Di: vincula mi tendedero con el código, seguido de los seis dígitos de la etiqueta."


class LaunchHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        return _answer(handler_input, "Bienvenido al tendedero inteligente. Puedes consultar el agua, exponer o resguardar la ropa, cambiar el modo o controlar la luz. Di ayuda para conocer todas las órdenes.")


class VincularHandler(AbstractRequestHandler):
    """Agrega un tendedero al usuario, o renombra uno que ya tenia."""

    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("VincularThingIntent")(handler_input)

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

            repo = BindingRepository()
            user_id = _user_id(handler_input)
            vinculos = repo.list(user_id)
            existente = next((v for v in vinculos if v["thingName"] == thing_name), None)
            nombre = _nombre(handler_input)
            if not nombre:
                if existente:
                    nombre = existente.get("nombre") or NOMBRE_POR_DEFECTO
                elif not vinculos:
                    nombre = NOMBRE_POR_DEFECTO
                else:
                    return _answer(handler_input, "Ya tienes un tendedero vinculado, así que este necesita un nombre. Di, por ejemplo: vincula mi tendedero de la terraza con el código, y los seis dígitos.")
            otro = buscar_por_nombre(vinculos, nombre)
            if otro and otro["thingName"] != thing_name:
                return _answer(handler_input, "Ya tienes un tendedero llamado {}. Elige otro nombre, por ejemplo terraza o azotea.".format(nombre))
            if not existente and len(vinculos) >= MAX_TENDEDEROS:
                return _answer(handler_input, "Ya tienes {} tendederos vinculados, que es el máximo. Desvincula uno antes de agregar otro.".format(MAX_TENDEDEROS))

            repo.bind(user_id, thing_name, nombre, existente.get("fechaVinculacion") if existente else None)
            if existente:
                if clave_nombre(existente.get("nombre")) == clave_nombre(nombre):
                    return _answer(handler_input, "Ese tendedero ya estaba vinculado con el nombre {}.".format(nombre))
                return _answer(handler_input, "Ese tendedero ya estaba vinculado. Ahora se llama {}.".format(nombre))
            if not vinculos:
                return _answer(handler_input, "He vinculado tu tendedero {}. Ahora puedes consultar el agua, moverlo o calibrar el sensor.".format(nombre))
            return _answer(handler_input, "He vinculado tu tendedero {}. Ahora tienes {} tendederos: {}. En cada orden di en cuál, por ejemplo: resguarda el tendedero del patio. Si no lo dices, te preguntaré.".format(
                nombre, len(vinculos) + 1, lista_hablada(vinculos + [{"thingName": thing_name, "nombre": nombre}])))
        return _run_safe(handler_input, work)


class ListarTendederosHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ListarTendederosIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            vinculos = BindingRepository().list(_user_id(handler_input))
            if not vinculos:
                return _answer(handler_input, SIN_VINCULO)
            if len(vinculos) == 1:
                return _answer(handler_input, "Tienes un tendedero vinculado: {}.".format(vinculos[0].get("nombre")))
            return _answer(handler_input, "Tienes {} tendederos: {}. En cada orden di en cuál, por ejemplo: resguarda el tendedero del patio.".format(
                len(vinculos), lista_hablada(vinculos)))
        return _run_safe(handler_input, work)


class DesvincularHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("DesvincularThingIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            repo = BindingRepository()
            user_id = _user_id(handler_input)
            vinculos = repo.list(user_id)
            if not vinculos:
                return _answer(handler_input, "No tienes ningún tendedero vinculado.")
            nombre = _nombre(handler_input)
            if nombre:
                vinculo = buscar_por_nombre(vinculos, nombre)
                if not vinculo:
                    return _answer(handler_input, "No tienes un tendedero llamado {}. {}".format(nombre, tus_tendederos(vinculos)))
            elif len(vinculos) == 1:
                vinculo = vinculos[0]
            else:
                # Con varios, no se adivina: desvincular el equivocado deja al usuario sin control.
                return _preguntar_nombre(handler_input, vinculos, "¿Cuál quieres desvincular? Tienes {}.")
            repo.unbind(user_id, vinculo["thingName"])
            restantes = [v for v in vinculos if v["thingName"] != vinculo["thingName"]]
            if not restantes:
                return _answer(handler_input, "He eliminado la vinculación de tu tendedero.")
            return _answer(handler_input, "He desvinculado el tendedero {}. {}".format(
                vinculo.get("nombre"), tus_tendederos(restantes)))
        return _run_safe(handler_input, work)


class ComandoPosicionHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("ExponerTendederoIntent")(handler_input)
                or ask_utils.is_intent_name("ResguardarTendederoIntent")(handler_input))

    def handle(self, handler_input):
        def work():
            thing_name = _destino(handler_input)
            name = handler_input.request_envelope.request.intent.name
            position = "expuesto" if name == "ExponerTendederoIntent" else "resguardado"
            shadow = ShadowService()
            state = shadow.read(thing_name)
            reported = state.get("reported", {})
            desired = state.get("desired", {})
            # Convivencia con R1: en automatico, la ropa no sale con lluvia.
            if (position == "expuesto" and reported.get("modo") == "automatico"
                    and reported.get("agua_detectada") is True):
                return _answer(handler_input, "El sensor detecta agua y el tendedero está en modo automático, así que la ropa se queda resguardada. Si quieres exponerla igual, primero di: cambia a modo manual.")
            # Ya esta ahi y no hay otra orden pendiente: no se escribe nada.
            if reported.get("posicion") == position and desired.get("posicion") in (None, position):
                return _answer(handler_input, "El tendedero ya está {}.".format(position))
            shadow.request_position(thing_name, position)
            return _answer(handler_input, "He solicitado que el tendedero quede {}. Espera la confirmación del dispositivo.".format(position))
        return _run_safe(handler_input, work)


class ConsultarAguaHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarAguaIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _destino(handler_input)
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
            thing_name = _destino(handler_input)
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
            thing_name = _destino(handler_input)
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
            thing_name = _destino(handler_input)
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


class CambiarModoHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("CambiarModoIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _destino(handler_input)
            modo = _modo(handler_input)
            if not modo:
                return _answer(handler_input, "¿Qué modo quieres? Puedes decir: modo automático, o modo manual.")
            ShadowService().request_mode(thing_name, modo)
            if modo == "automatico":
                return _answer(handler_input, "He activado el modo automático. El tendedero resguardará la ropa si detecta agua y la luz seguirá al sensor de luz.")
            return _answer(handler_input, "He activado el modo manual. El tendedero y la luz solo cambiarán con tus órdenes.")
        return _run_safe(handler_input, work)


class ConsultarModoHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarModoIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _destino(handler_input)
            state = ShadowService().read(thing_name)
            reported = state.get("reported", {})
            modo = reported.get("modo")
            if modo not in MODOS:
                return _answer(handler_input, "El tendedero todavía no ha reportado su modo de operación.")
            phrase = "El tendedero está en modo {}.".format("automático" if modo == "automatico" else "manual")
            minutos = reported.get("minutos_reexponer")
            if modo == "automatico" and isinstance(minutos, int):
                phrase += " Vuelve a exponer la ropa después de {} minutos sin agua.".format(minutos)
            pedido = state.get("desired", {}).get("modo")
            if pedido in MODOS and pedido != modo:
                phrase += " Hay un cambio pendiente a modo {}.".format("automático" if pedido == "automatico" else "manual")
            return _answer(handler_input, phrase)
        return _run_safe(handler_input, work)


class ConfigurarEsperaHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConfigurarEsperaIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _destino(handler_input)
            minutos = _minutos(handler_input)
            if minutos is None or not MINUTOS_MIN <= minutos <= MINUTOS_MAX:
                return _answer(handler_input, "Dime un tiempo entre {} y {} minutos. Por ejemplo: espera treinta minutos para volver a exponer.".format(MINUTOS_MIN, MINUTOS_MAX))
            ShadowService().request_wait(thing_name, minutos)
            return _answer(handler_input, "Listo. En modo automático, la ropa volverá a exponerse después de {} minutos sin agua.".format(minutos))
        return _run_safe(handler_input, work)


class ComandoLuzHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("EncenderLuzIntent")(handler_input)
                or ask_utils.is_intent_name("ApagarLuzIntent")(handler_input))

    def handle(self, handler_input):
        def work():
            thing_name = _destino(handler_input)
            name = handler_input.request_envelope.request.intent.name
            estado = "encendido" if name == "EncenderLuzIntent" else "apagado"
            shadow = ShadowService()
            reported = shadow.read(thing_name).get("reported", {})
            if reported.get("led") not in ESTADOS_LED:
                return _answer(handler_input, "Tu tendedero no tiene la luz instalada o todavía no ha reportado su estado.")
            # Convivencia con R5: en automatico con sensor de luz, decide el sensor.
            if reported.get("modo") == "automatico" and isinstance(reported.get("oscuro"), bool):
                actual = "encendida" if reported["led"] == "encendido" else "apagada"
                return _answer(handler_input, "En modo automático la luz la controla el sensor de luz, y ahora está {}. Para controlarla tú, primero di: cambia a modo manual.".format(actual))
            shadow.request_led(thing_name, estado)
            return _answer(handler_input, "He pedido {} la luz del tendedero.".format("encender" if estado == "encendido" else "apagar"))
        return _run_safe(handler_input, work)


class ConsultarLuzHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ConsultarLuzIntent")(handler_input)

    def handle(self, handler_input):
        def work():
            thing_name = _destino(handler_input)
            reported = ShadowService().read(thing_name).get("reported", {})
            partes = []
            if isinstance(reported.get("oscuro"), bool):
                partes.append("Está oscuro." if reported["oscuro"] else "Hay luz.")
            if reported.get("led") in ESTADOS_LED:
                partes.append("La luz del tendedero está {}.".format("encendida" if reported["led"] == "encendido" else "apagada"))
            if not partes:
                return _answer(handler_input, "Tu tendedero no tiene el sensor de luz ni la luz instalados.")
            return _answer(handler_input, " ".join(partes))
        return _run_safe(handler_input, work)


class HelpHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        return _answer(handler_input, "Puedes vincular tus tendederos con su código y un nombre, preguntar qué tendederos tienes, preguntar por el agua, exponer o resguardar la ropa, consultar su posición, calibrar el sensor, cambiar a modo automático o manual, decir cuántos minutos esperar para volver a exponer, y encender, apagar o consultar la luz.")


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
builder.add_request_handler(ListarTendederosHandler())
builder.add_request_handler(ComandoPosicionHandler())
builder.add_request_handler(ConsultarAguaHandler())
builder.add_request_handler(ConsultarPosicionHandler())
builder.add_request_handler(CalibrarSensorHandler())
builder.add_request_handler(ConsultarCalibracionHandler())
builder.add_request_handler(CambiarModoHandler())
builder.add_request_handler(ConsultarModoHandler())
builder.add_request_handler(ConfigurarEsperaHandler())
builder.add_request_handler(ComandoLuzHandler())
builder.add_request_handler(ConsultarLuzHandler())
builder.add_request_handler(HelpHandler())
builder.add_request_handler(StopHandler())
builder.add_request_handler(FallbackHandler())
builder.add_exception_handler(ErrorHandler())

lambda_handler = builder.lambda_handler()
