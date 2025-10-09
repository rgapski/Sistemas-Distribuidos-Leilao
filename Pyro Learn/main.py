import Pyro5.api
import Pyro5.nameserver
import sys
import time
import threading
from peer import Peer

# Lista de todos os peers do sistema
TODOS_PEERS = ["PeerA", "PeerB", "PeerC", "PeerD"]

def verificar_servidor_nomes():
    """
    Verifica se o Servidor de Nomes está rodando.
    Se não estiver, instrui o usuário a iniciá-lo.
    """
    try:
        ns = Pyro5.api.locate_ns()
        print("[SERVIDOR DE NOMES] Servidor de nomes encontrado!")
        return True
    except Pyro5.errors.NamingError:
        print("\n" + "="*60)
        print("ERRO: Servidor de Nomes não está rodando!")
        print("="*60)
        print("\nPor favor, inicie o servidor de nomes manualmente em outro terminal:")
        print("  python -m Pyro5.nameserver")
        print("\nDepois execute este peer novamente.")
        print("="*60 + "\n")
        return False

def main():
    """
    Função principal que inicializa um peer.
    """
    # Verifica se o nome do peer foi passado como argumento
    if len(sys.argv) != 2:
        print("Uso: python main.py <NomeDoPeer>")
        print(f"Peers disponíveis: {', '.join(TODOS_PEERS)}")
        sys.exit(1)
    
    nome_peer = sys.argv[1]
    
    # Valida o nome do peer
    if nome_peer not in TODOS_PEERS:
        print(f"Erro: '{nome_peer}' não é um nome válido!")
        print(f"Peers disponíveis: {', '.join(TODOS_PEERS)}")
        sys.exit(1)
    
    print(f"\n{'='*50}")
    print(f"INICIANDO {nome_peer}")
    print(f"{'='*50}\n")
    
    # ETAPA 1: Verifica se o servidor de nomes está rodando
    if not verificar_servidor_nomes():
        sys.exit(1)
    
    # ETAPA 2: Cria o daemon (ouvinte) do PyRO
    print(f"[{nome_peer}] Criando daemon PyRO...")
    daemon = Pyro5.api.Daemon()
    
    # ETAPA 3: Cria a instância do peer e registra no daemon
    print(f"[{nome_peer}] Criando objeto Peer...")
    peer = Peer(nome_peer)
    uri = daemon.register(peer)
    print(f"[{nome_peer}] URI do peer: {uri}")
    
    # ETAPA 4: Registra o peer no servidor de nomes
    print(f"[{nome_peer}] Registrando no servidor de nomes...")
    max_tentativas_registro = 5
    ns = None
    
    for tentativa in range(max_tentativas_registro):
        try:
            ns = Pyro5.api.locate_ns()
            ns.register(nome_peer, uri)
            print(f"[{nome_peer}] Registrado com sucesso!")
            break
        except Exception as e:
            print(f"[{nome_peer}] Tentativa {tentativa + 1}/{max_tentativas_registro} falhou: {e}")
            if tentativa < max_tentativas_registro - 1:
                time.sleep(1)
            else:
                print(f"[{nome_peer}] ERRO: Não foi possível registrar no servidor de nomes!")
                sys.exit(1)
    
    # ETAPA 5: Configura descoberta contínua de peers
    print(f"\n[{nome_peer}] Configurando descoberta contínua de peers...")
    peer.configurar_descoberta(ns, TODOS_PEERS)
    
    # Aguarda um momento para descobrir peers iniciais
    print(f"[{nome_peer}] Procurando peers existentes...")
    time.sleep(2)
    
    print(f"\n[{nome_peer}] Peers conhecidos: {peer.listar_peers_conhecidos()}")
    print(f"[{nome_peer}] (Descoberta contínua ativa - novos peers serão detectados automaticamente)")
    
    # ETAPA 6: Inicia o loop do daemon em uma thread separada
    print(f"\n[{nome_peer}] Iniciando daemon em background...")
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    
    # ETAPA 7: Interface do usuário
    print(f"\n{'='*50}")
    print(f"{nome_peer} ESTÁ PRONTO!")
    print(f"{'='*50}")
    print("\nComandos disponíveis:")
    print("  pedir       - Solicita acesso à Seção Crítica")
    print("  liberar     - Libera a Seção Crítica")
    print("  status      - Mostra o estado atual do peer")
    print("  teste <peer> <mensagem> - Envia mensagem de teste")
    print("  peers       - Lista peers conhecidos")
    print("  descobrir   - Força busca de peers")
    print("  listar_ns   - Lista todos os nomes no servidor de nomes")
    print("  sair        - Encerra o peer")
    print()
    
    # Loop de comandos
    while True:
        try:
            entrada = input(f"{nome_peer}> ").strip().split(maxsplit=2)
            
            if not entrada:
                continue
            
            comando = entrada[0].lower()
            
            if comando == "sair":
                print(f"[{nome_peer}] Encerrando...")
                peer.parar()  # Para as threads
                ns.remove(nome_peer)
                break
            
            elif comando == "pedir":
                # Executa em uma thread separada para não travar a interface
                threading.Thread(target=peer.solicitar_sc, daemon=True).start()
            
            elif comando == "liberar":
                peer.liberar_sc()
            
            elif comando == "status":
                estado = peer.obter_estado()
                print(f"\n{'='*40}")
                print(f"Estado de {estado['nome']}:")
                print(f"  Estado atual: {estado['estado']}")
                print(f"  Relógio lógico: {estado['relogio']}")
                print(f"  Timestamp pedido: {estado['timestamp_pedido']}")
                print(f"  Respostas recebidas: {estado['respostas']}")
                print(f"  Pedidos na fila: {estado['fila_pedidos']}")
                print(f"  Peers conhecidos: {estado['peers_conhecidos']}")
                print(f"  Peers ativos: {estado['peers_ativos']}")
                print(f"{'='*40}\n")
            
            elif comando == "peers":
                conhecidos = peer.listar_peers_conhecidos()
                estado_info = peer.obter_estado()
                ativos = set(estado_info['peers_ativos'])
                
                print(f"\n{'='*40}")
                print("Peers conhecidos:")
                for p in conhecidos:
                    status = "💚 ATIVO" if p in ativos else "☠️  INATIVO"
                    print(f"  {p}: {status}")
                print(f"{'='*40}\n")
            
            elif comando == "descobrir":
                print(f"Forçando descoberta de peers...")
                for outro_peer in TODOS_PEERS:
                    if outro_peer != nome_peer and outro_peer not in peer.peer_uris:
                        try:
                            uri_outro = ns.lookup(outro_peer)
                            peer.registrar_peer(outro_peer, uri_outro)
                        except Exception as e:
                            print(f"Erro ao descobrir {outro_peer}: {e}")
                print(f"Peers conhecidos agora: {peer.listar_peers_conhecidos()}")
            
            elif comando == "listar_ns":
                print("Peers registrados no servidor de nomes:")
                try:
                    registrados = ns.list()
                    for nome, uri in registrados.items():
                        print(f"  {nome}: {uri}")
                except Exception as e:
                    print(f"Erro ao listar: {e}")
            
            elif comando == "teste":
                if len(entrada) < 3:
                    print("Uso: teste <peer> <mensagem>")
                    continue
                
                peer_destino = entrada[1]
                mensagem = entrada[2]
                
                if peer_destino not in peer.peer_uris:
                    print(f"Erro: Peer '{peer_destino}' não encontrado!")
                    continue
                
                try:
                    # Cria um proxy fresco para esta chamada
                    proxy_destino = peer.obter_proxy(peer_destino)
                    resposta = proxy_destino.mensagem_teste(mensagem, nome_peer)
                    print(f"Resposta de {peer_destino}: {resposta}")
                except Exception as e:
                    print(f"Erro ao comunicar com {peer_destino}: {e}")
            
            else:
                print(f"Comando desconhecido: {comando}")
        
        except KeyboardInterrupt:
            print(f"\n[{nome_peer}] Encerrando...")
            peer.parar()  # Para as threads
            ns.remove(nome_peer)
            break
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    main()