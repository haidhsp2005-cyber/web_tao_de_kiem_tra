import os
import sys
import socket
import uvicorn

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def find_available_port(start_port=8888, fallbacks=(8088, 8800, 9000, 9999)):
    for port in [start_port, *fallbacks]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', port)) != 0:
                    return port
        except Exception:
            pass
    return start_port

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
        
    env_port = os.getenv("PORT")
    port = int(env_port) if env_port and env_port.isdigit() else find_available_port(8888)
    env_host = os.getenv("HOST", "0.0.0.0" if env_port else "127.0.0.1")

    print('=' * 60)
    print('  EduExam AI 2026 - Tao & Tron De Kiem Tra Chuan Nam Hoc 2026 - 2027')
    print(f'  Server running at: http://{env_host}:{port}')
    print('=' * 60)
    uvicorn.run('app.main:app', host=env_host, port=port, reload=False)
