<<<<<<< HEAD
# main.py - Inicialização do Sistema
=======
# Arquivo: main.py
import os
os.environ["PYRO_PREFER_IP_VERSION"] = "4"
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5

import sys
import time
import threading
import subprocess
import platform
<<<<<<< HEAD
=======
import Pyro5.api

Pyro5.config.SERVERTYPE = "thread"
Pyro5.config.THREADPOOL_SIZE = 50
Pyro5.config.SOCK_NODELAY = True
Pyro5.config.COMMTIMEOUT = 2.0
Pyro5.config.POLLTIMEOUT = 2.0

# Importações dos novos arquivos
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
from peer import Peer
import config

def iniciar_ns():
    try:
<<<<<<< HEAD
        ns = Pyro5.api.locate_ns(host="127.0.0.1")
        print("[NS] Servidor de nomes encontrado!")
        return ns
    except:
        print("[NS] Iniciando servidor de nomes...")
        try:
            cmd = [sys.executable, "-m", "Pyro5.nameserver", "-n", "127.0.0.1"]
=======
        ns = Pyro5.api.locate_ns()
        return ns
    except Pyro5.errors.NamingError:
        print("[SISTEMA] Iniciando Servidor de Nomes...")
        try:
            comando = [sys.executable, "-m", "Pyro5.nameserver", "--host", "127.0.0.1"]
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(cmd, startupinfo=startupinfo)
            time.sleep(3)
<<<<<<< HEAD
            ns = Pyro5.api.locate_ns(host="127.0.0.1")
            print("[NS] Servidor iniciado!")
            return ns
        except Exception as e:
            print(f"\nERRO: {e}")
            print(f"Inicie manualmente: {sys.executable} -m Pyro5.nameserver -n 127.0.0.1\n")
=======
            ns = Pyro5.api.locate_ns()
            return ns
        except Exception as e:
            print(f"\nERRO: Falha ao iniciar Servidor de Nomes: {e}")
            print(f"Inicie manualmente: {sys.executable} -m Pyro5.nameserver\n")
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
            return None

def main():
    if len(sys.argv) != 2:
        print(f"Uso: python main.py <NomeDoPeer>")
<<<<<<< HEAD
        print(f"Peers: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)
    
    nome = sys.argv[1]
    if nome not in config.TODOS_PEERS:
        print(f"Erro: '{nome}' inválido!")
        print(f"Peers: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)
    
    print(f"\n{'='*50}\nINICIANDO {nome}\n{'='*50}\n")
=======
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
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
    
    ns = iniciar_ns()
    if not ns:
        sys.exit(1)
    
<<<<<<< HEAD
    daemon = Pyro5.api.Daemon()
    peer = Peer(nome)
    uri = daemon.register(peer)
    
    try:
        ns.register(nome, uri)
        print(f"[{nome}] Registrado!")
=======
    daemon = Pyro5.api.Daemon(host="127.0.0.1")
    peer = Peer(nome_peer)
    uri = daemon.register(peer)
    
    try:
        ns.register(nome_peer, uri)
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
    except Exception as e:
        print(f"[{nome}] Erro ao registrar: {e}")
        sys.exit(1)
    
<<<<<<< HEAD
    peer.configurar(ns)
=======
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
    time.sleep(2)
    
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    
<<<<<<< HEAD
    print(f"\n{'='*50}\n{nome} PRONTO!\n{'='*50}")
=======
    print(f"{'='*60}")
    print(f"{nome_peer} PRONTO")
    print(f"{'='*60}")
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
    print("\nComandos: pedir, liberar, status, peers, sair\n")
    
    try:
        while True:
<<<<<<< HEAD
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
=======
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
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5

if __name__ == "__main__":
    main()