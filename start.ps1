# ============================================
# Retail Sales Agent - Start Script
# Starts both Backend and Frontend servers
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   🛒 RETAIL SALES AGENT - LAUNCHER" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { "d:\Projects\retail_sales_agent" }
$frontendPath = "$projectRoot\ey-frontend\E-Y"

# Start Backend Server
Write-Host "🚀 Starting Backend Server (FastAPI)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
    `$Host.UI.RawUI.WindowTitle = 'Backend - FastAPI (Port 8000)'
    cd '$projectRoot'
    Write-Host '============================================' -ForegroundColor Green
    Write-Host '   BACKEND SERVER - FastAPI' -ForegroundColor Green
    Write-Host '   http://localhost:8000' -ForegroundColor Green
    Write-Host '   API Docs: http://localhost:8000/docs' -ForegroundColor Green
    Write-Host '============================================' -ForegroundColor Green
    Write-Host ''
    python api_server.py
"@

# Wait for backend to initialize
Write-Host "⏳ Waiting for backend to start..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Start Frontend Server
Write-Host "🚀 Starting Frontend Server (Next.js)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
    `$Host.UI.RawUI.WindowTitle = 'Frontend - Next.js (Port 9002)'
    cd '$frontendPath'
    Write-Host '============================================' -ForegroundColor Magenta
    Write-Host '   FRONTEND SERVER - Next.js' -ForegroundColor Magenta
    Write-Host '   http://localhost:9002' -ForegroundColor Magenta
    Write-Host '============================================' -ForegroundColor Magenta
    Write-Host ''
    npm run dev
"@

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   ✅ SERVERS STARTED!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:9002" -ForegroundColor Magenta
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "   Close the PowerShell windows to stop servers" -ForegroundColor Yellow
Write-Host ""

# Optional: Open browser after a delay
Start-Sleep -Seconds 8
Write-Host "🌐 Opening browser..." -ForegroundColor Green
Start-Process "http://localhost:9002"
