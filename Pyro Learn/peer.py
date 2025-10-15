# Arquivo: peer.py

import Pyro5.api
import threading
import time
from threading import Timer
import random
from datetime import datetime

# Importações dos novos arquivos
from logic import RicartAgrawalaLogic
import config


def timestamp_log():
    """Retorna timestamp formatado para logs"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


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
                print(f"[{timestamp_log()}][{self.nome}] Peer '{nome_peer}' conectado")

    def receber_pedido(self, timestamp_outro, nome_outro):
        # Verifica se o peer está ativo ANTES de processar a lógica
        if nome_outro not in self.peers_ativos:
            return
        
        decisao = self.logica.receber_pedido(timestamp_outro, nome_outro)
        
        if decisao == "CONCEDER_AGORA":
            delay = random.uniform(config.MIN_DELAY_RESPOSTA, config.MAX_DELAY_RESPOSTA)
            print(f"[{timestamp_log()}][{self.nome}] Concedendo OK para {nome_outro} (ts={timestamp_outro})")
            time.sleep(delay)

            try:
                proxy = self.obter_proxy(nome_outro)
                proxy.receber_resposta(self.nome)
            except Exception as e:
                print(f"[{timestamp_log()}][{self.nome}] ERRO ao enviar OK para {nome_outro}: {e}")
        else:
            print(f"[{timestamp_log()}][{self.nome}] Adiando resposta para {nome_outro} (ts={timestamp_outro})")

    @Pyro5.api.oneway
    def receber_resposta(self, nome_outro):
        pode_entrar, status = self.logica.receber_resposta(nome_outro)
        
        if status == "TARDIO":
            return

        print(f"[{timestamp_log()}][{self.nome}] Recebi OK de {nome_outro}")
        if pode_entrar:
            print(f"[{timestamp_log()}][{self.nome}] Recebi OK de TODOS os peers necessarios!")
            self.evento_liberado.set()

    # --- Métodos Locais (Chamados pelo Usuário) ---

    def solicitar_sc(self):
        self.evento_liberado.clear()
        
        with self.logica.lock:
            peers_para_pedir_nomes = self.peers_ativos.intersection(set(self.peer_uris.keys()))
        
        timestamp, _ = self.logica.iniciar_pedido_sc(peers_para_pedir_nomes)

        if timestamp is None:
            print(f"[{timestamp_log()}][{self.nome}] ERRO: ja estou em outro estado")
            return

        print(f"\n[{timestamp_log()}][{self.nome}] {'='*60}")
        print(f"[{timestamp_log()}][{self.nome}] SOLICITANDO SECAO CRITICA (timestamp={timestamp})")
        print(f"[{timestamp_log()}][{self.nome}] Peers ativos: {list(peers_para_pedir_nomes)}")
        print(f"[{timestamp_log()}][{self.nome}] {'='*60}")

        if not peers_para_pedir_nomes:
            print(f"[{timestamp_log()}][{self.nome}] Nenhum peer ativo. Entrando direto na SC")
            self.evento_liberado.set()
        else:
            for nome_peer in peers_para_pedir_nomes:
                threading.Thread(target=self._enviar_pedido_com_timeout, args=(nome_peer, timestamp), daemon=True).start()

        sucesso = self.evento_liberado.wait()

        if sucesso:
            self.logica.entrar_sc()
            print(f"\n[{timestamp_log()}][{self.nome}] {'='*60}")
            print(f"[{timestamp_log()}][{self.nome}] >>> ENTRANDO NA SECAO CRITICA <<<")
            print(f"[{timestamp_log()}][{self.nome}] {'='*60}\n")
            self.timer_sc = Timer(config.TEMPO_MAXIMO_SC, self.liberar_sc)
            self.timer_sc.start()
        else:
            self.logica.falhar_pedido()
            print(f"[{timestamp_log()}][{self.nome}] ERRO: Falha ao obter acesso a SC")

    def liberar_sc(self):
        if self.timer_sc and self.timer_sc.is_alive():
            self.timer_sc.cancel()

        pedidos_pendentes = self.logica.liberar_sc()

        if not pedidos_pendentes and self.logica.obter_estado()['estado'] != "LIBERADO":
             print(f"[{timestamp_log()}][{self.nome}] ERRO: nao estou na SC")
             return
        
        print(f"\n[{timestamp_log()}][{self.nome}] {'='*60}")
        print(f"[{timestamp_log()}][{self.nome}] <<< SAINDO DA SECAO CRITICA >>>")
        print(f"[{timestamp_log()}][{self.nome}] {'='*60}")

        if pedidos_pendentes:
            print(f"[{timestamp_log()}][{self.nome}] Enviando {len(pedidos_pendentes)} respostas adiadas...")
        
        for _, nome_peer in pedidos_pendentes:
            try:
                print(f"[{timestamp_log()}][{self.nome}] Enviando OK adiado para {nome_peer}")
                proxy = self.obter_proxy(nome_peer)
                proxy.receber_resposta(self.nome)
            except Exception as e:
                print(f"[{timestamp_log()}][{self.nome}] ERRO ao enviar resposta para {nome_peer}: {e}")
        
        print(f"[{timestamp_log()}][{self.nome}] SC liberada!\n")

    # --- Métodos de Suporte e Threads ---

    def _enviar_pedido_com_timeout(self, nome_peer, timestamp):
        try:
            proxy = self.obter_proxy(nome_peer)
            proxy._pyroTimeout = config.TIMEOUT_PEDIDO_INDIVIDUAL
            proxy.receber_pedido(timestamp, self.nome)
        except Exception as e:
            print(f"[{timestamp_log()}][{self.nome}] Timeout com {nome_peer}: {e}")
            self._remover_peer_morto(nome_peer)

    def _remover_peer_morto(self, nome_peer):
        with self.logica.lock:
            if nome_peer in self.peers_ativos:
                self.peers_ativos.discard(nome_peer)
                print(f"[{timestamp_log()}][{self.nome}] Peer '{nome_peer}' detectado como MORTO")
                
                if self.logica.remover_peer_de_espera(nome_peer):
                    print(f"[{timestamp_log()}][{self.nome}] Tenho respostas suficientes dos peers vivos!")
                    self.evento_liberado.set()

    def _descobrir_peers_continuamente(self):
        ns_local = Pyro5.api.locate_ns()
        
        while self.rodando:
            for outro_peer in config.TODOS_PEERS:
                if outro_peer != self.nome:
                    try:
                        uri_outro = ns_local.lookup(outro_peer)
                        if outro_peer not in self.peer_uris:
                             self.peer_uris[outro_peer] = uri_outro
                             print(f"[{timestamp_log()}][{self.nome}] Peer '{outro_peer}' descoberto")
                    except Pyro5.errors.NamingError:
                        if outro_peer in self.peer_uris:
                            del self.peer_uris[outro_peer]
            
            time.sleep(3)

    def _enviar_heartbeats(self):
        while self.rodando:
            time.sleep(config.INTERVALO_HEARTBEAT)
            
            peers_para_enviar = list(self.peer_uris.keys())
            
            for nome_peer in peers_para_enviar:
                try:
                    proxy = self.obter_proxy(nome_peer)
                    proxy._pyroTimeout = 1.0
                    proxy.receber_heartbeat(self.nome)
                except Exception:
                    pass  # Silencioso - a verificação de heartbeat vai detectar

    def _verificar_heartbeats(self):
        while self.rodando:
            time.sleep(config.TIMEOUT_HEARTBEAT)
            
            tempo_atual = time.time()
            peers_mortos = []
            
            with self.logica.lock:
                for nome_peer, ultimo_heartbeat in self.ultimos_heartbeats.items():
                    tempo_desde_ultimo = tempo_atual - ultimo_heartbeat
                    if tempo_desde_ultimo > config.TIMEOUT_HEARTBEAT:
                        if nome_peer in self.peers_ativos:
                            peers_mortos.append(nome_peer)
            
            for nome_peer in peers_mortos:
                self._remover_peer_morto(nome_peer)
    
    def obter_proxy(self, nome_peer):
        if nome_peer not in self.peer_uris:
            return None
        proxy = Pyro5.api.Proxy(self.peer_uris[nome_peer])
        proxy._pyroTimeout = 2.0
        return proxy

    def parar(self):
        self.rodando = False
        if self.timer_sc:
            self.timer_sc.cancel()

    def obter_estado_completo(self):
        estado_logica = self.logica.obter_estado()
        estado_logica['peers_ativos'] = list(self.peers_ativos)
        estado_logica['peers_conhecidos'] = len(self.peer_uris)
        estado_logica['nome'] = self.nome
        return estado_logica