# Arquivo: peer.py

import Pyro5.api
import threading
import time
from threading import Timer

# Importações dos novos arquivos
from logic import RicartAgrawalaLogic
import config

@Pyro5.api.expose
class Peer:
    """
    Controlador: Gerencia a comunicação de rede (PyRO), threads e a interface,
    delegando a lógica do algoritmo para a classe RicartAgrawalaLogic.
    """
    def __init__(self, nome):
        self.nome = nome
        self.logica = RicartAgrawalaLogic(nome)
        
        # --- Atributos de Rede e Sincronização ---
        self.peer_uris = {}
        self.ns = None
        self.evento_liberado = threading.Event()
        self.timer_sc = None
        
        # --- Atributos de Detecção de Falhas ---
        self.ultimos_heartbeats = {}
        self.peers_ativos = set()
        
        # --- Atributos de Controle de Threads ---
        self.rodando = True
        self.thread_descoberta = None
        self.thread_heartbeat_envio = None
        self.thread_heartbeat_verificacao = None
        
        print(f"[{self.nome}] Peer (Controlador) inicializado!")

    def configurar_descoberta(self, ns):
        self.ns = ns
        self.thread_descoberta = threading.Thread(target=self._descobrir_peers_continuamente, daemon=True)
        self.thread_descoberta.start()
        self.thread_heartbeat_envio = threading.Thread(target=self._enviar_heartbeats, daemon=True)
        self.thread_heartbeat_envio.start()
        self.thread_heartbeat_verificacao = threading.Thread(target=self._verificar_heartbeats, daemon=True)
        self.thread_heartbeat_verificacao.start()

    # --- Métodos Remotos (Expostos via PyRO) ---
    
    @Pyro5.api.oneway
    def receber_heartbeat(self, nome_peer):
        with self.logica.lock:
            self.ultimos_heartbeats[nome_peer] = time.time()
            if nome_peer not in self.peers_ativos:
                self.peers_ativos.add(nome_peer)
                print(f"[{self.nome}] 💚 {nome_peer} está ativo!")

    def receber_pedido(self, timestamp_outro, nome_outro):
        print(f"[{self.nome}] Recebi pedido de {nome_outro} (ts={timestamp_outro})")
        
        # Verifica se o peer está ativo ANTES de processar a lógica
        if nome_outro not in self.peers_ativos:
            print(f"[{self.nome}] Ignorando pedido de {nome_outro} (peer não está ativo)")
            return
        
        decisao = self.logica.receber_pedido(timestamp_outro, nome_outro)
        
        if decisao == "CONCEDER_AGORA":
            print(f"[{self.nome}] → Concedendo OK para {nome_outro}")
            try:
                proxy = self.obter_proxy(nome_outro)
                proxy.receber_resposta(self.nome)
            except Exception as e:
                print(f"[{self.nome}] ✗ Erro ao enviar OK para {nome_outro}: {e}")
        else: # ADIAR
            print(f"[{self.nome}] → Adiando resposta para {nome_outro}")

    def receber_resposta(self, nome_outro):
        pode_entrar, status = self.logica.receber_resposta(nome_outro)
        
        if status == "TARDIO":
            print(f"[{self.nome}] Recebi OK tardio de {nome_outro}, mas não estou mais esperando. Ignorando.")
            return

        print(f"[{self.nome}] ✓ Recebi OK de {nome_outro}")
        if pode_entrar:
            print(f"[{self.nome}]Recebi OK de TODOS! Liberando para entrar na SC.")
            self.evento_liberado.set()

    # --- Métodos Locais (Chamados pelo Usuário) ---

    def solicitar_sc(self):
        self.evento_liberado.clear()
        
        # Adicionado lock para leitura segura de peers_ativos >>>
        with self.logica.lock:
            # Obtém os peers ativos no momento do pedido de forma segura
            peers_para_pedir_nomes = self.peers_ativos.intersection(set(self.peer_uris.keys()))
        
        timestamp, _ = self.logica.iniciar_pedido_sc(peers_para_pedir_nomes)

        if timestamp is None:
            print(f"[{self.nome}] Erro: já estou em outro estado.")
            return

        print(f"\n[{self.nome}] {'='*50}\n[{self.nome}] SOLICITANDO ACESSO À SC (timestamp={timestamp})\n[{self.nome}] {'='*50}")

        if not peers_para_pedir_nomes:
            print(f"[{self.nome}]  Nenhum peer ativo detectado! Entrando direto na SC.")
            self.evento_liberado.set()
        else:
            print(f"[{self.nome}] Enviando pedidos para {len(peers_para_pedir_nomes)} peers ativos...")
            for nome_peer in peers_para_pedir_nomes:
                threading.Thread(target=self._enviar_pedido_com_timeout, args=(nome_peer, timestamp), daemon=True).start()

        sucesso = self.evento_liberado.wait(timeout=config.TIMEOUT_GERAL_PEDIDO)

        if sucesso:
            self.logica.entrar_sc()
            print(f"\n[{self.nome}] {'='*50}\n[{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!\n[{self.nome}] {'='*50}\n")
            print(f"[{self.nome}] ⏳ O recurso será liberado automaticamente em {config.TEMPO_MAXIMO_SC} segundos.")
            self.timer_sc = Timer(config.TEMPO_MAXIMO_SC, self.liberar_sc)
            self.timer_sc.start()
        else:
            self.logica.falhar_pedido()
            print(f"[{self.nome}] ✗ Falha ao obter acesso à SC (Timeout geral)")

    def liberar_sc(self):
        if self.timer_sc and self.timer_sc.is_alive():
            self.timer_sc.cancel()
            print(f"[{self.nome}] Liberação manual. Timer de liberação automática cancelado.")

        pedidos_pendentes = self.logica.liberar_sc()

        if not pedidos_pendentes and self.logica.obter_estado()['estado'] != "LIBERADO":
             print(f"[{self.nome}] Erro: não estou na SC.")
             return
        
        print(f"\n[{self.nome}] {'='*50}\n[{self.nome}] SAINDO DA SEÇÃO CRÍTICA\n[{self.nome}] {'='*50}")

        for _, nome_peer in pedidos_pendentes:
            try:
                print(f"[{self.nome}] → Enviando OK adiado para {nome_peer}")
                proxy = self.obter_proxy(nome_peer)
                proxy.receber_resposta(self.nome)
            except Exception as e:
                print(f"[{self.nome}] Erro ao enviar resposta para {nome_peer}: {e}")
        
        print(f"[{self.nome}] ✓ Liberado!\n")

    # --- Métodos de Suporte e Threads ---

    def _enviar_pedido_com_timeout(self, nome_peer, timestamp):
        try:
            proxy = self.obter_proxy(nome_peer)
            proxy._pyroTimeout = config.TIMEOUT_PEDIDO_INDIVIDUAL
            proxy.receber_pedido(timestamp, self.nome)
        except Exception as e:
            print(f"[{self.nome}] Timeout/Erro com {nome_peer}: {e}")
            self._remover_peer_morto(nome_peer)

    def _remover_peer_morto(self, nome_peer):
        with self.logica.lock:
            if nome_peer in self.peers_ativos:
                self.peers_ativos.discard(nome_peer)
                print(f"[{self.nome}] {nome_peer} detectado como MORTO (sem heartbeat)")
                
                # Delega para a lógica a remoção do peer da lista de espera
                if self.logica.remover_peer_de_espera(nome_peer):
                    print(f"[{self.nome}] ✓ Tenho respostas de todos os peers vivos necessários!")
                    self.evento_liberado.set()

    def _descobrir_peers_continuamente(self):
        print(f"[{self.nome}] Thread de descoberta iniciada!")
        ns_local = Pyro5.api.locate_ns()
        while self.rodando:
            for outro_peer in config.TODOS_PEERS:
                if outro_peer != self.nome:
                    try:
                        uri_outro = ns_local.lookup(outro_peer)
                        if outro_peer not in self.peer_uris:
                             self.peer_uris[outro_peer] = uri_outro
                             print(f"[{self.nome}] ✓ Peer '{outro_peer}' conectado!")
                    except Pyro5.errors.NamingError:
                        if outro_peer in self.peer_uris:
                            del self.peer_uris[outro_peer]
            time.sleep(3)

    def _enviar_heartbeats(self):
        print(f"[{self.nome}] Thread de envio de heartbeats iniciada!")
        while self.rodando:
            time.sleep(config.INTERVALO_HEARTBEAT)
            for nome_peer in list(self.peer_uris.keys()):
                try:
                    proxy = self.obter_proxy(nome_peer)
                    proxy.receber_heartbeat(self.nome)
                except Exception:
                    pass

    def _verificar_heartbeats(self):
        print(f"[{self.nome}] Thread de verificação de heartbeats iniciada!")
        while self.rodando:
            time.sleep(config.TIMEOUT_HEARTBEAT)
            tempo_atual = time.time()
            peers_mortos = []
            with self.logica.lock:
                for nome_peer, ultimo_heartbeat in self.ultimos_heartbeats.items():
                    if (tempo_atual - ultimo_heartbeat) > config.TIMEOUT_HEARTBEAT:
                        if nome_peer in self.peers_ativos:
                            peers_mortos.append(nome_peer)
            for nome_peer in peers_mortos:
                self._remover_peer_morto(nome_peer)
    
    def obter_proxy(self, nome_peer):
        return Pyro5.api.Proxy(f"PYRONAME:{nome_peer}")

    def parar(self):
        self.rodando = False
        if self.timer_sc: self.timer_sc.cancel()

    def obter_estado_completo(self):
        estado_logica = self.logica.obter_estado()
        estado_logica['peers_ativos'] = list(self.peers_ativos)
        estado_logica['peers_conhecidos'] = len(self.peer_uris)
        estado_logica['nome'] = self.nome
        return estado_logica