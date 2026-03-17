param(
  [string]$Workspace = ".",
  [string]$PythonExe = "python",
  [string]$TaskPath = "examples/task.codegen.sample.yaml",
  [string]$ServeHost = "127.0.0.1",
  [int]$ServePort = 8787,
  [string]$StubHost = "127.0.0.1",
  [int]$StubPort = 9000,
  [string]$Token = "dev-agentkit-token",
  [string]$ApiKey = "local-dev-key",
  [string]$LogLevel = "DEBUG",
  [switch]$KeepAlive
)

$ErrorActionPreference = "Stop"
$workspacePath = (Resolve-Path $Workspace).Path
Set-Location $workspacePath

$env:PYTHONPATH = "src"
$env:AGENTKIT_LLM_API_KEY = $ApiKey

$logsDir = Join-Path $workspacePath ".agentkit/logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$stubOut = Join-Path $logsDir "llm_stub.out.log"
$stubErr = Join-Path $logsDir "llm_stub.err.log"
$serveOut = Join-Path $logsDir "agentkit_serve.out.log"
$serveErr = Join-Path $logsDir "agentkit_serve.err.log"

$stubArgs = @("scripts/llm_codegen_stub.py", "--host", $StubHost, "--port", "$StubPort")
$stubProc = Start-Process -FilePath $PythonExe -ArgumentList $stubArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $stubOut -RedirectStandardError $stubErr
Set-Content -Encoding ascii -Path (Join-Path $workspacePath ".agentkit/llm_stub.pid") -Value $stubProc.Id

Start-Sleep -Seconds 1
if ($stubProc.HasExited) {
  Write-Host "llm stub failed to start"
  if (Test-Path $stubErr) { Get-Content $stubErr }
  if (Test-Path $stubOut) { Get-Content $stubOut }
  throw "llm stub process exited prematurely"
}

$serveArgs = @("-m", "agentkit", "serve", "--workspace", ".", "--host", $ServeHost, "--port", "$ServePort", "--require-token", "--token", $Token, "--log-level", $LogLevel)
$serveProc = Start-Process -FilePath $PythonExe -ArgumentList $serveArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $serveOut -RedirectStandardError $serveErr
Set-Content -Encoding ascii -Path (Join-Path $workspacePath ".agentkit/serve.pid") -Value $serveProc.Id

Start-Sleep -Seconds 2
if ($serveProc.HasExited) {
  Write-Host "agentkit-serve failed to start"
  if (Test-Path $serveErr) { Get-Content $serveErr }
  if (Test-Path $serveOut) { Get-Content $serveOut }
  throw "agentkit-serve process exited prematurely"
}

$stubHealth = Invoke-RestMethod -Method Get -Uri ("http://{0}:{1}/health" -f $StubHost, $StubPort)
$serveHealth = Invoke-RestMethod -Method Get -Uri ("http://{0}:{1}/health" -f $ServeHost, $ServePort)
Write-Host "stub health:" ($stubHealth | ConvertTo-Json -Compress)
Write-Host "serve health:" ($serveHealth | ConvertTo-Json -Compress)

$headers = @{ Authorization = "Bearer $Token" }
$runPayload = @{ task = $TaskPath } | ConvertTo-Json
$runResp = Invoke-RestMethod -Method Post -Uri ("http://{0}:{1}/v1/tasks/run" -f $ServeHost, $ServePort) -Headers $headers -ContentType "application/json" -Body $runPayload
Write-Host "run response:" ($runResp | ConvertTo-Json -Depth 8)

$verifyPayload = @{ task_id = $runResp.task_id } | ConvertTo-Json
$verifyResp = Invoke-RestMethod -Method Post -Uri ("http://{0}:{1}/v1/tasks/verify" -f $ServeHost, $ServePort) -Headers $headers -ContentType "application/json" -Body $verifyPayload
Write-Host "verify response:" ($verifyResp | ConvertTo-Json -Depth 8)

Write-Host "logs:"
Write-Host "-" (Join-Path $workspacePath ".agentkit/logs/agentkit-serve.log")
Write-Host "-" $serveOut
Write-Host "-" $serveErr
Write-Host "-" $stubOut
Write-Host "-" $stubErr

if (-not $KeepAlive) {
  if (-not $serveProc.HasExited) { Stop-Process -Id $serveProc.Id -Force }
  if (-not $stubProc.HasExited) { Stop-Process -Id $stubProc.Id -Force }
}
