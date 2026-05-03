# Tick Producer — Java WebFlux + Kafka

Job programado en **Spring Boot 3.3 / WebFlux** (Java 21) que cada hora consulta
candles OHLCV del **Python Gateway** (mt5-bridge-api) y publica mensajes
`TickMessageV1` en el topic `topic_ticks` de **Apache Kafka**.

El servicio es **stateless**: no persiste datos localmente; solo actúa como
productor de eventos. Usa `WebClient` reactivo para las llamadas HTTP y
`KafkaTemplate` para la publicación con serialización JSON.

---

## Flujo de datos

```
  ┌─────────────────────────────────────────────────────────────┐
  │  Minikube Node (Docker container en Windows)                │
  │                                                             │
  │  ┌──────────────────────┐    ┌──────────────────────────┐  │
  │  │  Pod: tick-producer  │    │  Pod: kafka              │  │
  │  │                      │    │                          │  │
  │  │  Scheduler (cron)    │    │  :9092 broker            │  │
  │  │  cada hora en punto  │    │  :8080 UI                │  │
  │  │         │            │    └──────────────────────────┘  │
  │  │         ▼            │               ▲                  │
  │  │  CandleGateway       │               │ topic_ticks      │
  │  │  Client              │───────────────┘                  │
  │  │  http://mt5-gateway  │                                  │
  │  │  :8000               │                                  │
  │  └────────┬─────────────┘                                  │
  │           │                                                │
  │  ┌────────▼─────────────────────────┐                     │
  │  │  Service: mt5-gateway             │                     │
  │  │  type: ExternalName               │                     │
  │  │  → host.minikube.internal         │                     │
  │  └────────┬─────────────────────────┘                     │
  │           │  CNAME DNS resolution                         │
  └───────────┼───────────────────────────────────────────────┘
              │  host.minikube.internal = IP del host Windows
  ┌───────────▼───────────────────────────────────────────────┐
  │  Host Windows                                             │
  │  Python Gateway (mt5-bridge-api) → localhost:8000         │
  └───────────────────────────────────────────────────────────┘
```

Para cada símbolo (e.g. `EURUSDm`, `GBPUSDm`, …) el scheduler:

1. Calcula `from` = hora anterior truncada, `to` = hora actual truncada
2. Llama `GET {gateway}/api/v1/tick/{symbol}?from=...&to=...&period=1h`
3. Toma la última candle de la respuesta
4. Construye un `TickMessageV1` y lo publica en `topic_ticks` con `key = symbol`

---

## Estructura del proyecto

```
tick-producer/
├── build.gradle.kts           Dependencias y plugins Gradle
├── settings.gradle.kts        Nombre del proyecto
├── Dockerfile                 Multi-stage: build + runtime
├── .gitignore
├── README.md                  ← este archivo
├── k8s/
│   ├── configmap.yaml         Variables de entorno para K8s
│   ├── deployment.yaml        Deployment stateless
│   └── service.yaml           ClusterIP para actuator
└── src/
    ├── main/
    │   ├── java/com/trading/tickproducer/
    │   │   ├── TickProducerApplication.java    Entry point
    │   │   ├── config/
    │   │   │   ├── KafkaProducerConfig.java    ProducerFactory + KafkaTemplate
    │   │   │   ├── WebClientConfig.java        WebClient → Gateway
    │   │   │   └── TickProperties.java         @ConfigurationProperties
    │   │   ├── model/
    │   │   │   ├── Candle.java                 Record: vela OHLCV
    │   │   │   ├── CandleResponse.java         Record: respuesta del Gateway
    │   │   │   └── TickMessageV1.java          Record: mensaje Kafka
    │   │   ├── service/
    │   │   │   ├── CandleGatewayClient.java    WebClient reactivo → Gateway
    │   │   │   └── TickPublisherService.java   KafkaTemplate → topic_ticks
    │   │   └── scheduler/
    │   │       └── TickScheduler.java          @Scheduled + Flux processing
    │   └── resources/
    │       └── application.yml                 Configuración Spring Boot
    └── test/
        └── java/com/trading/tickproducer/
            └── TickSchedulerTest.java          Tests unitarios (Mockito)
```

