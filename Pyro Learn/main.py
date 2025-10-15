# Arquivo: main.py
import os
os.environ["PYRO_PREFER_IP_VERSION"] = "4"

import sys
import time
import threading
import subprocess
import platform
import Pyro5.api

Pyro5.config.SERVERTYPE = "thread"
Pyro5.config.THREADPOOL_SIZE = 50
Pyro5.config.SOCK_NODELAY = True
Pyro5.config.COMMTIMEOUT = 2.0
Pyro5.config.POLLTIMEOUT = 2.0

# Importações dos novos arquivos
from peer import Peer
import config

def verificar_servidor_nomes():
    try:
        ns = Pyro5.api.locate_ns()
        return ns
    except Pyro5.errors.NamingError:
        print("[SISTEMA] Iniciando Servidor de Nomes...")
        try:
            comando = [sys.executable, "-m", "Pyro5.nameserver", "--host", "127.0.0.1"]
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(comando, startupinfo=startupinfo)
            time.sleep(3)
            ns = Pyro5.api.locate_ns()
            return ns
        except Exception as e:
            print(f"\nERRO: Falha ao iniciar Servidor de Nomes: {e}")
            print(f"Inicie manualmente: {sys.executable} -m Pyro5.nameserver\n")
            return None

def main():
    if len(sys.argv) != 2:
        print(f"Uso: python main.py <NomeDoPeer>")
        print(f"Peers disponiveis: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)
    
    nome_peer = sys.argv[1]
    
    if nome_peer not in config.TODOS_PEERS:
        print(f"Erro: '{nome_peer}' nao e um nome valido!")
        print(f"Peers disponiveis: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"INICIANDO {nome_peer}")
    print(f"{'='*60}\n")
    
    ns = verificar_servidor_nomes()
    if not ns:
        sys.exit(1)
    
    daemon = Pyro5.api.Daemon(host="127.0.0.1")
    peer = Peer(nome_peer)
    uri = daemon.register(peer)
    
    try:
        ns.register(nome_peer, uri)
    except Exception as e:
        print(f"[{nome_peer}] ERRO ao registrar: {e}")
        sys.exit(1)

    peer.configurar_descoberta(ns)
    
    time.sleep(2)
    
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    
    print(f"{'='*60}")
    print(f"{nome_peer} PRONTO")
    print(f"{'='*60}")
    print("\nComandos: pedir, liberar, status, peers, sair\n")
    
    try:
        while True:
            entrada = input(f"{nome_peer}> ").strip().lower()
            if not entrada: continue

            if entrada == "sair": 
                break
            elif entrada == "pedir": 
                threading.Thread(target=peer.solicitar_sc, daemon=True).start()
            elif entrada == "liberar": 
                peer.liberar_sc()
            elif entrada == "status":
                estado = peer.obter_estado_completo()
                print(f"\n{'='*60}")
                print(f"ESTADO DE {estado['nome']}")
                print(f"{'='*60}")
                print(f"  Estado          : {estado['estado']}")
                print(f"  Relogio Logico  : {estado['relogio']}")
                print(f"  Timestamp Pedido: {estado['timestamp_pedido']}")
                print(f"  Peers Ativos    : {estado['peers_ativos']}")
                print(f"  Peers Conhecidos: {estado['peers_conhecidos']}")
                print(f"{'='*60}\n")
            elif entrada == "peers":
                print(f"Peers ativos: {list(peer.peers_ativos)}")
            else: 
                print("Comando desconhecido.")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        print(f"\n[{nome_peer}] Encerrando...")
        peer.parar()
        try:
            ns.remove(nome_peer)
        except Exception: 
            pass
        print(f"[{nome_peer}] Encerrado.\n")

if __name__ == "__main__":
    main()