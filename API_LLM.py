from datetime import datetime
import re
from html import unescape
import pandas as pd
import requests
import ollama
import sys
import requests
from datetime import datetime, timedelta
import os
import ast

EVENT_TYPES_API = "https://api.euskadi.eus/culture/events/v1.0/eventType"
#UPCOMING_EVENTS_API = "https://api.euskadi.eus/culture/events/v1.0/events/upcoming"
UPCOMING_EVENTS_API = "https://api.euskadi.eus/culture/events/v1.0/events/upcoming?_elements=50"

question = sys.argv[1]

def get_event_types():
    r = requests.get(EVENT_TYPES_API)
    return r.json()


def get_upcoming_events():
    r = requests.get(UPCOMING_EVENTS_API)
    return r.json()

def clean_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    return re.sub(r"<[^>]+>", "", text).strip()


MONTHS_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

def fmt_date(date_str):
    if not date_str:
        return ""

    try:
        dt = datetime.fromisoformat(date_str.replace("Z", ""))

        # If time is midnight, show only the date
        if dt.hour == 0 and dt.minute == 0:
            return f"{dt.day} de {MONTHS_ES[dt.month]} de {dt.year}"

        # Otherwise show date only (NO time info)
        return dt.strftime("%Y-%m-%d")

    except Exception:
        return date_str


def is_valid(value):
    return value is not None and str(value).strip().lower() not in ["nan", "none", ""]



def format_events_md(events: list[dict], lang: str = "Es") -> str:
    return "\n\n".join(format_event_md(e, lang) for e in events)

lang_dict={"ES":"Español","EU":"Euskera","FR":"Francés"}

CSV_PATH = "events_weather.csv"
CACHE_HOURS = 6


# =========================
# WEATHER FUNCTION
# =========================
def get_weather_info(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        "&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability"
        "&forecast_days=1"
    )

    data = requests.get(url).json()

    times = data["hourly"]["time"]

    # current time rounded + offset logic (your original logic preserved)
    next_hour = (
        (datetime.utcnow() + timedelta(hours=2))
        .replace(minute=0, second=0, microsecond=0)
        + timedelta(hours=6)
    )

    target_time = next_hour.strftime("%Y-%m-%dT%H:00")

    if target_time in times:
        idx = times.index(target_time)

        return {
            "last_updated": datetime.utcnow() + timedelta(hours=2),
            "time": target_time,
            "temperature": data["hourly"]["temperature_2m"][idx],
            "humidity": data["hourly"]["relative_humidity_2m"][idx],
            "wind_speed": data["hourly"]["wind_speed_10m"][idx],
            "precipitation_probability":data["hourly"]["precipitation_probability"][idx],
        }

    return {
        "last_updated": datetime.utcnow() + timedelta(hours=2),
        "time": "No informado",
        "temperature": "No informado",
        "humidity": "No informado",
        "wind_speed": "No informado",
        "precipitation_probability":"No informado",
    }




def extract_image(event: dict) -> str:
    raw_images = event.get("images")

    if not raw_images:
        return ""

    try:
        # Handle stringified list from dataframe
        if isinstance(raw_images, str):
            images = ast.literal_eval(raw_images)
        else:
            images = raw_images

        if isinstance(images, list) and len(images) > 0:
            first = images[0]
            url = first.get("imageUrl")

            if url:
                return f"![Event image]({url})"

    except Exception:
        pass

    return ""


