# ==================================================
# Arquivo: main.py (versão com patch de timeout)
# ==================================================

import os
import sys
import time
import threading
import subprocess
import platform
import Pyro5.api

# --- Configuração de rede e Pyro ---
os.environ["PYRO_PREFER_IP_VERSION"] = "4"

Pyro5.config.SERVERTYPE = "thread"
Pyro5.config.THREADPOOL_SIZE = 50
Pyro5.config.SOCK_NODELAY = True
Pyro5.config.COMMTIMEOUT = 2.0

# --- Importações locais ---
from peer import Peer
import config


def verificar_servidor_nomes():
    """Inicia ou localiza o servidor de nomes Pyro5"""
    try:
        ns = Pyro5.api.locate_ns()
        print("[SERVIDOR DE NOMES] Servidor de nomes encontrado!")
        return ns
    except Pyro5.errors.NamingError:
        print("[SERVIDOR DE NOMES] Servidor de nomes não encontrado. Tentando iniciar...")
        try:
            comando = [sys.executable, "-m", "Pyro5.nameserver", "--host", "127.0.0.1"]
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(comando, startupinfo=startupinfo)
            time.sleep(3)
            ns = Pyro5.api.locate_ns()
            print("[SERVIDOR DE NOMES] Servidor iniciado e encontrado com sucesso!")
            return ns
        except Exception as e:
            print("\nERRO: Falha ao iniciar ou encontrar o Servidor de Nomes.")
            print(f"Por favor, inicie-o manualmente: {sys.executable} -m Pyro5.nameserver\n")
            return None


def main():
    if len(sys.argv) != 2:
        print(f"Uso: python main.py <NomeDoPeer>\nPeers disponíveis: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)

    nome_peer = sys.argv[1]

    if nome_peer not in config.TODOS_PEERS:
        print(f"Erro: '{nome_peer}' não é um nome válido!\nPeers disponíveis: {', '.join(config.TODOS_PEERS)}")
        sys.exit(1)

    print(f"\n{'='*50}\nINICIANDO {nome_peer}\n{'='*50}\n")

    # --- Localiza ou inicia o NameServer ---
    ns = verificar_servidor_nomes()
    if not ns:
        sys.exit(1)

    # --- Criação do Daemon e aplicação do patch de timeout ---
    daemon = Pyro5.api.Daemon(host="127.0.0.1")

    # PATCH: reduzir timeout padrão do select() interno (corrige delay de 4.5s no Windows 10)
    try:
        if hasattr(daemon, "sock"):
            daemon.sock.settimeout(0.1)
            print(f"[PATCH] Timeout principal do daemon ajustado para 0.1s")
        if hasattr(daemon, "sockets"):
            for s in daemon.sockets:
                s.settimeout(0.1)
            print(f"[PATCH] Timeout de sockets individuais ajustado para 0.1s")
    except Exception as e:
        print(f"[PATCH] Falha ao ajustar timeout do daemon: {e}")

    # --- Registro do peer ---
    peer = Peer(nome_peer)
    uri = daemon.register(peer)

    try:
        ns.register(nome_peer, uri)
        print(f"[{nome_peer}] Registrado com sucesso!")
    except Exception as e:
        print(f"[{nome_peer}] ERRO ao registrar: {e}")
        sys.exit(1)

    peer.configurar_descoberta(ns)

    print(f"[{nome_peer}] Procurando peers existentes...")
    time.sleep(2)

    # --- Inicia o loop do daemon em thread separada ---
    threading.Thread(target=daemon.requestLoop, daemon=True).start()

    print(f"\n{'='*50}\n{nome_peer} ESTÁ PRONTO!\n{'='*50}")
    print("\nComandos: pedir, liberar, status, peers, listar_ns, sair\n")

    try:
        while True:
            entrada = input(f"{nome_peer}> ").strip().lower()
            if not entrada:
                continue

            if entrada == "sair":
                break
            elif entrada == "pedir":
                threading.Thread(target=peer.solicitar_sc, daemon=True).start()
            elif entrada == "liberar":
                peer.liberar_sc()
            elif entrada == "status":
                estado = peer.obter_estado_completo()
                print(f"\n--- Estado de {estado['nome']} ---")
                print(f"  Estado Lógico: {estado['estado']}")
                print(f"  Relógio Lógico: {estado['relogio']}")
                print(f"  Timestamp Pedido: {estado['timestamp_pedido']}")
                print(f"  Peers Ativos: {estado['peers_ativos']}")
                print(f"  Peers Conhecidos: {estado['peers_conhecidos']}\n")
            elif entrada == "peers":
                print(f"Peers ativos: {list(peer.peers_ativos)}")
            elif entrada == "listar_ns":
                print(f"Registros no NS: {list(ns.list().keys())}")
            else:
                print("Comando desconhecido.")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        print(f"[{nome_peer}] Encerrando...")
        peer.parar()
        try:
            ns.remove(nome_peer)
            print(f"[{nome_peer}] Registro removido do servidor de nomes.")
        except Exception:
            pass
        print(f"[{nome_peer}] Encerrado.")


if __name__ == "__main__":
    main()
