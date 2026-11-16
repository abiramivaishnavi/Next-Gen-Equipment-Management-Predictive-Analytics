# Starts the backend and frontend in two new windows and opens the app.
# Usage:  powershell -ExecutionPolicy Bypass -File E:\Equipment-Management-System\EMS_Project\start_all.ps1
$project = "E:\Equipment-Management-System\EMS_Project"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$project\backend'; .\venv\Scripts\python.exe -m uvicorn main:app --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$project\frontend'; npm run dev"
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
Write-Host "Two windows opened (backend + frontend). Keep them open while you use the app." -ForegroundColor Green