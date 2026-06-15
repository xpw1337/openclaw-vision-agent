# Week 1 Setup Guide

Reproduce the headless agent infrastructure on a fresh machine. For architecture and file inventory, see [week1-infrastructure-foundation.md](week1-infrastructure-foundation.md).

## Prerequisites

| Tool | Purpose |
|------|---------|
| **Docker Desktop** (WSL 2 backend) | Build images, run k3d |
| **Python 3.10+** | Tests, acceptance script |
| **k3d** | Local Kubernetes ([GitHub releases](https://github.com/k3d-io/k3d/releases)) |
| **kubectl** | `winget install Kubernetes.kubectl` |
| **helm** | `winget install Helm.Helm` |
| **nats CLI** (optional) | Verify observations ([GitHub releases](https://github.com/nats-io/natscli/releases)) |
| **Gemini API key** | [Google AI Studio](https://aistudio.google.com/apikey) |

Enable virtualization in BIOS before installing Docker/WSL 2.

Verify:

```powershell
docker version
k3d version
kubectl version --client
helm version
python --version
```

## 1. Clone and install Python deps

```powershell
git clone https://github.com/xpw1337/openclaw-vision-agent.git
cd openclaw-vision-agent
pip install -r requirements.txt
python -m pytest   # expect 49 passed
```

## 2. Create `.env`

```powershell
copy .env.example .env
# Edit .env and set GEMINI_API_KEY=your-key-here
```

Never commit `.env` — it is gitignored.

## 3. Create cluster and install NATS

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-cluster.ps1
```

### kubeconfig fix (Windows)

If `kubectl cluster-info` fails with `host.docker.internal`, repoint the API server:

```powershell
kubectl config view --minify
# Note the port in the server URL, then:
kubectl config set-cluster k3d-surveillance --server="https://127.0.0.1:<port>"
kubectl cluster-info
```

## 4. Build, push, and deploy

Creates the `gemini-api` Secret from `.env`, builds the image, pushes to the local registry, and rolls out 3 agent replicas:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-and-deploy.ps1
```

Verify pods:

```powershell
kubectl -n surveillance get pods
```

Expect `nats-0`, `nats-box`, and three `vision-agent-*` pods — all Running and Ready.

## 5. Acceptance test

**Terminal 1** — port-forward NATS to localhost:

```powershell
kubectl -n surveillance port-forward svc/nats 4222:4222
```

**Terminal 2** — publish a test image (any jpg/png):

```powershell
python -m agent.publish_test_job path\to\image.jpg --camera-id cam-1
```

You should receive structured JSON with `"error": null` and a populated `"analysis"` object.

Optional — verify with the nats CLI:

```powershell
nats sub observations --count=1 --server nats://localhost:4222
# In another terminal, run publish_test_job again
```

Confirm the API key is not hardcoded anywhere:

```powershell
Select-String -Path k8s\*.yaml, Dockerfile, agent\*.py -Pattern 'AIza|GEMINI_API_KEY'
# Should only match comments / secret template, not actual key material
```

## 6. Shut down

When you are done (safe before shutting down your PC):

```powershell
k3d cluster delete surveillance
k3d registry delete k3d-registry.localhost
```

Optionally quit **Docker Desktop** from the system tray if you want nothing Docker-related running in the background.

## 7. Resume after reboot

```powershell
# Start Docker Desktop first, then:
powershell -ExecutionPolicy Bypass -File scripts\setup-cluster.ps1
kubectl config set-cluster k3d-surveillance --server="https://127.0.0.1:<port>"   # if needed
powershell -ExecutionPolicy Bypass -File scripts\build-and-deploy.ps1
```

## Linux / macOS

The scripts are PowerShell. Equivalent manual steps:

```bash
# Registry + cluster
k3d registry create registry.localhost --port 5000
k3d cluster create surveillance --registry-use k3d-registry.localhost:5000 --agents 1

kubectl create namespace surveillance
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm upgrade --install nats nats/nats --namespace surveillance --wait

# Secret from .env
export GEMINI_API_KEY=$(grep '^GEMINI_API_KEY=' .env | cut -d= -f2- | tr -d '"')
kubectl -n surveillance create secret generic gemini-api \
  --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" --dry-run=client -o yaml | kubectl apply -f -

# Build and push (use localhost:5000 on the host)
docker build -t localhost:5000/vision-agent:dev .
docker push localhost:5000/vision-agent:dev
kubectl apply -f k8s/
kubectl -n surveillance rollout restart deployment/vision-agent
```
