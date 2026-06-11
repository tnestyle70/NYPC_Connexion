@echo off
rem Connexion local contest portal launcher
rem - opens a console window running the WSL server (close it to stop)
rem - then opens the portal in your default browser
start "Connexion Portal Server" wsl bash -lc "cd /mnt/c/Users/tnest/Desktop/Connexion && python3 scripts/contest_server.py --port 8733"
timeout /t 2 /nobreak >nul
start http://localhost:8733/problems/1
