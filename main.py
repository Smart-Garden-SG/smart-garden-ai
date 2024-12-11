import json
import mysql.connector
from fastapi import FastAPI, HTTPException, Query
import pandas as pd
import joblib
import logging
import httpx
from typing import Dict, Tuple
from fastapi.middleware.cors import CORSMiddleware

model = joblib.load("fertilizer_classification_model_for_alface.pkl")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FERTILIZER_MESSAGES = {
    "Adicionar Nitrato de Amônio (NH₄NO₃)": "Nitrogênio muito baixo, aplique fertilizantes ricos em Nitrogênio.",
    "Adicionar Superfosfato Simples": "Fósforo muito baixo, aplique fertilizantes ricos em Fósforo.",
    "Adicionar Cloreto de Potássio (KCl)": "Potássio muito baixo, aplique fertilizantes ricos em Potássio.",
    "Adicionar Enxofre Elementar": "pH fora da faixa ideal, ajuste com um regulador de pH.",
    "Adicionar Calcário": "pH fora da faixa ideal, ajuste com um regulador de pH.",
    "Não é necessário ajustar fertilizante": "Os níveis do solo estão balanceados",
}

logging.basicConfig(level=logging.INFO)

COLUMN_MAPPING = {
    'Nitrogen': 'Nitrogen (mg/kg)',
    'Phosphorus': 'Phosphorus (mg/kg)',
    'Potassium': 'Potassium (mg/kg)',
    'pH': 'pH',
    'Conductivity': 'Conductivity (us/cm)',
    'Temperature Soil': 'Temperature Soil (°C)',
    'Humidity': 'Humidity (%RH)',
    'Salinity': 'Salinity (mg/L)',
    'TDS': 'TDS (mg/L)',
    'Conductivity factor': 'Conductivity factor',
    'Salinity factor': 'Salinity factor',
    'feels_like': 'feels_like',
    'temp': 'temp',
    'temp_min': 'temp_min',
    'temp_max': 'temp_max',
    'pressure': 'pressure',
    'humidity': 'humidity',
    'Recommended Fertilizer': 'Recommended Fertilizer'
}

numeric_features = [
    'Nitrogen (mg/kg)',
    'Phosphorus (mg/kg)',
    'Potassium (mg/kg)',
    'pH',
    'Conductivity (us/cm)',
    'Temperature Soil (°C)',
    'Humidity (%RH)',
    'Salinity (mg/L)',
    'TDS (mg/L)',
    'Conductivity factor',
    'Salinity factor',
    'feels_like',
    'temp',
    'temp_min',
    'temp_max',
    'pressure',
    'humidity'
]

def predict_fertilizer_model(input_data: pd.DataFrame):
    prediction = model.predict(input_data)
    return prediction

async def get_weather_data(lat: float, lon: float, api_key: str) -> Dict[str, float]:
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid=6d2a222c0a4cb9354b52687ceb0ddf1f&units=metric"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
    if response.status_code == 200:
        weather_data = response.json()

        return {
            "feels_like": weather_data["main"]["feels_like"],
            "temp": weather_data["main"]["temp"],
            "temp_min": weather_data["main"]["temp_min"],
            "temp_max": weather_data["main"]["temp_max"],
            "pressure": weather_data["main"]["pressure"],
            "humidity": weather_data["main"]["humidity"]
        }
    else:
        raise HTTPException(status_code=500, detail="Erro ao consultar a API de clima")

