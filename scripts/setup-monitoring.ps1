$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update prometheus-community

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
    --namespace monitoring `
    --create-namespace `
    --wait

Write-Host ""
Write-Host "Monitoring installed."
Write-Host "Grafana:"
Write-Host "  kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80"
Write-Host "Prometheus:"
Write-Host "  kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090"
Write-Host ""
Write-Host "Import docs/monitoring/week3-grafana-dashboard.json into Grafana for the Week 3 panels."
