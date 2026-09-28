# start.ps1 - get a PowerShell window ready to run the JobGuard eval harness.
# RUN IT WITH A DOT AND A SPACE IN FRONT so the settings stay in this window:
#     . .\start.ps1
Set-Location $PSScriptRoot
. "$PSScriptRoot\.venv\Scripts\Activate.ps1"
if ($env:ANTHROPIC_API_KEY -and $env:ANTHROPIC_API_KEY.StartsWith("sk-ant-")) {
    Write-Host "API key already set in this window." -ForegroundColor Green
} else {
    $k = Read-Host "Paste API key (starts with sk-ant-; hidden)" -AsSecureString
    $env:ANTHROPIC_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k))
    if ($env:ANTHROPIC_API_KEY.StartsWith("sk-ant-")) {
        Write-Host "API key set for this window only." -ForegroundColor Green
    } else {
        Write-Host "That doesn't look like an API key (should start with sk-ant-). Run . .\start.ps1 again." -ForegroundColor Red
    }
}
Write-Host "Ready. Try: python classify.py   or   python run_eval.py" -ForegroundColor Cyan