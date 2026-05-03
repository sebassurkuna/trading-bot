# Apache Kafka en Kubernetes — Trading Platform

Despliegue local de **Apache Kafka 7.7.1 (Confluent)** en modo **KRaft** (sin Zookeeper)
junto con **Kafka UI** para gestión visual, dentro del namespace `trading` en Minikube.

Ambos procesos corren como contenedores _sidecar_ en el mismo Pod (StatefulSet),
compartiendo red vía `localhost`. Los datos del broker se persisten en un PVC de 2 Gi.

---

## Arquitectura del Pod

```
┌─────────────────────────────────────────────────────────┐
│  StatefulSet: kafka   (namespace: trading)              │
│                                                         │
│  ┌─────────────────────┐   ┌─────────────────────────┐  │
│  │  kafka (cp-kafka)   │   │  kafka-ui               │  │
│  │  :9092  broker      │◄──│  :8080  web UI          │  │
│  │  :9093  controller  │   │  (provectuslabs/        │  │
│  │  KRaft mode         │   │   kafka-ui:latest)      │  │
│  └────────┬────────────┘   └─────────────────────────┘  │
│           │                                             │
│  ┌────────▼────────────┐                                │
│  │  PVC: kafka-data    │                                │
│  │  2Gi RWO            │                                │
│  └─────────────────────┘                                │
└─────────────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │  Service: kafka       │
        │  NodePort 30092 → 9092│
        │  NodePort 30080 → 8080│
        └───────────────────────┘
```

---

## Por qué port-forward es la única opción en Windows + Docker Desktop

Minikube con `--driver=docker` en Windows ejecuta el nodo dentro de un contenedor
Docker. La red del nodo no es accesible directamente desde el host, por lo que
`NodePort` no funciona sin un túnel intermedio. La solución más sencilla y fiable es
`kubectl port-forward`.

---

## Prerrequisitos

| Herramienta      | Versión mínima | Instalación                              |
| ---------------- | -------------- | ---------------------------------------- |
| Docker Desktop   | 4.x            | https://docs.docker.com/desktop/install/ |
| Minikube         | 1.33           | `winget install minikube`                |
| kubectl          | 1.30           | Incluido con Docker Desktop              |

---

## Paso a paso

### 1 — Asegurarse de que Docker Desktop esté corriendo

Verificar que el ícono de Docker aparezca en la bandeja del sistema.

### 2 — Iniciar Minikube (si no está corriendo)

```cmd
minikube status
```

Si no está activo:

```cmd
minikube start --driver=docker --cpus=4 --memory=4096
```

> **Nota:** Kafka requiere más recursos que PostgreSQL. Se recomiendan al menos 4 GB
> de RAM y 4 CPUs para el nodo.

### 3 — Desplegar Kafka

```cmd
cd kafka-k8s
kubectl apply -f namespace.yaml -f configmap.yaml -f secret.yaml -f statefulset.yaml -f service.yaml
```

Salida esperada:

```
namespace/trading unchanged
configmap/kafka-config created
secret/kafka-secret created
statefulset.apps/kafka created
service/kafka created
```

### 4 — Verificar que el Pod esté listo

```cmd
kubectl get pods -n trading -l app=kafka -w
```

Esperar a que ambos contenedores muestren `2/2 Running`:

```
NAME      READY   STATUS    RESTARTS   AGE
kafka-0   2/2     Running   0          90s
```

> El broker tarda ~60s en arrancar en modo KRaft. Si se reinicia varias veces,
> revisar los logs con `kubectl logs kafka-0 -n trading -c kafka`.

### 5 — Abrir el túnel a Kafka UI

```cmd
kubectl port-forward svc/kafka -n trading 8080:8080
```

Abrir en el navegador: **http://localhost:8080**

Se verá el cluster `trading-local` con el broker conectado.

### 6 — Abrir el túnel al broker (para productores/consumidores locales)

En otra terminal:

```cmd
kubectl port-forward svc/kafka -n trading 9092:9092
```

Ahora los clientes locales pueden conectarse a `localhost:9092`.

