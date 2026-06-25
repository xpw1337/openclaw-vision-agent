param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(0, 1)]
    [int]$Replicas
)

$ErrorActionPreference = "Stop"

if ($Replicas -gt 0) {
    Write-Warning "Scaling samplers above 0 resumes Gemini API calls and API cost."
    Write-Warning "Use -Replicas 0 to pause the feed publishers again after the demo."
}

kubectl -n surveillance scale deploy -l app=sampler --replicas=$Replicas

Write-Host ""
kubectl -n surveillance get deploy -l app=sampler -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas
