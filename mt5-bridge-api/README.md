# MT5 Bridge API

Servicio Python que actúa como puente entre cualquier cliente HTTP y MetaTrader 5 (Exness).  
Expone endpoints REST para consultar la cuenta, obtener candles históricos y gestionar órdenes con deduplicación por `order_id`. Persiste en PostgreSQL y expone métricas Prometheus + trazas OpenTelemetry.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Trading Bot (Windows)                 │
│                                                         │
│  ┌──────────────┐   HTTP    ┌──────────────────────┐    │
│  │  Any client  │ ────────► │  FastAPI (port 8000) │    │
│  └──────────────┘           │  mt5_bridge service  │    │
│                             └──────────┬─────────── ┘   │
│                                        │ IPC             │
│                             ┌──────────▼──────────┐     │
│                             │ MetaTrader5 Terminal │     │
│                             │  (Exness)            │     │
│                             └──────────────────────┘     │
│                                        │ TCP:30432        │
│                             ┌──────────▼──────────┐     │
│                             │ PostgreSQL (K8s)     │     │
│                             │  minikube NodePort   │     │
│                             └──────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

---

## Prerrequisitos

- **Windows 10/11 x64** — la librería `MetaTrader5` de Python solo funciona en Windows
- **MetaTrader 5** instalado (terminal de Exness: https://www.exness.com/trading/platforms/)
- **Python 3.11+** — `winget install Python.Python.3.11`
- **minikube** — para PostgreSQL local en Kubernetes
- **kubectl** — viene con minikube

---

## Estructura del proyecto

```
Trading Bot/
├── mt5-bridge-api/
│   ├── src/mt5_bridge/
│   │   ├── main.py                   ← FastAPI app + lifespan
│   │   ├── config.py                 ← Settings desde .env
│   │   ├── dependencies.py           ← get_session(), get_mt5()
│   │   ├── api/v1/
│   │   │   ├── account.py            ← GET /account
│   │   │   ├── orders.py             ← POST / DELETE / PATCH orders
│   │   │   └── candles.py            ← GET /tick/{symbol}
│   │   ├── services/
│   │   │   ├── mt5_connection.py     ← Singleton + ThreadPoolExecutor
│   │   │   ├── order_service.py      ← open/close/modify + dedupe
│   │   │   ├── candle_service.py     ← copy_rates_range
│   │   │   └── account_service.py
│   │   ├── repositories/
│   │   │   └── order_repository.py   ← CRUD order_map + exec_reports
│   │   ├── models/db/                ← SQLAlchemy ORM models
│   │   ├── models/schemas/           ← Pydantic request/response schemas
│   │   ├── exceptions/               ← Domain exceptions
│   │   └── metrics/                  ← Prometheus + OpenTelemetry
│   ├── tests/
│   ├── .env.example
│   ├── requirements.txt
│   └── pyproject.toml
├── postgres-k8s/                     ← Manifests K8s para PostgreSQL
│   ├── README.md                     ← Instrucciones detalladas K8s
│   └── ...
└── mt5_bridge_postman_collection.json
```

---

## Setup paso a paso

### 1 — Levantar PostgreSQL en Kubernetes

Sigue el [postgres-k8s/README.md](postgres-k8s/README.md) para el setup completo.  
Resumen rápido:

```cmd
:: Asegúrate de que Docker Desktop esté corriendo
minikube start --driver=docker --cpus=2 --memory=2048

cd postgres-k8s
kubectl apply -f namespace.yaml -f configmap.yaml -f configmap-init.yaml -f secret.yaml -f statefulset.yaml -f service.yaml

:: Espera a que el pod esté Running
kubectl get pods -n trading -w
```

#### Abrir el túnel local (mantener esta terminal abierta)

Con el driver Docker de minikube en Windows, los puertos no son accesibles directamente.  
El `port-forward` crea el túnel `localhost:5432 → postgres-0:5432`:

```cmd
kubectl port-forward svc/postgres -n trading 5432:5432
```

O en segundo plano:

```powershell
# PowerShell
Start-Process kubectl -ArgumentList 'port-forward svc/postgres -n trading 5432:5432' -WindowStyle Minimized
```

```cmd
:: CMD
start /min kubectl port-forward svc/postgres -n trading 5432:5432
```

PostgreSQL queda en `localhost:5432`. Configura pgAdmin con:  
Host: `localhost` · Port: `5432` · User: `trading_user` · Password: `trading_pass_local` · DB: `trading_db`

---

### 2 — Configurar el entorno Python

```cmd
cd "c:\Users\sebas\Desktop\Trading Bot\mt5-bridge-api"

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
pip install -e .
```

---

### 3 — Configurar variables de entorno

Copia el ejemplo y rellena tus credenciales:

```cmd
copy .env.example .env
```

Edita `.env`:

```env
# MetaTrader 5
MT5_LOGIN=12345678
MT5_PASSWORD=tu_contraseña_mt5
MT5_SERVER=Exness-MT5Trial3
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# PostgreSQL — NodePort en la IP privada de minikube (no expuesta a internet)
# Reemplaza la IP con la salida de: minikube ip
DB_URL=postgresql+asyncpg://trading_user:trading_pass_local@192.168.49.2:30432/trading_db

APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

> **Importante:** el terminal de MT5 debe estar abierto y con sesión activa antes de arrancar el servicio.

---

### 4 — Arrancar el servicio

```cmd
cd "c:\Users\sebas\Desktop\Trading Bot\mt5-bridge-api"
.venv\Scripts\activate
python -m mt5_bridge.main
```

O con uvicorn directamente:

```cmd
uvicorn mt5_bridge.main:app --host 0.0.0.0 --port 8000 --reload
```

Salida esperada:
```
2026-02-25 10:00:00 | INFO     | mt5_bridge.main — Starting MT5 Bridge API…
2026-02-25 10:00:00 | INFO     | mt5_bridge.main — Database tables verified.
2026-02-25 10:00:01 | INFO     | mt5_bridge.services.mt5_connection — MT5 connected — account=12345678, broker=Exness, server=Exness-MT5Trial3
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### 5 — Debug en VS Code

La configuración de debug ya está en `.vscode/launch.json`.  
Abre el panel **Run and Debug** → selecciona `Debug mt5_bridge.main` → F5.

---

## Referencia de Endpoints

Base URL: `http://localhost:8000`

### `GET /api/v1/account`

Retorna información en vivo de la cuenta MT5.

**Response 200:**
```json
{
  "account_id": 12345678,
  "name": "John Doe",
  "broker": "Exness-MT5",
  "currency": "USD",
  "balance": 10000.00,
  "equity": 10050.00,
  "margin": 500.00,
  "free_margin": 9550.00,
  "margin_level": 2010.00,
  "leverage": 200,
  "is_trade_allowed": true,
  "server": "Exness-MT5Trial3"
}
```

---

### `GET /api/v1/tick/{symbol}`

Retorna candles OHLCV históricos para backtesting.

**Query params:**

| Param | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `from` | datetime ISO 8601 | ✅ | Inicio del rango (UTC) |
| `to` | datetime ISO 8601 | ✅ | Fin del rango (UTC) |
| `period` | string | ❌ | `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w` (default: `1h`) |

**Ejemplo:**
```
GET /api/v1/tick/EURUSDm?from=2026-01-01T00:00:00Z&to=2026-02-25T00:00:00Z&period=1h
```

**Response 200:**
```json
{
  "symbol": "EURUSDm",
  "period": "1h",
  "count": 100,
  "candles": [
    {
      "time": "2026-02-01T00:00:00Z",
      "open": 1.10500,
      "high": 1.10800,
      "low": 1.10300,
      "close": 1.10650,
      "tick_volume": 5678,
      "spread": 2
    }
  ]
}
```

---

### `POST /api/v1/order`

Abre una orden. **Idempotente por `order_id`**: reenviar el mismo UUID retorna el resultado original con `is_duplicate: true` y HTTP 200, sin re-ejecutar en MT5.

**Request body:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "symbol": "EURUSDm",
  "action": "BUY",
  "order_type": "MARKET",
  "volume": 0.10,
  "price": null,
  "sl": 1.09500,
  "tp": 1.11500,
  "comment": "strategy-A",
  "magic": 12345,
  "deviation": 20
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `order_id` | UUID | ✅ | Clave de idempotencia (generar en cliente) |
| `symbol` | string | ✅ | Símbolo con sufijo Exness, e.g. `EURUSDm` |
| `action` | `BUY` \| `SELL` | ✅ | Dirección |
| `order_type` | `MARKET` \| `LIMIT` \| `STOP` | ❌ | Default: `MARKET` |
| `volume` | float | ✅ | Lotes (> 0) |
| `price` | float | Solo LIMIT/STOP | Precio de entrada |
| `sl` | float | ❌ | Stop-loss |
| `tp` | float | ❌ | Take-profit |
| `comment` | string | ❌ | Etiqueta libre (max 64 chars) |
| `magic` | int | ❌ | Magic number del EA |
| `deviation` | int | ❌ | Desviación máxima en puntos (default 20) |

**Response 201** (nueva orden) / **200** (duplicado):
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "broker_ticket": 987654321,
  "position_ticket": 987654321,
  "status": "FILLED",
  "fill_price": 1.10650,
  "sl": 1.09500,
  "tp": 1.11500,
  "timestamp": "2026-02-25T10:00:00Z",
  "is_duplicate": false
}
```

---

### `DELETE /api/v1/order/{orderId}`

Cierra la posición abierta asociada al `order_id` del cliente.

**Response 200:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "broker_ticket": 987654321,
  "status": "CLOSED",
  "close_price": 1.10700,
  "profit": 5.00,
  "timestamp": "2026-02-25T11:00:00Z"
}
```

