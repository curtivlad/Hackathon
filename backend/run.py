import subprocess, sys
result = subprocess.run(
    [sys.executable, '-c', 'print("hello"); import uvicorn; print("uvicorn ok")'],
    capture_output=True, text=True, cwd=r'C:\Users\Paul\Desktop\Hackaton\Hackathon\backend'
)
with open(r'C:\Users\Paul\Desktop\Hackaton\Hackathon\backend\output.txt', 'w') as f:
    f.write(f'STDOUT: {result.stdout}\nSTDERR: {result.stderr}\nRETCODE: {result.returncode}')
