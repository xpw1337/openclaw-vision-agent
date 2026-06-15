# Build the worker image, push to the k3d registry, and (re)deploy.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Push via localhost:5000 (the host port mapping) — `k3d-registry.localhost`
# only resolves inside the cluster network, not on the Windows host.
docker build -t localhost:5000/vision-agent:dev .
docker push localhost:5000/vision-agent:dev

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/agent-deployment.yaml
kubectl -n surveillance rollout restart deployment/vision-agent
kubectl -n surveillance rollout status deployment/vision-agent --timeout=180s
