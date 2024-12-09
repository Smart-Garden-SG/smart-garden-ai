import json
import mysql.connector
from fastapi import FastAPI, HTTPException, Query
import pandas as pd
import joblib
import logging
import httpx
from typing import Dict, Tuple
from fastapi.middleware.cors import CORSMiddleware

# Carregar o modelo salvo
model = joblib.load("fertilizer_classification_model_for_alface.pkl")

# Configurar o FastAPI
app = FastAPI()

# Adicionar middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Permitir a origem do front-end
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos os métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permitir todos os headers
)


# Dicionário de mensagens para os fertilizantes
FERTILIZER_MESSAGES = {
    "Adicionar Nitrato de Amônio (NH₄NO₃)": "Nitrogênio muito baixo, aplique fertilizantes ricos em Nitrogênio.",
    "Adicionar Superfosfato Simples": "Fósforo muito baixo, aplique fertilizantes ricos em Fósforo.",
    "Adicionar Cloreto de Potássio (KCl)": "Potássio muito baixo, aplique fertilizantes ricos em Potássio.",
    "Adicionar Enxofre Elementar": "pH fora da faixa ideal, ajuste com um regulador de pH.",
    "Adicionar Calcário": "pH fora da faixa ideal, ajuste com um regulador de pH.",
    "Não é necessário ajustar fertilizante": "Os níveis do solo estão balanceados",
}

# Configuração de logging para depuração
logging.basicConfig(level=logging.INFO)

# Mapeamento das colunas do banco para as colunas esperadas pelo modelo
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
    'Recommended Fertilizer': 'Recommended Fertilizer'  # Pode ser uma coluna de saída esperada para comparação
}

# Definição das features numéricas esperadas pelo modelo
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

# Função para fazer a predição com o modelo carregado
def predict_fertilizer_model(input_data: pd.DataFrame):
    prediction = model.predict(input_data)
    return prediction

# Função para obter os dados de clima via API usando latitude e longitude
async def get_weather_data(lat: float, lon: float, api_key: str) -> Dict[str, float]:
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
    if response.status_code == 200:
        weather_data = response.json()
        # Extrair dados relevantes de clima
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

# Função para pegar os últimos registros de cada device_id da tabela tb_measures junto com lat e lon
def get_latest_measure_data() -> list:
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="admin",
            database="smartlettuce"
        )
        cursor = connection.cursor(dictionary=True)

        # Consulta para pegar o último registro de cada device_id com lat e lon
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

# Função para inserir dados na tabela tb_events com o campo measure
def insert_event(data: Dict[str, str], measure: float):
    try:
        # Conexão com o banco de dados MySQL
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="admin",
            database="smartlettuce"
        )
        cursor = connection.cursor()

        # Query para inserir dados na tabela tb_events com "INSERT IGNORE"
        query = """
                INSERT IGNORE INTO tb_events (gene_by_ia, device_id, `desc`, level, measure, created_at)
                VALUES (%s, %s, %s, %s, %s, now())
                """


        # Concatenando a mensagem e o fertilizante previsto
        message = f"{data['predicted_fertilizer']}"

        # Definindo os valores a serem inseridos
        values = (1, data['device_id'], message, 'warning', measure)

        # Executando a query de inserção
        cursor.execute(query, values)
        connection.commit()

        # Fechando a conexão
        cursor.close()
        connection.close()
    except mysql.connector.Error as err:
        logging.error(f"Erro ao inserir dados na tabela tb_events: {err}")
        raise HTTPException(status_code=500, detail="Erro ao inserir no banco de dados")

# Função para renomear as colunas conforme o mapeamento
def rename_columns(input_data: pd.DataFrame) -> pd.DataFrame:
    return input_data.rename(columns=COLUMN_MAPPING)

# Função para garantir que os dados tenham todas as colunas de numeric_features
def prepare_input_data(input_data: pd.DataFrame) -> pd.DataFrame:
    # Adicionar colunas ausentes com valor padrão (0 ou NaN)
    for col in numeric_features:
        if col not in input_data.columns:
            input_data[col] = 0  # Ou use np.nan se preferir marcar como ausente

    # Reordenar as colunas para garantir a compatibilidade com o modelo
    input_data = input_data[numeric_features]
    
    return input_data