---

### `PATCH /api/v1/order/{orderId}/modify`

Modifica el SL y/o TP de una posición abierta. Al menos un campo es requerido.

**Request body:**
```json
{ "sl": 1.10000, "tp": 1.12000 }
```

**Response 200:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "broker_ticket": 987654321,
  "status": "MODIFIED",
  "sl": 1.10000,
  "tp": 1.12000,
  "timestamp": "2026-02-25T10:30:00Z"
}
```

---

## Observabilidad

### Métricas Prometheus

Disponibles en `GET /metrics`.

| Métrica | Tipo | Labels | Descripción |
|---------|------|--------|-------------|
| `mt5_gateway_order_latency_ms` | Histogram | `operation` (open/close/modify) | Latencia E2E de operaciones MT5 |
| `mt5_gateway_success_rate_total` | Counter | `operation`, `outcome` (success/failure) | Conteo de operaciones por resultado |
| `duplicate_order_attempts_total` | Counter | `symbol` | Intentos de orden rechazados por duplicado |
| `http_requests_total` | Counter | `handler`, `status`, `method` | Todas las peticiones HTTP (auto) |
| `http_request_duration_seconds` | Histogram | `handler`, `method` | Duración de peticiones HTTP (auto) |

### Documentación interactiva

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Testing

```cmd
cd "c:\Users\sebas\Desktop\Trading Bot\mt5-bridge-api"
.venv\Scripts\activate
pytest tests/ -v
```

Los tests usan SQLite en memoria (sin PostgreSQL ni MT5 reales).

---

## Postman Collection

Importa `mt5_bridge_postman_collection.json` en Postman:

1. Postman → **Import** → selecciona el archivo JSON
2. Setea la variable de entorno `base_url = http://localhost:8000`
3. Ejecuta las requests en orden — el `order_id` se setea automáticamente entre requests

