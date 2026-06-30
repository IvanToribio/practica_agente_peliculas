
# Este archivo contiene el código principal de la skill de Alexa pero no se ejecuta directamente.
# En la Developer Console de Alexa, se tiene la verdadera estructura de la skill.
# Este archivo utiliza formatters y movie_service que dependen también de config.py y tmdb_client.py

from __future__ import annotations

"""
Lambda principal para la skill de Alexa.
"""

import logging
from typing import Optional

import ask_sdk_core.utils as ask_utils

from ask_sdk_core.dispatch_components import (
    AbstractExceptionHandler,
    AbstractRequestHandler,
)
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model import Response

from app.formatters import (
    format_movie_for_alexa_intent,
    format_not_found_for_alexa,
)

from app.movie_service import (
    MovieServiceError,
    get_movie_by_title,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================
# Constantes
# ============================================================

SKILL_NAME = "agente peliculas"

MOVIE_TITLE_SLOT = "movie_title"
YEAR_SLOT = "year"

CONTINUE_REPROMPT = (
    "Puedes hacerme otra pregunta sobre películas, "
    "o decir salir para terminar."
)

GOODBYE_MESSAGE = "Hasta luego cocodrilo."


# ============================================================
# Funciones auxiliares
# ============================================================

def get_slot_value(handler_input, slot_name):
    # type: (HandlerInput, str) -> Optional[str]
    """
    Extrae el valor de un slot de Alexa.

    Si el slot no existe o viene vacío, devuelve None.
    """
    request = handler_input.request_envelope.request
    intent = getattr(request, "intent", None)

    if intent is None or intent.slots is None:
        return None

    slot = intent.slots.get(slot_name)

    if slot is None or slot.value is None:
        return None

    value = slot.value.strip()

    if not value:
        return None

    return value


def parse_year(year_value):
    # type: (Optional[str]) -> Optional[int]
    """
    Convierte el slot year en entero si es posible.
    """
    if year_value is None:
        return None

    clean_value = "".join(character for character in year_value if character.isdigit())

    if len(clean_value) != 4:
        return None

    try:
        return int(clean_value)
    except ValueError:
        return None


def build_response(handler_input, speak_output, reprompt=None):
    # type: (HandlerInput, str, Optional[str]) -> Response
    """
    Construye una respuesta de Alexa.

    Si recibe reprompt, mantiene la sesión abierta.
    Si no recibe reprompt, Alexa responde y termina la sesión.
    """
    response_builder = handler_input.response_builder.speak(speak_output)

    if reprompt:
        response_builder.ask(reprompt)

    return response_builder.response


def build_continue_response(handler_input, speak_output):
    # type: (HandlerInput, str) -> Response
    """
    Construye una respuesta que mantiene la skill abierta.
    """
    return build_response(
        handler_input=handler_input,
        speak_output=speak_output,
        reprompt=CONTINUE_REPROMPT,
    )


def build_end_response(handler_input, speak_output):
    # type: (HandlerInput, str) -> Response
    """
    Construye una respuesta que termina la skill.
    """
    return build_response(
        handler_input=handler_input,
        speak_output=speak_output,
        reprompt=None,
    )


def build_missing_title_response(handler_input):
    # type: (HandlerInput) -> Response
    """
    Respuesta cuando Alexa no ha entendido el título de la película.
    """
    speak_output = (
        "No he entendido el título de la película. "
        "Puedes decir, por ejemplo: quién dirigió Dune, "
        "qué nota tiene Interstellar, "
        "cuánto dura Oppenheimer, "
        "o de qué va El Padrino."
    )

    return build_continue_response(
        handler_input=handler_input,
        speak_output=speak_output,
    )


def answer_movie_intent(handler_input, intent_name):
    # type: (HandlerInput, str) -> Response
    """
    Lógica común para los intents que consultan una película.

    Esta función mantiene la skill abierta después de responder.
    """
    movie_title = get_slot_value(handler_input, MOVIE_TITLE_SLOT)
    year_value = get_slot_value(handler_input, YEAR_SLOT)
    year = parse_year(year_value)

    logger.info("Intent recibido: %s", intent_name)
    logger.info("Slot movie_title: %s", movie_title)
    logger.info("Slot year: %s", year)

    if movie_title is None:
        return build_missing_title_response(handler_input)

    try:
        movie = get_movie_by_title(
            title=movie_title,
            year=year,
        )

    except MovieServiceError:
        logger.exception("Error en movie_service al buscar la película.")

        speak_output = (
            "Ha ocurrido un problema al consultar la información de la película. "
            "Puedes probar con otra película o intentarlo de nuevo."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )

    except Exception:
        logger.exception("Error inesperado al buscar la película.")

        speak_output = (
            "Ha ocurrido un error inesperado al buscar la película. "
            "Puedes probar con otra consulta."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )

    if movie is None:
        speak_output = format_not_found_for_alexa(movie_title)

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )

    speak_output = format_movie_for_alexa_intent(
        movie=movie,
        intent_name=intent_name,
    )

    return build_continue_response(
        handler_input=handler_input,
        speak_output=speak_output,
    )