# Função auxiliar para gerar uma chave única para o cache de clima
def generate_weather_cache_key(lat: float, lon: float) -> Tuple[float, float]:
    return (lat, lon)

# Função para gerar eventos de temperatura e umidade com o campo measure
def generate_temp_humidity_event(device_id: int, temp: float, humidity: float):
    try:
        # Conexão com o banco de dados MySQL
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="admin",
            database="smartlettuce"
        )
        cursor = connection.cursor()

        print("temp ", temp, " humidity ", humidity)

        # Verificação de temperatura
        if 17 <= temp <= 19:
            temp_message = "Temperatura baixa... As plantas estão tremendo! ⚠️"
            temp_level = "warning"
        elif temp < 17:
            temp_message = "Congelando! 🥶 As plantas podem não resistir ao frio extremo!"
            temp_level = "critical"
        else:
            temp_message = None

        # Verificação de umidade
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

        # Inserir evento de temperatura se existir mensagem
        if temp_message:
            cursor.execute(
                "INSERT IGNORE INTO tb_events (gene_by_ia, device_id, `desc`, level, measure, created_at) VALUES (%s, %s, %s, %s, %s, now())",
                (0, device_id, temp_message, temp_level, temp)
            )

        # Inserir evento de umidade se existir mensagem
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

# Modificação no endpoint /predict para chamar a função de geração de eventos de temperatura e umidade
@app.post("/predict")
async def predict_fertilizer(api_key: str = Query(...)):
    try:
        # Obter os últimos registros de cada device_id com lat e lon
        measure_data = get_latest_measure_data()

        if not measure_data:
            return {"message": "Nenhum dado de medida válido encontrado.", "results": []}

        valid_predictions = []

        # Cache para armazenar dados climáticos já buscados
        weather_cache: Dict[Tuple[float, float], Dict[str, float]] = {}

        # Iterar sobre os dados de medida (para cada dispositivo)
        for record in measure_data:
            device_id = record['device_id']
            lat = record.get('lat')
            lon = record.get('lon')

            # Verificar se lat e lon estão presentes
            if lat is None or lon is None:
                logging.info(f"Dispositivo {device_id} sem lat ou lon. Ignorando.")
                continue

            # Gerar chave para o cache
            cache_key = generate_weather_cache_key(lat, lon)

            # Verificar se os dados climáticos já foram buscados
            if cache_key in weather_cache:
                weather_data = weather_cache[cache_key]
            else:
                # Obter os dados de clima usando latitude e longitude
                weather_data = await get_weather_data(lat, lon, api_key)
                weather_cache[cache_key] = weather_data  # Armazenar no cache

            # Criar um DataFrame com os dados para a predição
            input_data = pd.DataFrame([record])

            # Renomear as colunas para que correspondam aos nomes esperados pelo modelo
            input_data = rename_columns(input_data)

            # Adicionar os dados de clima ao input_data
            input_data["feels_like"] = weather_data["feels_like"]
            input_data["temp"] = weather_data["temp"]
            input_data["temp_min"] = weather_data["temp_min"]
            input_data["temp_max"] = weather_data["temp_max"]
            input_data["pressure"] = weather_data["pressure"]
            input_data["humidity"] = weather_data["humidity"]

            # Garantir que apenas numeric_features sejam usadas e estejam formatadas corretamente
            input_data = prepare_input_data(input_data)

            # Realizando a predição com o modelo
            prediction = predict_fertilizer_model(input_data)

            # Obter o fertilizante previsto
            predicted_fertilizer = prediction[0]

            # Determinar a medida com base no fertilizante previsto
            if "Calcário" in predicted_fertilizer or "Enxofre Elementar" in predicted_fertilizer:
                measure = record["pH"]
            elif "Nitrato de Amônio" in predicted_fertilizer:
                measure = record["Nitrogen"]
            elif "Superfosfato Simples" in predicted_fertilizer:
                measure = record["Phosphorus"]
            elif "Cloreto de Potássio" in predicted_fertilizer:
                measure = record["Potassium"]
            else:
                measure = 0  # Caso não seja necessário ajuste

            # Criar o dicionário com os dados para o insert
            event_data = {
                "device_id": device_id,
                "predicted_fertilizer": predicted_fertilizer
            }

            # Inserir os dados na tabela tb_events com a medida
            insert_event(event_data, measure)

            # Gerar eventos de temperatura e umidade
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
