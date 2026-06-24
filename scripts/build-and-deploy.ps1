# Build the worker, sampler, and fusion images, push to the k3d registry, and
# (re)deploy the full Week 2 stack (NATS workers + Postgres + Redis + fusion + samplers).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# --- Secrets -----------------------------------------------------------------

# Gemini key from .env (never commit the real key).
$envFile = Join-Path (Get-Location) ".env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found. Copy .env.example to .env and set GEMINI_API_KEY."
}
$line = Get-Content $envFile | Where-Object { $_ -match '^GEMINI_API_KEY=' } | Select-Object -First 1
if (-not $line) {
    Write-Error "GEMINI_API_KEY not found in .env"
}
$key = ($line -replace '^GEMINI_API_KEY=', '').Trim().Trim('"')
kubectl -n surveillance create secret generic gemini-api `
    --from-literal=GEMINI_API_KEY=$key `
    --dry-run=client -o yaml | kubectl apply -f -

# Postgres password from .env (POSTGRES_PASSWORD) or a stable dev default.
# Keep it stable across runs — the PVC retains data initialized with it.
$pgLine = Get-Content $envFile | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1
if ($pgLine) {
    $pgPass = ($pgLine -replace '^POSTGRES_PASSWORD=', '').Trim().Trim('"')
} else {
    $pgPass = "postgres"
}
kubectl -n surveillance create secret generic postgres-credentials `
    --from-literal=POSTGRES_PASSWORD=$pgPass `
    --dry-run=client -o yaml | kubectl apply -f -

# --- Sample clips ------------------------------------------------------------

# Samplers bake clips into their image; make sure they exist before building.
if (-not (Test-Path "data/clips/cam-dock-1.avi")) {
    Write-Host "Sample clips missing; fetching..."
    & (Join-Path $PSScriptRoot "fetch-sample-clips.ps1")
}

# --- Build + push images -----------------------------------------------------

# Push via localhost:5000 (host port mapping); k3d-registry.localhost only
# resolves inside the cluster network, not on the Windows host.
docker build -t localhost:5000/vision-agent:dev .
docker push localhost:5000/vision-agent:dev

docker build -f Dockerfile.sampler -t localhost:5000/vision-sampler:dev .
docker push localhost:5000/vision-sampler:dev

docker build -f Dockerfile.fusion -t localhost:5000/vision-fusion:dev .
docker push localhost:5000/vision-fusion:dev

# --- Apply manifests ---------------------------------------------------------

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/agent-deployment.yaml
kubectl apply -f k8s/fusion-deployment.yaml
kubectl apply -f k8s/sampler-deployment.yaml

# --- Roll + wait -------------------------------------------------------------

kubectl -n surveillance rollout restart `
    deployment/vision-agent deployment/fusion `
    deployment/sampler-cam-dock-1 deployment/sampler-cam-dock-2 `
    deployment/sampler-cam-lobby-1 deployment/sampler-cam-lot-1

kubectl -n surveillance rollout status deployment/postgres --timeout=180s
kubectl -n surveillance rollout status deployment/redis --timeout=120s
kubectl -n surveillance rollout status deployment/vision-agent --timeout=180s
kubectl -n surveillance rollout status deployment/fusion --timeout=180s

Write-Host ""
Write-Host "Deployed. Query the fused area summary with:"
Write-Host "  kubectl -n surveillance port-forward svc/fusion 8000:8000"
Write-Host "  curl http://localhost:8000/area"
