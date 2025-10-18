# main.py - Inicialização do Sistema

import Pyro5.api
import sys
import time
import threading
import subprocess
import platform
from peer import Peer
import config

def iniciar_ns():
    try:
        ns = Pyro5.api.locate_ns(host="127.0.0.1")
        print("[NS] Servidor de nomes encontrado!")
        return ns
    except:
        print("[NS] Iniciando servidor de nomes...")
        try:
            cmd = [sys.executable, "-m", "Pyro5.nameserver", "-n", "127.0.0.1"]
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(cmd, startupinfo=startupinfo)
            time.sleep(3)
            ns = Pyro5.api.locate_ns(host="127.0.0.1")
            print("[NS] Servidor iniciado!")
            return ns
        except Exception as e:
            print(f"\nERRO: {e}")
            print(f"Inicie manualmente: {sys.executable} -m Pyro5.nameserver -n 127.0.0.1\n")
            return None

def main():
    if len(sys.argv) != 2:
        print(f"Uso: python main.py <NomeDoPeer>")
        print(f"Peers: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)
    
    nome = sys.argv[1]
    if nome not in config.TODOS_PEERS:
        print(f"Erro: '{nome}' inválido!")
        print(f"Peers: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)
    
    print(f"\n{'='*50}\nINICIANDO {nome}\n{'='*50}\n")
    
    ns = iniciar_ns()
    if not ns:
        sys.exit(1)
    
    daemon = Pyro5.api.Daemon()
    peer = Peer(nome)
    uri = daemon.register(peer)
    
    try:
        ns.register(nome, uri)
        print(f"[{nome}] Registrado!")
    except Exception as e:
        print(f"[{nome}] Erro ao registrar: {e}")
        sys.exit(1)
    
    peer.configurar(ns)
    time.sleep(2)
    
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    
    print(f"\n{'='*50}\n{nome} PRONTO!\n{'='*50}")
    print("\nComandos: pedir, liberar, status, peers, sair\n")
    
    try:
        while True:
            cmd = input(f"{nome}> ").strip().lower()
            if not cmd:
                continue
            
            if cmd == "sair":
                break
            elif cmd == "pedir":
                threading.Thread(target=peer.solicitar_sc, daemon=True).start()
            elif cmd == "liberar":
                peer.liberar_sc()
            elif cmd == "status":
                peer.status()
            elif cmd == "peers":
                print(f"Peers ativos: {list(peer.peers_ativos)}")
            else:
                print("Comando desconhecido")
    
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        print(f"\n[{nome}] Encerrando...")
        peer.parar()
        try:
            ns.remove(nome)
        except:
            pass
        print(f"[{nome}] Encerrado.\n")

if __name__ == "__main__":
    main()