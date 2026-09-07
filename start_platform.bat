@echo off
title INDstocks Private Algo Trading Platform
color 0A
echo ====================================================================
echo    Starting Private Algo Platform (100%% Free, Local & Worldwide)
echo ====================================================================
echo  * Laptop / PC URL : http://localhost:8000
echo  * Home Wi-Fi URL  : http://192.168.1.15:8000
echo  * Worldwide Mobile: Click [Mobile Link] button in Dashboard Header
echo  * Authorized User : Raxit@5001
echo ====================================================================
cd /d "C:\Users\Hrgaj\.gemini\antigravity\scratch\indstocks_algo_platform"

:: Launch browser after 2 seconds
start "" timeout /t 2 >nul & start http://localhost:8000

:: Start the Python backend server
"C:\Users\Hrgaj\AppData\Local\Programs\Python\Python312\python.exe" app.py
pause