---

## TickMessageV1 — Schema del mensaje Kafka

```json
{
  "symbol": "EURUSDm",
  "open": 1.08500,
  "high": 1.08700,
  "low": 1.08400,
  "close": 1.08650,
  "tickVolume": 5678,
  "spread": 2,
  "time": "2026-02-26T13:00:00Z",
  "period": "1h",
  "publishedAt": "2026-02-26T14:00:01.234Z"
}
```

| Campo         | Tipo          | Descripción                              |
| ------------- | ------------- | ---------------------------------------- |
| `symbol`      | `String`      | Símbolo del instrumento forex            |
| `open`        | `BigDecimal`  | Precio de apertura                       |
| `high`        | `BigDecimal`  | Precio máximo                            |
| `low`         | `BigDecimal`  | Precio mínimo                            |
| `close`       | `BigDecimal`  | Precio de cierre                         |
| `tickVolume`  | `long`        | Volumen de ticks en la barra             |
| `spread`      | `int`         | Spread al abrir la barra                 |
| `time`        | `Instant`     | Hora de apertura de la candle (UTC)      |
| `period`      | `String`      | Período de la candle (`1h`)              |
| `publishedAt` | `Instant`     | Momento de publicación a Kafka           |

---

## Prerrequisitos

| Herramienta      | Versión mínima | Instalación                                  |
| ---------------- | -------------- | -------------------------------------------- |
| JDK              | 21             | https://adoptium.net/                        |
| Gradle           | 8.10           | Se usa el wrapper (`gradlew`)                |
| Docker Desktop   | 4.x            | https://docs.docker.com/desktop/install/     |
| Minikube         | 1.33           | `winget install minikube`                    |
| kubectl          | 1.30           | Incluido con Docker Desktop                  |

> **Dependencia en runtime:** Kafka y el Python Gateway deben estar accesibles.

---

## Levantar en local

### 1 — Verificar que Kafka y el Gateway estén corriendo

```cmd
REM Kafka (ver kafka-k8s/README.md)
kubectl port-forward svc/kafka -n trading 9092:9092

REM Gateway (ver mt5-bridge-api/README.md)
REM Debe estar escuchando en http://localhost:8000
```

### 2 — Compilar y ejecutar

```cmd
cd tick-producer
gradlew bootRun
```

Salida esperada:

```
  .   ____          _            __ _ _
 /\\ / ___'_ __ _ _(_)_ __  __ _ \ \ \ \
( ( )\___ | '_ | '_| | '_ \/ _` | \ \ \ \
 \\/  ___)| |_)| | | | | || (_| |  ) ) ) )
  '  |____| .__|_| |_|_| |_\__, | / / / /
 =========|_|==============|___/=/_/_/_/
 :: Spring Boot ::        (v3.3.5)

... TickProducerApplication : Started TickProducerApplication in 2.3 seconds
... TickScheduler           : ══ Tick cycle started — 6 symbols to process ══
... TickPublisherService    : Published EURUSDm → topic=topic_ticks partition=0 offset=0
```

### 3 — Ejecutar tests

```cmd
gradlew test
```

### 4 — Verificar actuator

```cmd
curl http://localhost:8081/actuator/health
```

```json
{
  "status": "UP"
}
```

---

## Levantar en Kubernetes (Minikube)

### 1 — Asegurar que Minikube esté corriendo

```cmd
minikube status
```

### 2 — Construir la imagen Docker dentro de Minikube

```cmd
cd tick-producer
minikube image build -t tick-producer:latest .
```

> Esto construye la imagen directamente en el registry de Minikube,
> sin necesidad de Docker Hub. El Deployment usa `imagePullPolicy: Never`.

### 3 — Desplegar

```cmd
kubectl apply -f k8s/external-services.yaml -f k8s/configmap.yaml -f k8s/deployment.yaml -f k8s/service.yaml
```

Salida esperada:

```
service/mt5-gateway created
configmap/tick-producer-config created
deployment.apps/tick-producer created
service/tick-producer created
```

> **Importante:** el Python Gateway debe estar corriendo en el host Windows
> (`http://localhost:8000`) antes de desplegar el tick-producer.

### 4 — Verificar el Pod