def get_latest_measure_data() -> list:
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="admin",
            database="smartlettuce"
        )
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT m.*, d.lat, d.lon
        FROM tb_measures m
        JOIN tb_devices d ON m.device_id = d.id
        WHERE (m.device_id, m.created_at) IN (
            SELECT device_id, MAX(created_at)
            FROM tb_measures
            GROUP BY device_id
        )
        AND d.lat IS NOT NULL AND d.lon IS NOT NULL
        """
        cursor.execute(query)
        data = cursor.fetchall()
        cursor.close()
        connection.close()

        return data
    except mysql.connector.Error as err:
        logging.error(f"Erro ao consultar o banco de dados: {err}")
        raise HTTPException(status_code=500, detail="Erro ao acessar o banco de dados")

def insert_event(data: Dict[str, str], measure: float):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="admin",
            database="smartlettuce"
        )
        cursor = connection.cursor()

        query = """
                INSERT IGNORE INTO tb_events (gene_by_ia, device_id, `desc`, level, measure, created_at)
                VALUES (%s, %s, %s, %s, %s, now())
                """

        message = f"{data['predicted_fertilizer']}"

        values = (1, data['device_id'], message, 'warning', measure)

        cursor.execute(query, values)
        connection.commit()

        cursor.close()
        connection.close()
    except mysql.connector.Error as err:
        logging.error(f"Erro ao inserir dados na tabela tb_events: {err}")
        raise HTTPException(status_code=500, detail="Erro ao inserir no banco de dados")

def rename_columns(input_data: pd.DataFrame) -> pd.DataFrame:
    return input_data.rename(columns=COLUMN_MAPPING)

def prepare_input_data(input_data: pd.DataFrame) -> pd.DataFrame:
    for col in numeric_features:
        if col not in input_data.columns:
            input_data[col] = 0

    input_data = input_data[numeric_features]
    
    return input_data

def generate_weather_cache_key(lat: float, lon: float) -> Tuple[float, float]:
    return (lat, lon)

def generate_temp_humidity_event(device_id: int, temp: float, humidity: float):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="admin",
            database="smartlettuce"
        )
        cursor = connection.cursor()

        print("temp ", temp, " humidity ", humidity)

        if 17 <= temp <= 19:
            temp_message = "Temperatura baixa... As plantas estão tremendo! ⚠️"
            temp_level = "warning"
        elif temp < 17:
            temp_message = "Congelando! 🥶 As plantas podem não resistir ao frio extremo!"
            temp_level = "critical"
        else:
            temp_message = None

        if 60 <= humidity <= 70:
            humidity_message = "Umidade no limite! 💦 Atenção para evitar fungos."
            humidity_level = "warning"
        elif humidity < 60:
            humidity_message = "Umidade muito baixa! 🌵 As plantas estão ressecando!"
            humidity_level = "critical"
        elif humidity > 70:
            humidity_message = "Umidade excessiva! 🌧️ Risco de fungos."
            humidity_level = "critical"
        else:
            humidity_message = None

        if temp_message:
            cursor.execute(
                "INSERT IGNORE INTO tb_events (gene_by_ia, device_id, `desc`, level, measure, created_at) VALUES (%s, %s, %s, %s, %s, now())",
                (0, device_id, temp_message, temp_level, temp)
            )

        if humidity_message:
            cursor.execute(
                "INSERT IGNORE INTO tb_events (gene_by_ia, device_id, `desc`, level, measure, created_at) VALUES (%s, %s, %s, %s, %s, now())",
                (0, device_id, humidity_message, humidity_level, humidity)
            )

        connection.commit()
        cursor.close()
        connection.close()

    except mysql.connector.Error as err:
        logging.error(f"Erro ao inserir eventos de temperatura e umidade: {err}")
        raise HTTPException(status_code=500, detail="Erro ao inserir eventos no banco de dados")    

@app.post("/predict")
async def predict_fertilizer(api_key: str = Query(...)):
    try:
        measure_data = get_latest_measure_data()

        if not measure_data:
            return {"message": "Nenhum dado de medida válido encontrado.", "results": []}

        valid_predictions = []

        weather_cache: Dict[Tuple[float, float], Dict[str, float]] = {}

        for record in measure_data:
            device_id = record['device_id']
            lat = record.get('lat')
            lon = record.get('lon')

            if lat is None or lon is None:
                logging.info(f"Dispositivo {device_id} sem lat ou lon. Ignorando.")
                continue

            cache_key = generate_weather_cache_key(lat, lon)

            if cache_key in weather_cache:
                weather_data = weather_cache[cache_key]
            else:
                weather_data = await get_weather_data(lat, lon, api_key)
                weather_cache[cache_key] = weather_data

            input_data = pd.DataFrame([record])

            input_data = rename_columns(input_data)

            input_data["feels_like"] = weather_data["feels_like"]
            input_data["temp"] = weather_data["temp"]
            input_data["temp_min"] = weather_data["temp_min"]
            input_data["temp_max"] = weather_data["temp_max"]
            input_data["pressure"] = weather_data["pressure"]
            input_data["humidity"] = weather_data["humidity"]

            input_data = prepare_input_data(input_data)

            prediction = predict_fertilizer_model(input_data)

            predicted_fertilizer = prediction[0]

            if "Calcário" in predicted_fertilizer or "Enxofre Elementar" in predicted_fertilizer:
                measure = record["pH"]
            elif "Nitrato de Amônio" in predicted_fertilizer:
                measure = record["Nitrogen"]
            elif "Superfosfato Simples" in predicted_fertilizer:
                measure = record["Phosphorus"]
            elif "Cloreto de Potássio" in predicted_fertilizer:
                measure = record["Potassium"]
            else:
                measure = 0

            event_data = {
                "device_id": device_id,
                "predicted_fertilizer": predicted_fertilizer
            }

            insert_event(event_data, measure)

            generate_temp_humidity_event(device_id, record["Temperature"], record["Humidity"])

            valid_predictions.append({
                "device_id": device_id,
                "predicted_fertilizer": predicted_fertilizer
            })

        return {
            "message": "Predição realizada com sucesso para os dispositivos válidos.",
            "results": valid_predictions
        }

    except Exception as e:
        logging.error(f"Erro na predição: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar a predição")