### 7 — Crear el topic `topic_ticks` manualmente

Desde la **Kafka UI** (http://localhost:8080):

1. Ir a **Topics** → **Add a Topic**
2. Configurar:
   - **Topic Name:** `topic_ticks`
   - **Number of Partitions:** `3`
   - **Replication Factor:** `1`
   - **Retention:** `168 hours` (7 días)
3. Click **Create**

Alternativamente, vía CLI:

```cmd
kubectl exec -it kafka-0 -n trading -c kafka -- kafka-topics --create --topic topic_ticks --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092
```

---

## Manifests incluidos

| Archivo            | Recurso                      | Descripción                                      |
| ------------------ | ---------------------------- | ------------------------------------------------ |
| `namespace.yaml`   | `Namespace`                  | Namespace `trading` (compartido con PostgreSQL)   |
| `configmap.yaml`   | `ConfigMap kafka-config`     | Variables de entorno para KRaft, broker y UI      |
| `secret.yaml`      | `Secret kafka-secret`        | Placeholder SASL (vacío, PLAINTEXT por ahora)     |
| `statefulset.yaml` | `StatefulSet kafka`          | Pod con 2 contenedores: broker + UI               |
| `service.yaml`     | `Service kafka (NodePort)`   | Expone broker (:30092) y UI (:30080)              |

---

## Variables de configuración

### Kafka Broker

| Variable                               | Valor                      | Descripción                           |
| -------------------------------------- | -------------------------- | ------------------------------------- |
| `KAFKA_NODE_ID`                        | `1`                        | ID del nodo KRaft                     |
| `KAFKA_PROCESS_ROLES`                  | `broker,controller`        | Roles combinados (single-node)        |
| `KAFKA_LISTENERS`                      | `PLAINTEXT://:9092,...`    | Listeners del broker y controller     |
| `KAFKA_AUTO_CREATE_TOPICS_ENABLE`      | `false`                    | Topics se crean manualmente           |
| `KAFKA_NUM_PARTITIONS`                 | `3`                        | Particiones por defecto               |
| `KAFKA_LOG_RETENTION_HOURS`            | `168`                      | Retención de 7 días                   |

### Kafka UI

| Variable                               | Valor                      | Descripción                           |
| -------------------------------------- | -------------------------- | ------------------------------------- |
| `KAFKA_CLUSTERS_0_NAME`               | `trading-local`            | Nombre visible en la UI               |
| `KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS`   | `localhost:9092`           | Conexión intra-pod al broker          |
| `DYNAMIC_CONFIG_ENABLED`              | `true`                     | Permite editar configuración desde UI |

---

## Errores comunes

| Síntoma                                    | Causa probable                              | Solución                                                  |
| ------------------------------------------ | ------------------------------------------- | --------------------------------------------------------- |
| Pod en `CrashLoopBackOff`                  | Recursos insuficientes en Minikube          | `minikube stop && minikube start --cpus=4 --memory=4096`  |
| `kafka-ui` no carga                        | Broker aún arrancando                       | Esperar ~90s, verificar con `kubectl logs kafka-0 -c kafka` |
| `Connection refused` en `localhost:9092`   | Falta port-forward                          | `kubectl port-forward svc/kafka -n trading 9092:9092`     |
| Topic no aparece en UI                     | Auto-create deshabilitado                   | Crear el topic manualmente (paso 7)                       |
| `CLUSTER_ID` mismatch tras recrear         | PVC con datos del cluster anterior          | Eliminar PVC: `kubectl delete pvc kafka-data-kafka-0 -n trading` |

---

## Teardown

Eliminar solo Kafka (preservar el namespace `trading` y PostgreSQL):

```cmd
kubectl delete statefulset kafka -n trading
kubectl delete service kafka -n trading
kubectl delete configmap kafka-config -n trading
kubectl delete secret kafka-secret -n trading
kubectl delete pvc kafka-data-kafka-0 -n trading
```

Eliminar todo el namespace (incluye PostgreSQL y demás):

```cmd
kubectl delete namespace trading
```

Detener Minikube:

```cmd
minikube stop
```