# ============================================================
# Launch Request
# ============================================================

class LaunchRequestHandler(AbstractRequestHandler):
    """
    Handler para cuando el usuario abre la skill sin lanzar un intent concreto.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = (
            f"Bienvenido a {SKILL_NAME}. "
            "Puedes preguntarme información sobre películas. "
            "Por ejemplo: quién dirigió Dune, "
            "qué nota tiene Interstellar, "
            "cuánto dura Oppenheimer, "
            "cuándo se estrenó Avatar, "
            "o qué géneros tiene El Padrino."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )


# ============================================================
# Custom Intent Handlers
# ============================================================

class SearchMovieIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("SearchMovieIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return answer_movie_intent(
            handler_input=handler_input,
            intent_name="SearchMovieIntent",
        )


class GetDirectorIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GetDirectorIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return answer_movie_intent(
            handler_input=handler_input,
            intent_name="GetDirectorIntent",
        )


class GetRatingIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GetRatingIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return answer_movie_intent(
            handler_input=handler_input,
            intent_name="GetRatingIntent",
        )


class GetReleaseDateIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GetReleaseDateIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return answer_movie_intent(
            handler_input=handler_input,
            intent_name="GetReleaseDateIntent",
        )


class GetRuntimeIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GetRuntimeIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return answer_movie_intent(
            handler_input=handler_input,
            intent_name="GetRuntimeIntent",
        )


class GetOverviewIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GetOverviewIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return answer_movie_intent(
            handler_input=handler_input,
            intent_name="GetOverviewIntent",
        )


class GetGenresIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GetGenresIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return answer_movie_intent(
            handler_input=handler_input,
            intent_name="GetGenresIntent",
        )


# ============================================================
# Amazon Built-in Intent Handlers
# ============================================================

class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = (
            "Puedes preguntarme información sobre películas. "
            "Por ejemplo: quién dirigió Dune, "
            "qué nota tiene Interstellar, "
            "cuánto dura Oppenheimer, "
            "cuándo se estrenó Avatar, "
            "de qué va El Padrino, "
            "o qué géneros tiene Matrix."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """
    Este handler SÍ cierra la skill.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input)
            or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)
        )

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return build_end_response(
            handler_input=handler_input,
            speak_output=GOODBYE_MESSAGE,
        )


class NavigateHomeIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.NavigateHomeIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = (
            f"Estás en {SKILL_NAME}. "
            "Puedes preguntarme por el director, la nota, la duración, "
            "la fecha de estreno, la sinopsis o los géneros de una película."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")

        speak_output = (
            "No he entendido bien la consulta. "
            "Puedes decir, por ejemplo: quién dirigió Dune, "
            "qué nota tiene Interstellar, "
            "cuánto dura Oppenheimer, "
            "o de qué va El Padrino."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """
    Alexa llama a este handler cuando la sesión ya ha terminado.
    Aquí no se responde con voz.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """
    Handler de debug. Debe ir al final.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)

        speak_output = (
            f"Has lanzado el intent {intent_name}, "
            "pero todavía no está implementado."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )


# ============================================================
# Exception Handler
# ============================================================

class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = (
            "Lo siento, ha ocurrido un problema al procesar tu consulta. "
            "Puedes probar otra vez o decir salir para terminar."
        )

        return build_continue_response(
            handler_input=handler_input,
            speak_output=speak_output,
        )


# ============================================================
# Skill Builder
# ============================================================

sb = SkillBuilder()

# Launch
sb.add_request_handler(LaunchRequestHandler())

# Custom intents
sb.add_request_handler(SearchMovieIntentHandler())
sb.add_request_handler(GetDirectorIntentHandler())
sb.add_request_handler(GetRatingIntentHandler())
sb.add_request_handler(GetReleaseDateIntentHandler())
sb.add_request_handler(GetRuntimeIntentHandler())
sb.add_request_handler(GetOverviewIntentHandler())
sb.add_request_handler(GetGenresIntentHandler())

# Amazon built-in intents
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(NavigateHomeIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

# Debug handler. Debe ir siempre el último.
sb.add_request_handler(IntentReflectorHandler())

# Exception handler
sb.add_exception_handler(CatchAllExceptionHandler())

# Entry point de AWS Lambda / Alexa-hosted
lambda_handler = sb.lambda_handler()