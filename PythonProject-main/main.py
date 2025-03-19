import json
import os
import re
import time
from urllib.parse import parse_qs

import httpx
import pandas as pd
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

load_dotenv()

CLICKSEND_USERNAME = os.getenv("CLICKSEND_USERNAME")
CLICKSEND_API_KEY = os.getenv("CLICKSEND_API_KEY")
CLICKSEND_SMS_URL = os.getenv("CLICKSEND_SMS_URL")
DEDICATED_NUMBER = os.getenv("DEDICATED_NUMBER")

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_DB = os.getenv("REDIS_DB")

EXCEL_FILE = os.getenv("EXCEL_FILE")
TIMEOUT_SECONDS = os.getenv("TIMEOUT_SECONDS")
VALID_TSHIRT_SIZES = {
    "CHICO",
    "MEDIANO",
    "GRANDE",
    "X GRANDE",
    "XX GRANDE",
    "JOVENES CHICO",
    "JOVENES MEDIANO",
    "JOVENES GRANDE",
}
MESSAGES = {
    "new": "Hola! Este es un numero automatico de Nuestra Casa para ayudarle ordenar sus camisetas para nuestra Caminata el 27 de Abril! Por favor responde con su nombre.",
    "awaiting_name": "¡Gracias! ¿Cómo se llama la persona que estás honrando?",
    "awaiting_lastname": "Por favor, dime su nombre y apellido.",
    "awaiting_honoree": "Por favor, completa la frase: Estoy caminando en memoria de ____________ (ejemplo: mi abuelo, mi hermana, mi hija).",
    "awaiting_relationship": "¿Qué tamaño de camiseta quiere ordenar? Tenemos CHICO/MEDIANO/GRANDE/X GRANDE/XX GRANDE/JOVENES CHICO/JOVENES MEDIANO/JOVENES GRANDE.",
    "completed": "¡Gracias por sus respuestas! ¡Nos vemos el 27 de Abril!",
    "invalid_name": "Lo siento, ingrese un nombre válido (solo letras y espacios, mínimo 2 caracteres).",
    "invalid_tshirt": "Por favor, seleccione una talla de la lista: CHICO, MEDIANO, GRANDE, X GRANDE, XX GRANDE, JOVENES CHICO, JOVENES MEDIANO, JOVENES GRANDE.",
}

DATA = {}


app = FastAPI()


def es_nombre_valido(nombre):
    """Valida que el nombre solo contenga letras en español y espacios."""
    return bool(re.match(r"^[A-Za-zÁÉÍÓÚÑÜáéíóúñü ]{2,50}$", nombre))


def es_talla_valida(talla):
    """Valida que la talla ingresada sea una de las opciones permitidas."""
    return talla.upper() in VALID_TSHIRT_SIZES


def send_sms(phone: str, message: str):
    payload = {"messages": [{"body": message, "to": phone, "from": DEDICATED_NUMBER}]}
    auth = (CLICKSEND_USERNAME, CLICKSEND_API_KEY)
    try:
        response = httpx.post(CLICKSEND_SMS_URL, json=payload, auth=auth, timeout=10)
        response.raise_for_status()
        return
    except httpx.HTTPError as e:
        print(f"Failed to send SMS to {phone}: {str(e)}")


def extract_image_url_and_text(body: str):
    url_pattern = re.compile(
        r"(http|ftp|https):\/\/([\w_-]+(?:\.[\w_-]+)+)([\w.,@?^=%&:/~+#-]*)"
    )

    match = url_pattern.findall(body)
    if match:
        media_url = "://".join(match[0][:2]) + match[0][2]
        text = body.replace(media_url, "").strip().replace("\\n", "").strip()
    else:
        media_url = None
        text = body.strip()

    return media_url, text


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    print("Inbound message received")

    try:
        raw_body = await request.body()
        form_data = parse_qs(raw_body.decode())
        print("Parsed form data:", form_data)

        phone = form_data.get("from", [""])[0]
        body = form_data.get("body", [""])[0].strip() if "body" in form_data else ""

        media_url, text = extract_image_url_and_text(body)

        if not phone:
            raise HTTPException(status_code=400, detail="Missing required fields")

        background_tasks.add_task(process_message, phone, text, media_url)
        return {"status": "received", "media_url": media_url, "text": text}

    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