---

## Variables de entorno — Referencia completa

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `MT5_LOGIN` | ✅ | — | Número de cuenta MT5 |
| `MT5_PASSWORD` | ✅ | — | Contraseña MT5 |
| `MT5_SERVER` | ✅ | — | Nombre del servidor, e.g. `Exness-MT5Trial3` |
| `MT5_PATH` | ❌ | auto | Ruta a `terminal64.exe` |
| `MT5_TIMEOUT` | ❌ | `60000` | Timeout de conexión MT5 en ms |
| `DB_URL` | ✅ | — | URL async PostgreSQL |
| `APP_HOST` | ❌ | `0.0.0.0` | Host de escucha |
| `APP_PORT` | ❌ | `8000` | Puerto de escucha |
| `LOG_LEVEL` | ❌ | `INFO` | Nivel de logging (`DEBUG`, `INFO`, `WARNING`) |
| `OTEL_ENDPOINT` | ❌ | — | OTLP gRPC endpoint. Dejar vacío para deshabilitar |

---

## Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `MT5 initialize() failed — code=-6` | Credenciales incorrectas o terminal cerrado | Abre el terminal MT5 e inicia sesión manualmente |
| `MT5 initialize() failed — code=-10003` | Terminal MT5 no está corriendo | Abre MetaTrader 5 antes de iniciar el servicio |
| `Connection refused` en PostgreSQL | minikube no está corriendo o IP incorrecta | `minikube start` y verifica con `minikube ip` |
| `order_send() failed — retcode=10014` | Filling mode no soportado por el broker | Cambia `ORDER_FILLING_IOC` a `ORDER_FILLING_FOK` en `order_service.py` |
| `Symbol 'EURUSD' not found` | Falta el sufijo `m` de Exness | Usa siempre el símbolo con sufijo: `EURUSDm` |
