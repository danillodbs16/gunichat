from datetime import datetime
import re
from html import unescape
import pandas as pd
import requests
#import ollama
import sys
import requests
from datetime import datetime, timedelta
import os
import ast
import spacy

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


nlp = spacy.load("es_core_news_sm")


def get_dataframe_filter(query, I):
    doc = nlp(query)
    query_lower = query.lower()

    filters = []

    # ==========================================================
    # MUNICIPALITY
    # ==========================================================

    municipalities = (
        I["municipalityEs"]
        .dropna()
        .astype(str)
        .unique()
    )

    for municipality in municipalities:
        if municipality.lower() in query_lower:
            filters.append(
                f'I["municipalityEs"].fillna("").str.lower() == '
                f'"{municipality.lower()}"'
            )
            break

    # ==========================================================
    # DATE
    # ==========================================================

    if "hoy" in query_lower:
        filters.append(
            'pd.to_datetime(I["startDate"], errors="coerce").dt.date '
            '== pd.Timestamp.today().date()'
        )

    elif "mañana" in query_lower:
        filters.append(
            'pd.to_datetime(I["startDate"], errors="coerce").dt.date '
            '== (pd.Timestamp.today() + pd.Timedelta(days=1)).date()'
        )

    # ==========================================================
    # ONLINE
    # ==========================================================

    if "online" in query_lower:
        filters.append(
            'I["online"] == True'
        )

    # ==========================================================
    # FREE EVENTS
    # ==========================================================

    if any(word in query_lower for word in [
        "gratis",
        "gratuito",
        "gratuita"
    ]):
        filters.append(
            'I["priceEs"].fillna("").str.lower()'
            '.str.contains("gratis|gratuito")'
        )

    # ==========================================================
    # PRICE
    #
    # Examples:
    #   "hasta 10 euros"
    #   "menos de 20 euros"
    #   "por debajo de 15 euros"
    # ==========================================================

    price_match = re.search(
        r'(?:hasta|menos de|menor de|por debajo de|máximo de|'
        r'maximo de|como máximo)\s*(\d+(?:[.,]\d+)?)\s*'
        r'(?:€|euros?|eur)?',
        query_lower
    )

    if price_match:

        price = float(
            price_match.group(1).replace(",", ".")
        )

        filters.append(
            f'pd.to_numeric('
            f'I["priceEs"].astype(str)'
            f'.str.extract(r"(\\d+(?:[.,]\\d+)?)")[0]'
            f'.str.replace(",", ".", regex=False), '
            f'errors="coerce") <= {price}'
        )

    # ==========================================================
    # WEATHER: PRECIPITATION
    #
    # Examples:
    #   "baja precipitación"
    #   "precipitación hasta 20%"
    #   "lluvia menor de 30%"
    # ==========================================================

    low_precip = any(phrase in query_lower for phrase in [
        "baja precipitación",
        "baja precipitacion",
        "poca precipitación",
        "poca precipitacion",
        "poca lluvia",
        "baja lluvia",
        "pocas lluvias"
    ])

    precip_match = re.search(
        r'(?:precipitación|precipitacion|lluvia|lluvias)'
        r'.*?(?:hasta|menos de|menor de|por debajo de|máximo de|maximo de)'
        r'\s*(\d+(?:[.,]\d+)?)\s*%?',
        query_lower
    )

    if precip_match:

        precipitation = float(
            precip_match.group(1).replace(",", ".")
        )

        filters.append(
            f'pd.to_numeric(I["precipitation_probability"], '
            f'errors="coerce") <= {precipitation}'
        )

    elif low_precip:

        # Default threshold for "baja precipitación"
        filters.append(
            'pd.to_numeric(I["precipitation_probability"], '
            'errors="coerce") <= 20'
        )

    # ==========================================================
    # WEATHER: TEMPERATURE
    #
    # Examples:
    #   "hasta 20 grados"
    #   "menos de 20 grados"
    #   "temperatura máxima de 20"
    # ==========================================================

    temp_match = re.search(
        r'(?:hasta|menos de|menor de|por debajo de|máximo de|maximo de)'
        r'\s*(\d+(?:[.,]\d+)?)\s*'
        r'(?:grados?|°c|°)?',
        query_lower
    )

    # Only interpret this as temperature if the query contains
    # temperature-related words.
    if temp_match and any(word in query_lower for word in [
        "grado",
        "grados",
        "temperatura",
        "temperaturas",
        "°c"
    ]):

        temperature = float(
            temp_match.group(1).replace(",", ".")
        )

        filters.append(
            f'pd.to_numeric(I["temperature"], '
            f'errors="coerce") <= {temperature}'
        )

    # ==========================================================
    # EVENT TYPE
    # ==========================================================

    type_mapping = {
        "concierto": "música",
        "conciertos": "música",
        "música": "música",
        "musica": "música",

        "teatro": "teatro",

        "cine": "cine",

        "exposición": "exposición",
        "exposiciones": "exposición",
        "exposicion": "exposición",

        "festival": "festival",

        "taller": "taller",
    }

    for keyword, event_type in type_mapping.items():

        if keyword in query_lower:

            filters.append(
                f'I["typeEs"].fillna("").str.lower()'
                f'.str.contains("{event_type}", regex=False)'
            )

            break

    # ==========================================================
    # RETURN
    # ==========================================================

    if not filters:
        return "pd.DataFrame()"

    return "I["+" & ".join(
        f"({filter_expression})"
        for filter_expression in filters
    )+"]".replace("df","I")


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
#model_query=ask_model(question)
#print(model_query)
#print(model_query)
#assignment=make_assignment(model_query)
#Filter=apply_filter(assignment)
Filter=eval(get_dataframe_filter(question, I))
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

{format_events_md(results)}
---"""))

except Exception as e:
    error_msg = (
        """---
⚠️ No hemos encontrado información que coincida con los filtros de tu búsqueda.

Te recomendamos reformular la consulta o intentar describirla de otra manera.

---"""
    )
    print(error_msg)