def send_response(phone, message):
    """Send an SMS response to the user."""
    send_sms(phone, message)


def process_message(phone: str, text: str, media_url: str = None):
    try:
        session_data = DATA.get(phone, None)
        session = (
            json.loads(session_data)
            if session_data
            else {"state": "new", "image_url": media_url}
        )

        state = session.get("state")

        state_handlers = {
            "new": handle_new_state,
            "awaiting_name": handle_awaiting_name,
            "awaiting_lastname": handle_awaiting_lastname,
            "awaiting_honoree": handle_awaiting_honoree,
            "awaiting_relationship": handle_awaiting_relationship,
            "awaiting_tshirt": handle_awaiting_tshirt,
        }

        handler = state_handlers.get(state)
        if handler:
            handler(phone, text, session)

        session["last_update"] = time.time()
        DATA[phone] = json.dumps(session)

        if session["state"] == "completed":
            DATA.pop(phone, None)

    except Exception as e:
        print(f"Error processing message from {phone}: {str(e)}")


def handle_new_state(phone, text, session):
    send_response(phone, MESSAGES["new"])
    session["state"] = "awaiting_name"


def handle_awaiting_name(phone, text, session):
    names = text.strip().split()
    status_message = None
    if len(names) >= 2:
        first_name = names[0]
        last_name = " ".join(names[1:])
        if es_nombre_valido(first_name):
            session.update(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "state": "awaiting_honoree",
                }
            )
            status_message = "awaiting_name"
        else:
            status_message = "invalid_name"
    else:
        if es_nombre_valido(text):
            status_message = "awaiting_lastname"
            session.update({"first_name": text, "state": "awaiting_lastname"})
        else:
            status_message = "invalid_name"
    send_response(phone, MESSAGES[status_message])


def handle_awaiting_lastname(phone, text, session):
    send_response(phone, MESSAGES["awaiting_name"])
    session.update({"last_name": text, "state": "awaiting_honoree"})


def handle_awaiting_honoree(phone, text, session):
    if es_nombre_valido(text):
        send_response(phone, MESSAGES["awaiting_honoree"])
        session.update({"honoree_name": text, "state": "awaiting_relationship"})
    else:
        send_response(phone, MESSAGES["invalid_name"])


def handle_awaiting_relationship(phone, text, session):
    if es_nombre_valido(text):
        send_response(phone, MESSAGES["awaiting_relationship"])
        session.update({"relationship": text, "state": "awaiting_tshirt"})
    else:
        send_response(phone, MESSAGES["invalid_name"])


def handle_awaiting_tshirt(phone, text, session):
    if es_talla_valida(text):
        send_response(phone, MESSAGES["completed"])
        session.update({"tshirt_size": text, "state": "completed"})
        save_to_excel(session, phone)
    else:
        send_response(phone, MESSAGES["invalid_tshirt"])


def save_to_excel(session, phone):
    try:
        new_data = pd.DataFrame([{**session, "phone": phone}])

        if os.path.exists(f"responses/{EXCEL_FILE}"):
            try:
                existing_df = pd.read_excel(
                    f"responses/{EXCEL_FILE}", engine="openpyxl"
                )
            except Exception as e:
                print(f"Error reading existing Excel file: {e}")
                existing_df = pd.DataFrame()

            df = pd.concat([existing_df, new_data], ignore_index=True)
        else:
            df = new_data

        df.to_excel(f"responses/{EXCEL_FILE}", index=False, engine="openpyxl")
        print("Data saved successfully")

    except Exception as e:
        print(f"Error saving to Excel: {str(e)}")
