@echo off
cd /d "%~dp0backend"
echo === Testing Python and imports ===
python3.12 -c "import sys; print(f'Python {sys.version}')"
echo.
echo === Testing imports ===
python3.12 -c "from v2x_channel import channel; print('v2x_channel OK')"
python3.12 -c "from collision_detector import get_collision_pairs; print('collision_detector OK')"
python3.12 -c "from priority_negotiation import compute_decisions_for_all; print('priority_negotiation OK')"
python3.12 -c "from infrastructure_agent import InfrastructureAgent; print('infrastructure_agent OK')"
python3.12 -c "from simulation import simulation; print('simulation OK')"
python3.12 -c "from main import app; print('main.py OK')"
python3.12 -c "import uvicorn; print('uvicorn OK')"
echo.
echo === All tests done ===
pause