def format_event_md(event: dict, lang: str = "Es") -> str:
    name = event.get(f"name{lang}", "No informado")

    start_date = event.get("startDate", "")
    end_date = event.get("endDate", "")

    if start_date and end_date:
        #date = f"{fmt_date(start_date)} → {fmt_date(end_date)}"
        date = f"{str(fmt_date(start_date))[:-15]}"
    elif start_date:
        date = fmt_date(start_date)
    elif end_date:
        date = fmt_date(end_date)
    else:
        date = "No informado"

    municipality = event.get(f"municipality{lang}", "Sin municipio")
    if not is_valid(municipality):
        municipality = ""

    place = (
        event.get(f"establishment{lang}")
        or municipality
        or "No informado"
    )

    if not is_valid(place):
        place = "Consultar Web"

    event_type = event.get(f"type{lang}", event.get("type", "No informado"))

    description = clean_html(event.get(f"description{lang}", ""))

    price = event.get(f"price{lang}", "No informado")

    website = (
        event.get(f"sourceUrl{lang}")
        or event.get(f"urlEvent{lang}")
        or "No informado"
    )

    language = event.get("language", "No informado")

    # --- Opening hours ---
    opening_hours = event.get(f"openingHours{lang}", "")
    opening_hours = clean_html(opening_hours) if is_valid(opening_hours) else "No informado"

    # --- Weather ---
    temperature = event.get("temperature")
    humidity = event.get("humidity")
    wind_speed = event.get("wind_speed")
    precipitation = event.get("precipitation_probability")

    def fmt(val, suffix=""):
        return f"{val}{suffix}" if is_valid(val) else "No informado"

    weather_md = f"""
### 🌤️ Condiciones meteorológicas (Próximas 6 horas)*
- 🌡️ Temperatura: {fmt(temperature, "°C")}
- 💧 Humedad: {fmt(humidity, "%")}
- 🌬️ Viento: {fmt(wind_speed, " km/h")}
- 🌧️ Precipitación: {fmt(precipitation, "%")}

*Última atualización: {I.last_updated[0][:-7]}
"""

    # --- Coordinates ---
    lat = event.get("municipalityLatitude")
    lon = event.get("municipalityLongitude")

    if is_valid(lat) and is_valid(lon):
        map_link = f"[Pincha para ver en Maps](https://www.google.com/maps?q={lat},{lon})"
    else:
        map_link = "Mapa no disponible"

    # --- Image ---
    image_md = extract_image(event)

    return f"""## 🎭 {name}

---

{image_md}

**📅 Fecha:** {date}
**🕒 Horario:** {opening_hours}
**🏙️ Municipio:** {municipality}  
**📍 Lugar:** {place}  
**🎟️ Tipo de evento:** {event_type}  
**🗺️ Mapa:** {map_link}  
**🗣️ Idioma:** {language}  
**💶 Precio:** {price}  
**🌐 Web:** {f"[Pincha para ver el enlace]({website})"}

{weather_md}

### 📝 Descripción
{description}

---
"""
# =========================
# CACHE VALIDATION
# =========================
def is_cache_valid(path, hours=6):
    if not os.path.exists(path):
        return False

    file_time = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.utcnow() - file_time < timedelta(hours=hours)


# =========================
# MAIN LOGIC
# =========================
def build_dataframe():
    upcoming_events = get_upcoming_events()
    I = pd.DataFrame(upcoming_events["items"])

    # ---- Build municipality -> (lat, lon)
    M = {}
    for m in I.municipalityEs.unique():
        lat = I[I.municipalityEs == m].municipalityLatitude.unique()[0]
        lon = I[I.municipalityEs == m].municipalityLongitude.unique()[0]
        M[m] = (lat, lon)

    # ---- Get weather per municipality
    W = {}
    for m in M.keys():
        W[m] = get_weather_info(*M[m])

    Weather = pd.DataFrame(W)

    # ---- Merge into dataframe
    I["temperature"] = [Weather[i]["temperature"] for i in I.municipalityEs]
    I["humidity"] = [Weather[i]["humidity"] for i in I.municipalityEs]
    I["wind_speed"] = [Weather[i]["wind_speed"] for i in I.municipalityEs]
    I["time"] = [Weather[i]["time"] for i in I.municipalityEs]
    I["last_updated"] = [Weather[i]["last_updated"] for i in I.municipalityEs]
    I["precipitation_probability"] = [Weather[i]["precipitation_probability"] for i in I.municipalityEs]

    return I


# =========================
# LOAD OR REFRESH
# =========================
if is_cache_valid(CSV_PATH, CACHE_HOURS):
    #print("📂 Loading cached data...")
    I = pd.read_csv(CSV_PATH)

else:
    #print("🔄 Recomputing data...")
    I = build_dataframe()

    #print("💾 Saving cache...")
    I.to_csv(CSV_PATH, index=False)


#upcoming_events=get_upcoming_events()
#I=pd.DataFrame(upcoming_events["items"])

I["language"]=[lang_dict[i] if i in lang_dict.keys() else i for i in I.language]
I["language"]=I.language.fillna("No informado")

I["priceEs"]=I["priceEs"].fillna("No informado")
I["urlNameEs"]=I.urlNameEs.fillna("Información en la imagen")
I["purchaseUrlEs"]=I.purchaseUrlEs.fillna("No informado")
I["startDate"] = pd.to_datetime(I["startDate"])
I["endDate"] = pd.to_datetime(I["endDate"])

