"""
Script para executar cenários de teste automatizados
Útil para demonstrações e validações rápidas
"""

import time
import Pyro5.api

def conectar_peer(nome_peer):
    """Conecta a um peer via PyRO"""
    try:
        ns = Pyro5.api.locate_ns()
        uri = ns.lookup(nome_peer)
        proxy = Pyro5.api.Proxy(uri)
        proxy._pyroTimeout = 3.0
        return proxy
    except Exception as e:
        print(f"Erro ao conectar em {nome_peer}: {e}")
        return None

def mostrar_status(peer_proxy, nome):
    """Mostra o status de um peer"""
    try:
        status = peer_proxy.obter_status()
        print(f"\n{'='*60}")
        print(f"STATUS DO {nome}")
        print(f"{'='*60}")
        print(f"Estado: {status['estado']}")
        print(f"Relógio Lógico: {status['relogio']}")
        print(f"Peers Ativos: {', '.join(status['peers_ativos']) if status['peers_ativos'] else 'Nenhum'}")
        print(f"{'='*60}\n")
        return status
    except Exception as e:
        print(f"Erro ao obter status de {nome}: {e}")
        return None

def teste_1_acesso_basico():
    """TESTE 1: Acesso básico sem concorrência"""
    print("\n" + "="*70)
    print("TESTE 1: Acesso Básico à Seção Crítica")
    print("="*70)
    
    peerA = conectar_peer("PeerA")
    if not peerA:
        print("❌ PeerA não encontrado. Certifique-se que todos os peers estão rodando.")
        return
    
    print("\n1. Verificando estado inicial...")
    mostrar_status(peerA, "PeerA")
    
    print("2. Solicitando acesso à SC...")
    peerA.solicitar_sc()
    
    print("\n3. Aguardando 5 segundos...")
    time.sleep(5)
    
    status = mostrar_status(peerA, "PeerA")
    if status and status['estado'] == 'DENTRO_DA_SC':
        print("✅ TESTE 1 PASSOU: PeerA está na SC")
    else:
        print("❌ TESTE 1 FALHOU: PeerA não entrou na SC")
    
    print("\n4. Aguardando liberação automática (15s)...")
    time.sleep(11)  # Já esperou 5s antes
    
    status = mostrar_status(peerA, "PeerA")
    if status and status['estado'] == 'LIBERADO':
        print("✅ TESTE 1 PASSOU: PeerA liberou automaticamente")
    else:
        print("❌ TESTE 1 FALHOU: PeerA não liberou corretamente")

def teste_2_concorrencia_simples():
    """TESTE 2: Concorrência entre 2 peers"""
    print("\n" + "="*70)
    print("TESTE 2: Concorrência Simples (2 Peers)")
    print("="*70)
    
    peerA = conectar_peer("PeerA")
    peerB = conectar_peer("PeerB")
    
    if not peerA or not peerB:
        print("❌ Peers não encontrados")
        return
    
    print("\n1. Estados iniciais:")
    mostrar_status(peerA, "PeerA")
    mostrar_status(peerB, "PeerB")
    
    print("2. Enviando pedidos simultâneos...")
    
    import threading
    
    def solicitar_a():
        peerA.solicitar_sc()
    
    def solicitar_b():
        time.sleep(0.1)  # Pequeno delay para B
        peerB.solicitar_sc()
    
    thread_a = threading.Thread(target=solicitar_a)
    thread_b = threading.Thread(target=solicitar_b)
    
    thread_a.start()
    thread_b.start()
    
    print("\n3. Aguardando 3 segundos...")
    time.sleep(3)
    
    status_a = mostrar_status(peerA, "PeerA")
    status_b = mostrar_status(peerB, "PeerB")
    
    # Verifica exclusão mútua
    if status_a and status_b:
        na_sc = []
        if status_a['estado'] == 'DENTRO_DA_SC':
            na_sc.append('PeerA')
        if status_b['estado'] == 'DENTRO_DA_SC':
            na_sc.append('PeerB')
        
        if len(na_sc) == 1:
            print(f"✅ TESTE 2 PASSOU: Apenas {na_sc[0]} está na SC (exclusão mútua OK)")
        elif len(na_sc) == 0:
            print("⚠️  TESTE 2 PARCIAL: Nenhum peer na SC ainda (pode estar negociando)")
        else:
            print("❌ TESTE 2 FALHOU: Múltiplos peers na SC simultaneamente!")
    
    thread_a.join(timeout=20)
    thread_b.join(timeout=20)

