# One-time local cluster setup: k3d registry + cluster + NATS via Helm.
$ErrorActionPreference = "Stop"

# Local registry so `docker push` -> cluster pulls work without a remote.
if (-not (k3d registry list -o json | ConvertFrom-Json | Where-Object { $_.name -eq "k3d-registry.localhost" })) {
    k3d registry create registry.localhost --port 5000
}

if (-not (k3d cluster list -o json | ConvertFrom-Json | Where-Object { $_.name -eq "surveillance" })) {
    k3d cluster create surveillance --registry-use k3d-registry.localhost:5000 --agents 1
}

kubectl create namespace surveillance --dry-run=client -o yaml | kubectl apply -f -

helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm repo update nats
helm upgrade --install nats nats/nats --namespace surveillance --values k8s/nats-values.yaml --wait

Write-Host "Cluster ready. NATS + JetStream reachable in-cluster at nats://nats.surveillance.svc:4222"
