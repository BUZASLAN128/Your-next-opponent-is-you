[CmdletBinding()]
param(
    [string]$ModelPath = (
        "$HOME\.cache\huggingface\hub\models--Qwen--Qwen3-8B-GGUF\snapshots\" +
        "7c41481f57cb95916b40956ab2f0b139b296d974\Qwen3-8B-Q4_K_M.gguf"
    ),
    [ValidateRange(1024, 65535)]
    [int]$Port = 18100,
    [string]$Device = "Vulkan0",
    [string]$LlamaServerPath = "llama-server",
    [ValidateRange(5, 300)]
    [int]$ReadyTimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ModelAlias = "ynoy-extractor-qwen3-8b-q4km"
$ModelRevision = "7c41481f57cb95916b40956ab2f0b139b296d974"
$ModelSha256 = "D98CDCBD03E17CE47681435B5150E34C1417F50B5C0019DD560E4882C5745785"
$ModelBytes = 5027783488
$RuntimeSignature = "version: 9803 (5c7c22c3e)"

$resolvedModel = (Resolve-Path -LiteralPath $ModelPath).Path
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$repositoryPrefix = $repositoryRoot.TrimEnd("\") + "\"
if ($resolvedModel.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The public model file must remain outside the Git worktree."
}

$modelInfo = Get-Item -LiteralPath $resolvedModel
if (-not $modelInfo.PSIsContainer -and $modelInfo.Length -ne $ModelBytes) {
    throw "The local extractor model size does not match the pinned artifact."
}
if ($modelInfo.PSIsContainer) {
    throw "The local extractor model path must be a regular file."
}
$actualHash = (Get-FileHash -LiteralPath $resolvedModel -Algorithm SHA256).Hash
if ($actualHash -ne $ModelSha256) {
    throw "The local extractor model SHA-256 does not match the pinned artifact."
}

$command = Get-Command $LlamaServerPath -ErrorAction Stop
$savedPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$runtimeVersion = (& $command.Source --version 2>&1 | ForEach-Object { $_.ToString() } |
    Out-String).Trim()
$runtimeExitCode = $LASTEXITCODE
$ErrorActionPreference = $savedPreference
if ($runtimeExitCode -ne 0) {
    throw "llama-server version inspection failed."
}
if ($runtimeVersion.IndexOf($RuntimeSignature, [System.StringComparison]::Ordinal) -lt 0) {
    throw "llama-server does not match the locally validated pinned build."
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "The requested loopback port is already in use."
}

$stdout = Join-Path $env:TEMP "ynoy-qwen3-8b-$Port.stdout.log"
$stderr = Join-Path $env:TEMP "ynoy-qwen3-8b-$Port.stderr.log"
$quotedModel = '"' + $resolvedModel + '"'
$arguments = @(
    "-m", $quotedModel,
    "--alias", $ModelAlias,
    "--host", "127.0.0.1",
    "--port", "$Port",
    "--ctx-size", "8192",
    "--n-gpu-layers", "all",
    "--device", $Device,
    "--flash-attn", "on",
    "--cache-type-k", "q8_0",
    "--cache-type-v", "q8_0",
    "--parallel", "1",
    "--reasoning", "off",
    "--no-webui",
    "--log-disable"
)
$process = Start-Process -FilePath $command.Source -ArgumentList $arguments `
    -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru

try {
    $healthUrl = "http://127.0.0.1:$Port/health"
    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline -and -not $process.HasExited) {
        try {
            $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
            $ready = $health.status -eq "ok"
        }
        catch {
            $ready = $false
        }
        if ($ready) {
            break
        }
        Start-Sleep -Milliseconds 250
        $process.Refresh()
    }
    if (-not $ready) {
        throw "The local extractor did not become ready before the bounded timeout."
    }
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 5
    if ($ModelAlias -notin @($models.data.id)) {
        throw "The ready endpoint did not expose the pinned extractor alias."
    }
}
catch {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    throw
}

$result = [ordered]@{
    status = "ready"
    process_id = $process.Id
    endpoint = "http://127.0.0.1:$Port/v1/chat/completions"
    model = $ModelAlias
    model_revision = $ModelRevision
    model_artifact_sha256 = $ModelSha256.ToLowerInvariant()
    runtime_signature = $RuntimeSignature
    bind_address = "127.0.0.1"
    logging = "disabled"
    private_data_sent = $false
}
$receipt = $result | ConvertTo-Json -Depth 3 -Compress
[Console]::Out.WriteLine($receipt)
