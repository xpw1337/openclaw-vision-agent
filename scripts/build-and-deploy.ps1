# Build the worker image, push to the k3d registry, and (re)deploy.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Create/update Secret from .env (never commit the real key).
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

# Push via localhost:5000 (the host port mapping) — `k3d-registry.localhost`
# only resolves inside the cluster network, not on the Windows host.
docker build -t localhost:5000/vision-agent:dev .
docker push localhost:5000/vision-agent:dev

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/agent-deployment.yaml
kubectl -n surveillance rollout restart deployment/vision-agent
kubectl -n surveillance rollout status deployment/vision-agent --timeout=180s