def teste_3_status_geral():
    """TESTE 3: Verifica status de todos os peers"""
    print("\n" + "="*70)
    print("TESTE 3: Status Geral de Todos os Peers")
    print("="*70)
    
    peers_nomes = ["PeerA", "PeerB", "PeerC", "PeerD"]
    peers_ativos = []
    
    for nome in peers_nomes:
        peer = conectar_peer(nome)
        if peer:
            peers_ativos.append(nome)
            mostrar_status(peer, nome)
        else:
            print(f"❌ {nome} não está acessível")
    
    print(f"\n{'='*70}")
    print(f"Resumo: {len(peers_ativos)}/4 peers ativos")
    print(f"Ativos: {', '.join(peers_ativos)}")
    print(f"{'='*70}\n")
    
    if len(peers_ativos) == 4:
        print("✅ TESTE 3 PASSOU: Todos os peers estão ativos")
    else:
        print(f"⚠️  TESTE 3 PARCIAL: Apenas {len(peers_ativos)} peers ativos")

def teste_4_deteccao_falha():
    """TESTE 4: Simula verificação de peers falhos"""
    print("\n" + "="*70)
    print("TESTE 4: Detecção de Falhas")
    print("="*70)
    print("\nPara este teste:")
    print("1. Deixe este script rodando")
    print("2. Mate um dos peers (ex: PeerD)")
    print("3. Aguarde ~7 segundos")
    print("4. Observe os logs dos outros peers detectando a falha")
    print("\nPressione Ctrl+C quando terminar o teste...")
    
    try:
        tempo = 0
        while tempo < 60:
            time.sleep(5)
            tempo += 5
            print(f"\n[{tempo}s] Verificando peers...")
            teste_3_status_geral()
    except KeyboardInterrupt:
        print("\nTeste interrompido pelo usuário")

def menu():
    """Menu principal de testes"""
    print("\n" + "="*70)
    print("SISTEMA DE TESTES AUTOMATIZADOS")
    print("Algoritmo de Ricart e Agrawala")
    print("="*70)
    print("\nCertifique-se que todos os peers estão rodando antes de iniciar!")
    print("Execute: python start_all.py")
    print("\nEscolha um teste:")
    print("1. Teste 1 - Acesso Básico (sem concorrência)")
    print("2. Teste 2 - Concorrência Simples (2 peers)")
    print("3. Teste 3 - Status Geral (verificar conectividade)")
    print("4. Teste 4 - Detecção de Falhas (manual)")
    print("5. Executar TODOS os testes automatizados")
    print("0. Sair")
    print("="*70)
    
    escolha = input("\nDigite o número do teste: ").strip()
    
    if escolha == "1":
        teste_1_acesso_basico()
    elif escolha == "2":
        teste_2_concorrencia_simples()
    elif escolha == "3":
        teste_3_status_geral()
    elif escolha == "4":
        teste_4_deteccao_falha()
    elif escolha == "5":
        print("\nExecutando todos os testes...\n")
        teste_3_status_geral()
        time.sleep(2)
        teste_1_acesso_basico()
        time.sleep(2)
        teste_2_concorrencia_simples()
        print("\n✅ Todos os testes automatizados concluídos!")
    elif escolha == "0":
        print("Saindo...")
        return False
    else:
        print("Opção inválida!")
    
    return True

def main():
    """Função principal"""
    try:
        while True:
            continuar = menu()
            if not continuar:
                break
            
            input("\nPressione ENTER para voltar ao menu...")
    except KeyboardInterrupt:
        print("\n\nEncerrando testes...")
    except Exception as e:
        print(f"\nErro: {e}")

if __name__ == "__main__":
    main()