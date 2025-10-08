import sys
import threading
import time
import Pyro5.api
import Pyro5.nameserver
from peer import Peer

def iniciar_servidor_nomes():
    """Tenta iniciar o servidor de nomes se não existir"""
    try:
        # Tenta localizar o servidor de nomes existente
        ns = Pyro5.api.locate_ns()
        print("Servidor de Nomes já está rodando")
        return ns
    except Pyro5.errors.NamingError:
        # Servidor não existe, cria um novo
        print("Iniciando novo Servidor de Nomes...")
        thread = threading.Thread(
            target=Pyro5.nameserver.start_ns_loop,
            kwargs={'host': 'localhost'},
            daemon=True
        )
        thread.start()
        time.sleep(2)  # Aguarda inicialização
        return Pyro5.api.locate_ns()

def descobrir_peers(ns, nome_proprio):
    """Descobre os outros peers no servidor de nomes"""
    nomes_peers = ["PeerA", "PeerB", "PeerC", "PeerD"]
    peers_encontrados = {}
    
    print(f"\nBuscando outros peers...")
    
    for nome in nomes_peers:
        if nome == nome_proprio:
            continue
        
        tentativas = 0
        max_tentativas = 10
        
        while tentativas < max_tentativas:
            try:
                uri = ns.lookup(nome)
                proxy = Pyro5.api.Proxy(uri)
                proxy._pyroTimeout = 3.0  # Timeout de 3 segundos
                
                # Testa a conexão
                proxy._pyroBind()
                
                peers_encontrados[nome] = proxy
                print(f"✓ {nome} encontrado")
                break
                
            except Exception as e:
                tentativas += 1
                if tentativas < max_tentativas:
                    time.sleep(1)
    
    print(f"\nTotal de peers encontrados: {len(peers_encontrados)}")
    return peers_encontrados

def interface_usuario(peer):
    """Interface de linha de comando para o usuário"""
    print(f"\n{'='*60}")
    print(f"Interface do {peer.nome}")
    print(f"{'='*60}")
    print("Comandos disponíveis:")
    print("  pedir    - Solicita acesso à Seção Crítica")
    print("  liberar  - Libera a Seção Crítica manualmente")
    print("  status   - Mostra o status atual do peer")
    print("  sair     - Encerra o peer")
    print(f"{'='*60}\n")
    
    while True:
        try:
            comando = input(f"[{peer.nome}] > ").strip().lower()
            
            if comando == "pedir":
                threading.Thread(target=peer.solicitar_sc, daemon=True).start()
            
            elif comando == "liberar":
                peer.liberar_sc()
            
            elif comando == "status":
                status = peer.obter_status()
                print(f"\n{'='*60}")
                print(f"STATUS DO {status['nome']}")
                print(f"{'='*60}")
                print(f"Estado: {status['estado']}")
                print(f"Relógio Lógico: {status['relogio']}")
                print(f"Timestamp do Pedido: {status['timestamp_pedido']}")
                print(f"Peers Ativos: {', '.join(status['peers_ativos']) if status['peers_ativos'] else 'Nenhum'}")
                print(f"{'='*60}\n")
            
            elif comando == "sair":
                print(f"[{peer.nome}] Encerrando...")
                peer.parar()
                break
            
            elif comando == "":
                continue
            
            else:
                print(f"Comando desconhecido: {comando}")
        
        except KeyboardInterrupt:
            print(f"\n[{peer.nome}] Encerrando...")
            peer.parar()
            break
        except Exception as e:
            print(f"Erro: {e}")

def main():
    if len(sys.argv) != 2:
        print("Uso: python main.py <NomeDoPeer>")
        print("Exemplo: python main.py PeerA")
        sys.exit(1)
    
    nome_peer = sys.argv[1]
    
    if nome_peer not in ["PeerA", "PeerB", "PeerC", "PeerD"]:
        print("Nome do peer deve ser: PeerA, PeerB, PeerC ou PeerD")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Iniciando {nome_peer}")
    print(f"{'='*60}\n")
    
    # Passo 1: Iniciar Daemon do PyRO
    print("1. Iniciando Daemon do PyRO...")
    daemon = Pyro5.api.Daemon(host='localhost')
    print(f"   Daemon rodando em {daemon.locationStr}")
    
    # Passo 2: Garantir que o Servidor de Nomes existe
    print("\n2. Conectando ao Servidor de Nomes...")
    ns = iniciar_servidor_nomes()
    
    # Passo 3: Criar e registrar o Peer
    print(f"\n3. Criando e registrando {nome_peer}...")
    peer = Peer(nome_peer)
    uri = daemon.register(peer)
    ns.register(nome_peer, uri)
    print(f"   {nome_peer} registrado com URI: {uri}")
    
    # Aguarda um pouco para outros peers se registrarem
    print("\n4. Aguardando outros peers (5 segundos)...")
    time.sleep(5)
    
    # Passo 4: Descobrir outros peers
    print("\n5. Descobrindo outros peers...")
    peers_encontrados = descobrir_peers(ns, nome_peer)
    
    for nome, proxy in peers_encontrados.items():
        peer.adicionar_peer(nome, proxy)
    
    # Iniciar threads de heartbeat e verificação de falhas
    print("\n6. Iniciando mecanismos de tolerância a falhas...")
    peer.iniciar_heartbeat()
    peer.iniciar_verificacao_falhas()
    
    # Iniciar daemon em thread separada
    print("\n7. Iniciando loop do Daemon...")
    thread_daemon = threading.Thread(target=daemon.requestLoop, daemon=True)
    thread_daemon.start()
    
    print(f"\n✓ {nome_peer} iniciado com sucesso!\n")
    
    # Iniciar interface do usuário
    interface_usuario(peer)
    
    # Cleanup
    ns.remove(nome_peer)
    daemon.shutdown()
    print(f"{nome_peer} encerrado.")

if __name__ == "__main__":
    main()