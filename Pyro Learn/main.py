# Arquivo: main.py
# (Código completo com as alterações)

import Pyro5.api
import Pyro5.nameserver
import sys
import time
import threading
import subprocess # <-- ALTERAÇÃO: para iniciar o servidor de nomes
import platform   # <-- ALTERAÇÃO: para ajustes de SO
from peer import Peer

# Lista de todos os peers do sistema
TODOS_PEERS = ["PeerA", "PeerB", "PeerC", "PeerD"]

# <<< FUNÇÃO MODIFICADA: para iniciar o servidor de nomes automaticamente >>>
def verificar_servidor_nomes():
    """
    Verifica se o Servidor de Nomes está rodando.
    Se não estiver, tenta iniciá-lo automaticamente.
    Retorna o proxy do servidor de nomes ou None em caso de falha.
    """
    try:
        ns = Pyro5.api.locate_ns()
        print("[SERVIDOR DE NOMES] Servidor de nomes encontrado!")
        return ns
    except Pyro5.errors.NamingError:
        print("[SERVIDOR DE NOMES] Servidor de nomes não encontrado.")
        print("[SERVIDOR DE NOMES] Tentando iniciar automaticamente...")
        
        try:
            # Usa sys.executable para garantir que está usando o mesmo python
            comando = [sys.executable, "-m", "Pyro5.nameserver"]
            
            # No Windows, oculta a janela do console que seria aberta
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # Inicia o processo em segundo plano
            subprocess.Popen(comando, startupinfo=startupinfo)
            
            print("[SERVIDOR DE NOMES] Aguardando inicialização (3 segundos)...")
            time.sleep(3)
            
            # Tenta localizar novamente
            ns = Pyro5.api.locate_ns()
            print("[SERVIDOR DE NOMES] Servidor iniciado e encontrado com sucesso!")
            return ns
            
        except (FileNotFoundError, Pyro5.errors.NamingError) as e:
            print("\n" + "="*60)
            print("ERRO: Falha ao iniciar ou encontrar o Servidor de Nomes automaticamente.")
            print(f"Detalhe: {e}")
            print("="*60)
            print("\nPor favor, inicie o servidor de nomes manualmente em outro terminal:")
            print(f"  {sys.executable} -m Pyro5.nameserver")
            print("\nDepois execute este peer novamente.")
            print("="*60 + "\n")
            return None
# <<< FIM DA FUNÇÃO MODIFICADA >>>

def main():
    """
    Função principal que inicializa um peer.
    """
    if len(sys.argv) != 2:
        print("Uso: python main.py <NomeDoPeer>")
        print(f"Peers disponíveis: {', '.join(TODOS_PEERS)}")
        sys.exit(1)
    
    nome_peer = sys.argv[1]
    
    if nome_peer not in TODOS_PEERS:
        print(f"Erro: '{nome_peer}' não é um nome válido!")
        print(f"Peers disponíveis: {', '.join(TODOS_PEERS)}")
        sys.exit(1)
    
    print(f"\n{'='*50}")
    print(f"INICIANDO {nome_peer}")
    print(f"{'='*50}\n")
    
    # ETAPA 1: Verifica/inicia o servidor de nomes
    # <<< ALTERAÇÃO: A função agora retorna o objeto ns ou None >>>
    ns = verificar_servidor_nomes()
    if not ns:
        sys.exit(1)
    
    # ETAPA 2: Cria o daemon
    daemon = Pyro5.api.Daemon()
    
    # ETAPA 3: Cria a instância do peer
    peer = Peer(nome_peer)
    uri = daemon.register(peer)
    
    # ETAPA 4: Registra o peer no servidor de nomes
    # <<< ALTERAÇÃO: Usa o objeto 'ns' que já foi localizado >>>
    try:
        ns.register(nome_peer, uri)
        print(f"[{nome_peer}] Registrado com sucesso!")
    except Exception as e:
        print(f"[{nome_peer}] ERRO: Não foi possível registrar no servidor de nomes: {e}")
        sys.exit(1)

    # ETAPA 5: Configura descoberta contínua
    peer.configurar_descoberta(ns, TODOS_PEERS)
    
    print(f"[{nome_peer}] Procurando peers existentes...")
    time.sleep(2)
    
    # ETAPA 6: Inicia o loop do daemon
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    
    # ETAPA 7: Interface do usuário
    print(f"\n{'='*50}")
    print(f"{nome_peer} ESTÁ PRONTO!")
    print(f"  (A seção crítica será liberada automaticamente após 10s)")
    print(f"{'='*50}")
    print("\nComandos disponíveis:")
    print("  pedir       - Solicita acesso à Seção Crítica")
    print("  liberar     - Libera a Seção Crítica (manualmente)")
    print("  status      - Mostra o estado atual do peer")
    print("  peers       - Lista peers conhecidos e seu status (ativo/inativo)")
    print("  listar_ns   - Lista todos os nomes no servidor de nomes")
    print("  sair        - Encerra o peer")
    print()
    
    # Loop de comandos
    while True:
        try:
            entrada = input(f"{nome_peer}> ").strip().split()
            if not entrada:
                continue
            
            comando = entrada[0].lower()
            
            if comando == "sair":
                break
            
            elif comando == "pedir":
                threading.Thread(target=peer.solicitar_sc, daemon=True).start()
            
            elif comando == "liberar":
                peer.liberar_sc()
            
            elif comando == "status":
                estado = peer.obter_estado()
                print(f"\n{'='*40}")
                print(f"Estado de {estado['nome']}:")
                print(f"  - Estado atual: {estado['estado']}")
                print(f"  - Relógio lógico: {estado['relogio']}")
                print(f"  - Peers ativos: {estado['peers_ativos']}")
                print(f"{'='*40}\n")
            
            elif comando == "peers":
                conhecidos = peer.listar_peers_conhecidos()
                ativos = set(peer.obter_estado()['peers_ativos'])
                print(f"\n{'='*40}")
                print("Status dos Peers Conhecidos:")
                for p in conhecidos:
                    status = "💚 ATIVO" if p in ativos else "☠️  INATIVO"
                    print(f"  - {p}: {status}")
                print(f"{'='*40}\n")
            
            elif comando == "listar_ns":
                print("\nPeers registrados no servidor de nomes:")
                try:
                    # <<< ALTERAÇÃO: Usa o objeto 'ns' que já temos >>>
                    registrados = ns.list()
                    for nome, uri_obj in registrados.items():
                        print(f"  - {nome}")
                except Exception as e:
                    print(f"Erro ao listar: {e}")
                print()

            else:
                print(f"Comando desconhecido: {comando}")
        
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"Erro inesperado: {e}")

    # Encerramento limpo
    print(f"\n[{nome_peer}] Encerrando...")
    peer.parar()
    try:
        # <<< ALTERAÇÃO: Usa o objeto 'ns' que já temos >>>
        ns.remove(nome_peer)
        print(f"[{nome_peer}] Registro removido do servidor de nomes.")
    except Exception as e:
        print(f"[{nome_peer}] Erro ao remover registro do servidor de nomes: {e}")
    
    print(f"[{nome_peer}] Encerrado.")


if __name__ == "__main__":
    main()