```cmd
kubectl get pods -n trading -l app=tick-producer
```

```
NAME                             READY   STATUS    RESTARTS   AGE
tick-producer-7f8b9c6d4f-x2k9m  1/1     Running   0          30s
```

### 5 — Ver logs del scheduler

```cmd
kubectl logs -f -l app=tick-producer -n trading
```

---

## Conectividad de red host ↔ Minikube

Cuando Minikube corre con `--driver=docker` en Windows, los pods **no pueden
usar `localhost`** para acceder a servicios del host — `localhost` resuelve
al propio Pod.

Solución: Minikube expone la IP del host bajo el hostname especial
`host.minikube.internal`. Se crea un **Service `ExternalName`** en el cluster
que actúa como puente DNS:

```
Pod → http://mt5-gateway:8000
         ↓ DNS (CNAME)
      host.minikube.internal
         ↓ resuelve a
      192.168.x.x (IP del host Windows)
         ↓ TCP :8000
      Python Gateway (localhost:8000 del host)
```

| Recurso | Tipo | Propósito |
|---------|------|-----------|
| `mt5-gateway` Service | `ExternalName` | Puente DNS: cluster → host |
| `GATEWAY_BASE_URL` | ConfigMap var | `http://mt5-gateway:8000` |

Esta arquitectura es limpia porque si el Gateway se migra a un pod de Kubernetes,
basta cambiar el Service de `ExternalName` a `ClusterIP` con selector —
el ConfigMap y el código permanecen sin cambios.

---

## Variables de configuración

| Variable                        | Default                                              | Descripción                              |
| ------------------------------- | ---------------------------------------------------- | ---------------------------------------- |
| `GATEWAY_BASE_URL`             | `http://localhost:8000` (local) / `http://mt5-gateway:8000` (K8s) | URL base del Python Gateway |
| `SPRING_KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092`                                    | Bootstrap servers de Kafka               |
| `TICK_TOPIC`                   | `topic_ticks`                                         | Topic de Kafka destino                   |
| `TICK_CRON`                    | `0 0 * * * *`                                         | Expresión cron (cada hora en punto)      |
| `TICK_SYMBOLS`                 | `EURUSDm,GBPUSDm,USDJPYm,AUDUSDm,USDCHFm,USDCADm`  | Símbolos a consultar (separados por `,`) |

Todas las variables se pueden sobreescribir vía variables de entorno o en el
ConfigMap de Kubernetes.

---

## Errores comunes

| Síntoma                                    | Causa probable                               | Solución                                                    |
| ------------------------------------------ | -------------------------------------------- | ----------------------------------------------------------- |
| `Connection refused` al Gateway            | Gateway no está corriendo                    | Iniciar mt5-bridge-api o verificar port-forward             |
| `UnknownHostException: mt5-gateway`        | ExternalName Service no aplicado             | `kubectl apply -f k8s/external-services.yaml`               |
| `Connection refused` a `host.minikube.internal` | Gateway no escucha en 0.0.0.0           | Asegurarse que el Gateway escucha en `0.0.0.0:8000` no solo `127.0.0.1` |
| `Connection refused` a Kafka               | Kafka no está corriendo                      | Verificar pod kafka-0 y port-forward 9092                   |
| `Topic not found` / `UNKNOWN_TOPIC`        | Topic no creado                              | Crear `topic_ticks` manualmente (ver kafka-k8s/README.md)   |
| `Timeout` en publicación                   | Kafka sobrecargado o sin recursos            | Aumentar resources en minikube                              |
| Pod en `CrashLoopBackOff`                  | Fallo en health check (Kafka no disponible)  | Verificar que Kafka esté `Running` antes de desplegar       |
| `ImagePullBackOff`                         | Imagen no construida en minikube             | Ejecutar `minikube image build -t tick-producer:latest .`   |

---

## Teardown

Eliminar solo el Tick Producer:

```cmd
kubectl delete deployment tick-producer -n trading
kubectl delete service tick-producer -n trading
kubectl delete configmap tick-producer-config -n trading
```

Verificar:

```cmd
kubectl get all -n trading -l app=tick-producer
```

```
No resources found in trading namespace.
```
