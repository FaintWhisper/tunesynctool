#!/usr/bin/env pwsh
# Reinstall tunesynctool in editable mode

Write-Host "Uninstalling tunesynctool..." -ForegroundColor Yellow
pip uninstall -y tunesynctool

Write-Host "`nInstalling tunesynctool in editable mode..." -ForegroundColor Yellow
pip install -e .

Write-Host "`nDone!" -ForegroundColor Green
