
# 🌿 Smart-Garden AI 🤖

Bem-vindo ao **Smart-Garden AI**! Esta aplicação utiliza Inteligência Artificial para recomendar fertilizantes específicos para otimizar o cultivo de alface! 🥬✨

---

## 🤖 Inteligência Artificial no Smart-Garden

### 🌾 Como o CatBoost Recomenda Fertilizantes

---

### 🧪 **Etapas da Recomendação**

1. **Coleta dos Dados**:  
   - Sensores de solo medem os seguintes parâmetros:  
     - **Nitrogênio (mg/kg)**  
     - **Fósforo (mg/kg)**  
     - **Potássio (mg/kg)**  
     - **pH**  
     - **Condutividade elétrica**  
     - **Temperatura do solo (°C)**  
     - **Umidade (%RH)**  
     - **Salinidade (mg/L)**  
     - **Sólidos Totais Dissolvidos (TDS) (mg/L)**  
   - Dados climáticos fornecidos pela API da **OpenWeather**:  
     - **Temperatura ambiente (°C)**  
     - **Umidade do ar (%)**  
     - **Pressão atmosférica (hPa)**  

2. **Armazenamento**:  
   Os dados coletados são armazenados no banco de dados na tabela `tb_measures`.

3. **Entrada na Tela de Recomendações**:  
   Quando o usuário acessa a tela de recomendações, a aplicação web faz uma requisição para a **API de IA** desenvolvida com **FastAPI**.

4. **Predição com o CatBoost**:  
   O modelo **CatBoost** é carregado e processa os dados recebidos. O modelo foi treinado para identificar quais características do solo estão fora dos padrões ideais para o cultivo de alface.

5. **Lógica de Decisão**:  
   O **CatBoost** avalia os seguintes parâmetros:  
   - **Níveis de Nutrientes**:  
     - **Nitrogênio** baixo → Recomenda **Nitrato de Amônio (NH₄NO₃)**  
     - **Fósforo** baixo → Recomenda **Superfosfato Simples**  
     - **Potássio** baixo → Recomenda **Cloreto de Potássio (KCl)**  
   - **pH do Solo**:  
     - **pH < 6.0** → Recomenda **Enxofre Elementar** para acidificar o solo.  
     - **pH > 7.0** → Recomenda **Calcário** para corrigir a alcalinidade.  
   - **Parâmetros Gerais**:  
     - Se os níveis estão equilibrados → Recomenda **Fertilizante Completo (NPK)**.  

6. **Geração da Recomendação**:  
   - A IA gera a recomendação do fertilizante apropriado.  
   - Um novo evento é inserido na tabela `tb_events` com a recomendação gerada.

7. **Visualização na Interface**:  
   - A recomendação é exibida na tela de eventos da aplicação web para que o usuário possa agir de acordo com a necessidade do solo.

---

### 🔄 **Exemplo de Funcionamento**

**Dados de Entrada**:  
```plaintext
Nitrogênio: 20 mg/kg  
Fósforo: 10 mg/kg  
Potássio: 80 mg/kg  
pH: 5.5  
Condutividade: 2.89 µS/cm  
Temperatura do Solo: 28.43 °C  
Umidade: 52.27 %RH  
Salinidade: 93.12 mg/L  
TDS: 415.67 mg/L  
Fator de Condutividade: 2.47  
Fator de Salinidade: 9.85  
Sensação Térmica: 32.55 °C  
Temperatura: 30.45 °C  
Temperatura Mínima: 22.99 °C  
Temperatura Máxima: 35.25 °C  
Pressão: 1005.52 hPa  
Umidade Relativa: 58.37 %  
```

**Predição do CatBoost**:  
- O modelo identifica que o nível de **nitrogênio** está baixo e o **pH** está ácido.

**Recomendação**:  
- **Nitrato de Amônio (NH₄NO₃)** para corrigir o nível de nitrogênio.  
- **Enxofre Elementar** para ajustar o pH.

---

### 📝 **Resumo do Processo**

1. **Entrada**: Dados do solo e clima.  
2. **Processamento**: O **CatBoost** analisa os dados e identifica deficiências no solo.  
3. **Recomendação**: O fertilizante adequado é sugerido com base nas deficiências detectadas.  
4. **Saída**: A recomendação é armazenada em `tb_events` e exibida na interface da aplicação.

---

## 🚀 Como Rodar o Projeto

1. **Instale as dependências**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Execute a aplicação FastAPI**:

   ```bash
   python main.py
   ```

3. **Acesse a documentação da API**:

   ```
   http://localhost:8000/docs
   ```

---

🌱 **Happy Gardening!** 🌿
