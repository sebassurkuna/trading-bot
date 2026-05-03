# PostgreSQL en Kubernetes — MT5 Bridge API

PostgreSQL 16 desplegado como **StatefulSet** en un clúster Kubernetes local (minikube + Docker Desktop).  
El esquema se inicializa automáticamente en el primer arranque mediante `/docker-entrypoint-initdb.d/`.  
Acceso desde Windows vía **`kubectl port-forward`** → `localhost:5432`.

---

## Por qué port-forward es la única opción en Windows + Docker Desktop

Con el driver Docker de minikube en Windows, los NodePorts **no son accesibles directamente**  
(ni por la IP de minikube ni por `127.0.0.1`) sin un proceso de forwarding. Es una limitación del networking de Docker en Windows.

`kubectl port-forward` crea un túnel TCP **estrictamente local** entre tu máquina y el pod:

```
Windows (localhost:5432)  ←──────────────────────→  pod/postgres-0:5432
         solo accesible desde tu propia máquina, nunca desde internet
```

**¿Es estable para connection pools (SQLAlchemy)?** Sí, para este caso de uso:
- El servicio es local y de baja concurrencia (pool_size=10)
- `pool_pre_ping=True` reestablece automáticamente cualquier conexión caída antes de usarla
- `pool_recycle=1800` previene conexiones idle obsoletas

---

## Prerrequisitos

| Herramienta | Versión mínima | Instalación |
|-------------|----------------|-------------|
| [minikube](https://minikube.sigs.k8s.io/docs/start/) | v1.32 | `winget install minikube` |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | v4.x | descargar desde docker.com |
| [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/) | v1.29 | incluido con minikube |

---

## Paso a paso

### 1 — Asegurarse de que Docker Desktop esté corriendo

Abre Docker Desktop y espera a que el icono en la barra de tareas esté verde (Engine running).

---

### 2 — Iniciar minikube con driver Docker

```cmd
minikube start --driver=docker --cpus=2 --memory=2048
```

Verifica que el clúster esté listo:
```cmd
kubectl get nodes
```

---

### 3 — Desplegar PostgreSQL

Aplica los manifests desde la carpeta `postgres-k8s/`:

```cmd
cd "c:\Users\sebas\Desktop\Trading Bot\postgres-k8s"

kubectl apply -f namespace.yaml -f configmap.yaml -f configmap-init.yaml -f secret.yaml -f statefulset.yaml -f service.yaml
```

Espera a que el pod esté `Running`:
```cmd
kubectl get pods -n trading -w
```

Salida esperada:
```
NAME         READY   STATUS    RESTARTS   AGE
postgres-0   1/1     Running   0          45s
```

---

### 4 — Abrir el túnel localhost → PostgreSQL

Ejecuta el port-forward **en una terminal dedicada** (debe permanecer abierta mientras el servicio esté corriendo):

```cmd
kubectl port-forward svc/postgres -n trading 5432:5432
```

Salida esperada:
```
Forwarding from 127.0.0.1:5432 -> 5432
Forwarding from [::1]:5432 -> 5432
```

PostgreSQL queda accesible en:
```
Host:     localhost
Port:     5432
User:     trading_user
Password: trading_pass_local
Database: trading_db
```

Cadena de conexión para el `.env` del servicio:
```
DB_URL=postgresql+asyncpg://trading_user:trading_pass_local@localhost:5432/trading_db
```

#### Abrir port-forward en segundo plano (opcional)

```powershell
# PowerShell — abre en ventana minimizada
Start-Process kubectl -ArgumentList 'port-forward svc/postgres -n trading 5432:5432' -WindowStyle Minimized
```

```cmd
:: CMD
start /min kubectl port-forward svc/postgres -n trading 5432:5432
```

Para cerrarlo:
```cmd
taskkill /F /FI "WINDOWTITLE eq kubectl*"
```

---

### 5 — Verificar la conexión

Con pgAdmin o `psql` (con el port-forward activo):
```
Host:    localhost
Port:    5432
User:    trading_user
Pass:    trading_pass_local
DB:      trading_db
```

```cmd
psql -h localhost -p 5432 -U trading_user -d trading_db
```

O directamente dentro del pod (no requiere port-forward):
```cmd
kubectl exec -it postgres-0 -n trading -- psql -U trading_user -d trading_db
```

Verifica que el schema fue creado:
```sql
\dt
```

Salida esperada:
```
          List of relations
 Schema |     Name     | Type  |    Owner
--------+--------------+-------+--------------
 public | exec_reports | table | trading_user
 public | order_map    | table | trading_user
```

---

### 6 — Aplicar migraciones manualmente (opcional)

El schema se crea automáticamente en el primer arranque.  
Para reaplicarlo en un pod existente:

```cmd
kubectl exec -i postgres-0 -n trading -- psql -U trading_user -d trading_db < migrations\001_init_schema.sql
```

---

## Cambiar la contraseña

Edita `secret.yaml`:
```yaml
stringData:
  POSTGRES_PASSWORD: "nueva_contraseña_segura"
```

Vuelve a aplicar:
```cmd
kubectl apply -f secret.yaml
kubectl rollout restart statefulset/postgres -n trading
```

Actualiza también `DB_URL` en el archivo `.env` del servicio.

---

## Teardown

```cmd
kubectl delete namespace trading
minikube stop
```

> ⚠️ Borrar el namespace elimina también el PersistentVolumeClaim y los datos.  
> Haz un backup antes si necesitas conservar los datos:
> ```cmd
> kubectl exec -it postgres-0 -n trading -- pg_dump -U trading_user trading_db > backup.sql
> ```

---

## Recursos Kubernetes creados

| Recurso | Nombre | Namespace |
|---------|--------|-----------|
| Namespace | `trading` | — |
| ConfigMap | `postgres-config` | trading |
| ConfigMap | `postgres-init-scripts` | trading |
| Secret | `postgres-secret` | trading |
| StatefulSet | `postgres` | trading |
| Service (NodePort) | `postgres` | trading |
| PVC (auto) | `postgres-data-postgres-0` | trading |