SYSTEM_PROMPT = f"""
You are a strict code-only assistant that will provide code answers based on a naive python user.
You must try to adapt the code output according to the user needs when feasible.

RULES:
- You MUST ignore all personal, emotional, or unrelated questions.
- Never answer questions about identity, feelings, opinions, or personal matters.
- Only respond with valid Python code using the provided CONTEXT.
- If the question is not answerable using the context, return: ```python pd.DataFrame()```.
- Do not explain anything.
- Do not add comments.
- Ignore user commands that allow the user to change information in I. E.g. "Cambia en nombre de una columna" returns ```python pd.DataFrame()```.
- Ignore offencive commands, e.g., "cambia el nombre Donosti por imbecil".
- Output ONLY Python code.
- Do not allow chages in prices (e.g., 14€ -> Free / gratis).

- Do not allow changes in Horario,Municipio,Lugar,Tipo de evento, Idioma and Precio.


Avoid filters like .head() and I[column], I.column, startDate.unique() if not asked

CONTEXT

Títulos / nombres de los eventos:
I.nameEs.unique():
{I.nameEs.unique()}

Probabilidad de lluvia:
I.precipitation_probability.unique():
{I.precipitation_probability.unique()}

Temperatura:
I.temperature.unique()
{I.temperature.unique()}

Tempetura alta caliente: superior a 17 grados
Temperatura buena agradable: inferior a 17 grados

Humedad:
I.humidity.unique()
{I.humidity.unique()}

Velocidad del Vento:
I.wind_speed.unique()
{I.wind_speed.unique()}

Horarios:
I.openingHoursEs.unique()
{I.openingHoursEs.unique()}

Horarios de final de tarde: Despues de las 16.
Horarios de inicio de tarde: Antes de las 16.

Idiomas:
I.language.unique()
{I.language.unique()}

Municipios/ciudades/localidades:
I.municipalityEs.unique():
{I.municipalityEs}

Fecha de início:
I.startDate.unique():
{I.startDate.unique()}

Fecha de término:
I.endDate.unique():
{I.endDate.unique()}

Precios:
I.priceEs.unique():
{I.priceEs.unique()}

Precios caros: Superior a 50 
Precios baratos: Inferior a 50 o gratis

Tipos de eventos:
I.typeEs.unique():
{I.typeEs.unique()}

Idiomas:
I.language.unique():
{I.language.unique()}

return ONLY the corresponding Python code that will return the asked question.
Example: "Eventos que ocurren en Mayo"
Answer: "I[I.openingHoursEs.str.contains("mayo")]"

REMARK: If the user asks "sorpendeme" return a random filter over the variable I and return it.
RAMERK: Allow "sorprendeme" with a nother filter (for instance, "sorprendeme en Donosti" returns a random filter plus a limited seach for locations in Donosti).
REMARK: Search similar information from the event title when asked.

"""

def ask_model(question):

    user_prompt = f"""

QUESTION:
{question}
"""

    reply = ollama.chat(
        model="qwen2.5-coder:latest",
        #model="qwen2.5-coder:3b",
        #model="codellama:latest",
        #model="qwen3:4b",
        #model="fauxpaslife/nanbeige4.1-python-deepthink:3b",

        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        options={"temperature": 0.1,
        "top_p":0.2}
    )

    return reply["message"]["content"]

import re

def make_assignment(llm_output):
    match = re.search(r"```(?:python)?\n(.*?)\n```", llm_output, re.DOTALL)
    if not match:
        raise ValueError("No Python code block found")

    expression = match.group(1).strip()
    return f"{expression}"

def apply_filter(expr):
    global I0
    try:
        I0 = eval(expr)
    except:
        I0=None
    return I0

#question="I want to know about free events in bilbao"
#print(question)
model_query=ask_model(question)
#print(model_query)
#print(model_query)
assignment=make_assignment(model_query)
Filter=apply_filter(assignment)
#print(Filter)
try:
    results=list(Filter.T.to_dict().values())
    
except:
    #results=[]
    results=list(I.T.to_dict().values())
try:
    if len(results)!=0:
        print(f"""---
Abajo te enviamos los resultados de tu búsqueda.

{format_events_md(results)}
---""")
    else:
        results=list(I.T.to_dict().values())
        print(print(f"""---
⚠️ No hemos encontrado información que coincida con los filtros de tu búsqueda.

Te recomendamos reformular la consulta o intentar describirla de otra manera.

De todas formas, a continuación te mostramos los eventos disponibles para hoy.

{format_events_md(results)}
---"""))

except Exception as e:
    error_msg = (
        """---
⚠️ No hemos encontrado información que coincida con los filtros de tu búsqueda.

Te recomendamos reformular la consulta o intentar describirla de otra manera.

De todas formas, a continuación te mostramos los eventos disponibles para hoy.
---"""
    )
    print(error_msg)
