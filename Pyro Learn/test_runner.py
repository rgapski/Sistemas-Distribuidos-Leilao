# Arquivo: test_runner.py

import subprocess
import time
import platform
import sys
import os
import threading
import Pyro5.api

# Importa as configurações do seu projeto
import config

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def verificar_servidor_nomes():
    """Tenta localizar o NS. Se não encontrar, não faz nada (assume que os peers farão)."""
    try:
        Pyro5.api.locate_ns()
        print("[Runner] Servidor de Nomes já está em execução.")
        return True
    except Pyro5.errors.NamingError:
        print("[Runner] Servidor de Nomes não encontrado. Será iniciado pelo primeiro peer.")
        return False

def start_peer_process(peer_name):
    """Inicia um peer em uma nova janela de terminal."""
    command = [sys.executable, "main.py", peer_name]
    
    # Comandos para abrir um novo terminal variam por SO
    system = platform.system()
    if system == "Windows":
        return subprocess.Popen(["cmd", "/c", "start", f"Peer {peer_name}"] + command)

def main():
    """Script principal para iniciar e controlar os peers."""
    verificar_servidor_nomes()
    
    processes = []
    print("[Runner] Iniciando todos os peers em novos terminais...")
    for name in config.TODOS_PEERS:
        p = start_peer_process(name)
        if p:
            processes.append(p)
        time.sleep(0.5) # Pequeno intervalo entre os lançamentos

    print("\n[Runner] Peers iniciados. Aguardando 5 segundos para estabilização da rede...")
    time.sleep(5)

    print("\n" + "="*50)
    print("CONSOLE DE CONTROLE")
    print("="*50)
    print("Comandos disponíveis:")
    print("  pedir <nome_peer>        - Envia um pedido de SC para o peer.")
    print("  liberar <nome_peer>      - Manda o peer liberar a SC.")
    print("  status <nome_peer>       - Mostra o status de um peer.")
    print("  race <peer1> <peer2>     - Simula uma disputa entre dois peers.")
    print("  sair                     - Encerra todos os peers e o runner.")
    print("="*50 + "\n")

    try:
        while True:
            cmd_input = input("Control> ").strip().split()
            if not cmd_input:
                continue

            command = cmd_input[0].lower()

            if command == "sair":
                break
            
            try:
                if command == "pedir" and len(cmd_input) == 2:
                    proxy = Pyro5.api.Proxy(f"PYRONAME:{cmd_input[1]}")
                    threading.Thread(target=proxy.solicitar_sc, daemon=True).start()
                    print(f"[Runner] Comando 'pedir' enviado para {cmd_input[1]}.")

                elif command == "liberar" and len(cmd_input) == 2:
                    proxy = Pyro5.api.Proxy(f"PYRONAME:{cmd_input[1]}")
                    proxy.liberar_sc()
                    print(f"[Runner] Comando 'liberar' enviado para {cmd_input[1]}.")

                elif command == "status" and len(cmd_input) == 2:
                    proxy = Pyro5.api.Proxy(f"PYRONAME:{cmd_input[1]}")
                    estado = proxy.obter_estado_completo()
                    print(f"\n--- Status de {cmd_input[1]} ---")
                    for key, value in estado.items():
                        print(f"  {key}: {value}")
                    print("--- Fim do Status ---\n")

                elif command == "race" and len(cmd_input) == 3:
                    peer1, peer2 = cmd_input[1], cmd_input[2]
                    proxy1 = Pyro5.api.Proxy(f"PYRONAME:{peer1}")
                    proxy2 = Pyro5.api.Proxy(f"PYRONAME:{peer2}")
                    
                    print(f"[Runner] Disparando pedidos de {peer1} e {peer2} quase simultaneamente...")
                    # Dispara os pedidos em threads para não bloquear o console
                    threading.Thread(target=proxy1.solicitar_sc, daemon=True).start()
                    threading.Thread(target=proxy2.solicitar_sc, daemon=True).start()

                else:
                    print("Comando inválido ou argumentos incorretos.")

            except Exception as e:
                print(f"ERRO ao executar comando: {e}")

    except (KeyboardInterrupt, EOFError):
        print("\n[Runner] Encerrando...")
    finally:
        # Tenta encerrar os processos dos peers (pode não funcionar em todos os SOs)
        # O mais garantido é fechar as janelas dos terminais.
        print("[Runner] Script encerrado. Por favor, feche as janelas dos terminais dos peers.")

if __name__ == "__main__":
    main()