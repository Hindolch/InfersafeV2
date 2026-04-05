$ComposeFile = "configs/docker-compose.yml"
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

Write-Host "Starting baseline gateway + load balancer + vllm-0"
docker compose -f $ComposeFile up -d gateway load-balancer vllm-0

Write-Host "Waiting 15 seconds before scale-out"
Start-Sleep -Seconds 15
$BeforeScale = $Stopwatch.Elapsed.TotalSeconds

Write-Host "Scaling out by adding vllm-1 and vllm-2"
docker compose -f $ComposeFile up -d vllm-1 vllm-2

Write-Host "Waiting 20 seconds for health checks"
Start-Sleep -Seconds 20
$AfterScale = $Stopwatch.Elapsed.TotalSeconds

Write-Host ("Cold-start / scale-out window (seconds): {0:N2}" -f ($AfterScale - $BeforeScale))
Write-Host "Scale-in is manual in this demo:"
Write-Host "docker compose -f configs/docker-compose.yml stop vllm-2"
