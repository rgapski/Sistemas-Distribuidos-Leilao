import subprocess
import sys
import time
import platform

def main():
    """Inicia todos os 4 peers em terminais/janelas separadas"""
    
    peers = ["PeerA", "PeerB", "PeerC", "PeerD"]
    sistema = platform.system()
    
    print("="*60)
    print("Iniciando Sistema Distribuído - Algoritmo de Ricart e Agrawala")
    print("="*60)
    print(f"\nSistema Operacional detectado: {sistema}")
    print(f"Iniciando {len(peers)} peers...\n")
    
    processos = []
    
    for peer in peers:
        print(f"Iniciando {peer}...")
        
        try:
            if sistema == "Windows":
                # Windows: Abre em nova janela do cmd
                processo = subprocess.Popen(
                    f'start cmd /k python main.py {peer}',
                    shell=True
                )
            
            elif sistema == "Darwin":  # macOS
                # macOS: Abre em nova aba do Terminal
                apple_script = f'''
                tell application "Terminal"
                    do script "cd {subprocess.check_output(['pwd']).decode().strip()} && python3 main.py {peer}"
                end tell
                '''
                processo = subprocess.Popen(
                    ['osascript', '-e', apple_script]
                )
            
            elif sistema == "Linux":
                # Linux: Tenta diferentes emuladores de terminal
                terminais = [
                    ['gnome-terminal', '--', 'python3', 'main.py', peer],
                    ['xterm', '-e', 'python3', 'main.py', peer],
                    ['konsole', '-e', 'python3', 'main.py', peer],
                    ['xfce4-terminal', '-e', f'python3 main.py {peer}'],
                ]
                
                sucesso = False
                for cmd in terminais:
                    try:
                        processo = subprocess.Popen(cmd)
                        sucesso = True
                        break
                    except FileNotFoundError:
                        continue
                
                if not sucesso:
                    print(f"  ⚠ Nenhum terminal compatível encontrado para {peer}")
                    print("  Execute manualmente: python3 main.py", peer)
                    continue
            
            else:
                print(f"  ⚠ Sistema operacional não suportado: {sistema}")
                print(f"  Execute manualmente: python main.py {peer}")
                continue
            
            processos.append(processo)
            print(f"  ✓ {peer} iniciado")
            time.sleep(1)  # Delay entre inicializações
        
        except Exception as e:
            print(f"  ✗ Erro ao iniciar {peer}: {e}")
    
    print("\n" + "="*60)
    print(f"✓ {len(processos)} peers iniciados com sucesso!")
    print("="*60)
    print("\nPressione Ctrl+C para encerrar todos os processos...")
    
    try:
        # Mantém o script rodando
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nEncerrando todos os processos...")
        for processo in processos:
            try:
                processo.terminate()
            except:
                pass
        print("Processos encerrados.")

if __name__ == "__main__":
    main()