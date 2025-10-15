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
        
        # --- Contadores de Performance ---
        self.contadores = {
            'heartbeats_enviados': 0,
            'heartbeats_recebidos': 0,
            'verificacoes_heartbeat': 0,
            'descobertas': 0,
            'pedidos_recebidos': 0,
            'respostas_recebidas': 0
        }
        self.lock_contadores = threading.Lock()
        
        print(f"[{timestamp_log()}][{self.nome}] Peer (Controlador) inicializado!")

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
        inicio = time.time()
        with self.logica.lock:
            self.ultimos_heartbeats[nome_peer] = time.time()
            if nome_peer not in self.peers_ativos:
                self.peers_ativos.add(nome_peer)
                print(f"[{timestamp_log()}][{self.nome}] 💚 {nome_peer} está ativo!")
        
        with self.lock_contadores:
            self.contadores['heartbeats_recebidos'] += 1
        
        duracao = (time.time() - inicio) * 1000
        if duracao > 100:  # Log se demorar mais de 100ms
            print(f"[{timestamp_log()}][{self.nome}] ⚠️ receber_heartbeat demorou {duracao:.1f}ms")

    def receber_pedido(self, timestamp_outro, nome_outro):
        inicio = time.time()
        print(f"[{timestamp_log()}][{self.nome}] Recebi pedido de {nome_outro} (ts={timestamp_outro})")
        
        with self.lock_contadores:
            self.contadores['pedidos_recebidos'] += 1

        # Verifica se o peer está ativo ANTES de processar a lógica
        if nome_outro not in self.peers_ativos:
            print(f"[{timestamp_log()}][{self.nome}] Ignorando pedido de {nome_outro} (peer não está ativo)")
            return
        
        decisao = self.logica.receber_pedido(timestamp_outro, nome_outro)
        
        if decisao == "CONCEDER_AGORA":
            delay = random.uniform(config.MIN_DELAY_RESPOSTA, config.MAX_DELAY_RESPOSTA)
            print(f"[{timestamp_log()}][{self.nome}] → Concedendo OK para {nome_outro}")
            time.sleep(delay)

            try:
                proxy = self.obter_proxy(nome_outro)
                proxy.receber_resposta(self.nome)
            except Exception as e:
                print(f"[{timestamp_log()}][{self.nome}] ✗ Erro ao enviar OK para {nome_outro}: {e}")
        else:
            print(f"[{timestamp_log()}][{self.nome}] → Adiando resposta para {nome_outro}")
        
        duracao = (time.time() - inicio) * 1000
        if duracao > 100:
            print(f"[{timestamp_log()}][{self.nome}] ⚠️ receber_pedido demorou {duracao:.1f}ms")

    @Pyro5.api.oneway
    def receber_resposta(self, nome_outro):
        inicio = time.time()
        with self.lock_contadores:
            self.contadores['respostas_recebidas'] += 1
        
        pode_entrar, status = self.logica.receber_resposta(nome_outro)
        
        if status == "TARDIO":
            print(f"[{timestamp_log()}][{self.nome}] Recebi OK tardio de {nome_outro}, mas não estou mais esperando. Ignorando.")
            return

        print(f"[{timestamp_log()}][{self.nome}] ✓ Recebi OK de {nome_outro}")
        if pode_entrar:
            print(f"[{timestamp_log()}][{self.nome}] Recebi OK de TODOS! Liberando para entrar na SC.")
            self.evento_liberado.set()
        
        duracao = (time.time() - inicio) * 1000
        if duracao > 100:
            print(f"[{timestamp_log()}][{self.nome}] ⚠️ receber_resposta demorou {duracao:.1f}ms")

    # --- Métodos Locais (Chamados pelo Usuário) ---

    def solicitar_sc(self):
        self.evento_liberado.clear()
        
        with self.logica.lock:
            peers_para_pedir_nomes = self.peers_ativos.intersection(set(self.peer_uris.keys()))
        
        timestamp, _ = self.logica.iniciar_pedido_sc(peers_para_pedir_nomes)

        if timestamp is None:
            print(f"[{timestamp_log()}][{self.nome}] Erro: já estou em outro estado.")
            return

        print(f"\n[{timestamp_log()}][{self.nome}] {'='*50}")
        print(f"[{timestamp_log()}][{self.nome}] SOLICITANDO ACESSO À SC (timestamp={timestamp})")
        print(f"[{timestamp_log()}][{self.nome}] {'='*50}")

        if not peers_para_pedir_nomes:
            print(f"[{timestamp_log()}][{self.nome}] Nenhum peer ativo detectado! Entrando direto na SC.")
            self.evento_liberado.set()
        else:
            print(f"[{timestamp_log()}][{self.nome}] Enviando pedidos para {len(peers_para_pedir_nomes)} peers ativos...")
            for nome_peer in peers_para_pedir_nomes:
                threading.Thread(target=self._enviar_pedido_com_timeout, args=(nome_peer, timestamp), daemon=True).start()

        sucesso = self.evento_liberado.wait()

        if sucesso:
            self.logica.entrar_sc()
            print(f"\n[{timestamp_log()}][{self.nome}] {'='*50}")
            print(f"[{timestamp_log()}][{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!")
            print(f"[{timestamp_log()}][{self.nome}] {'='*50}\n")
            print(f"[{timestamp_log()}][{self.nome}] ⏳ O recurso será liberado automaticamente em {config.TEMPO_MAXIMO_SC} segundos.")
            self.timer_sc = Timer(config.TEMPO_MAXIMO_SC, self.liberar_sc)
            self.timer_sc.start()
        else:
            self.logica.falhar_pedido()
            print(f"[{timestamp_log()}][{self.nome}] ✗ Falha ao obter acesso à SC (Timeout geral)")

    def liberar_sc(self):
        if self.timer_sc and self.timer_sc.is_alive():
            self.timer_sc.cancel()
            print(f"[{timestamp_log()}][{self.nome}] Liberação manual. Timer de liberação automática cancelado.")

        pedidos_pendentes = self.logica.liberar_sc()

        if not pedidos_pendentes and self.logica.obter_estado()['estado'] != "LIBERADO":
             print(f"[{timestamp_log()}][{self.nome}] Erro: não estou na SC.")
             return
        
        print(f"\n[{timestamp_log()}][{self.nome}] {'='*50}")
        print(f"[{timestamp_log()}][{self.nome}] SAINDO DA SEÇÃO CRÍTICA")
        print(f"[{timestamp_log()}][{self.nome}] {'='*50}")

        for _, nome_peer in pedidos_pendentes:
            try:
                print(f"[{timestamp_log()}][{self.nome}] → Enviando OK adiado para {nome_peer}")
                proxy = self.obter_proxy(nome_peer)
                proxy.receber_resposta(self.nome)
            except Exception as e:
                print(f"[{timestamp_log()}][{self.nome}] Erro ao enviar resposta para {nome_peer}: {e}")
        
        print(f"[{timestamp_log()}][{self.nome}] ✓ Liberado!\n")

    # --- Métodos de Suporte e Threads ---

    def _enviar_pedido_com_timeout(self, nome_peer, timestamp):
        try:
            proxy = self.obter_proxy(nome_peer)
            proxy._pyroTimeout = config.TIMEOUT_PEDIDO_INDIVIDUAL
            proxy.receber_pedido(timestamp, self.nome)
        except Exception as e:
            print(f"[{timestamp_log()}][{self.nome}] Timeout/Erro com {nome_peer}: {e}")
            self._remover_peer_morto(nome_peer)

    def _remover_peer_morto(self, nome_peer):
        with self.logica.lock:
            if nome_peer in self.peers_ativos:
                self.peers_ativos.discard(nome_peer)
                print(f"[{timestamp_log()}][{self.nome}] ❌ {nome_peer} detectado como MORTO (sem heartbeat)")
                
                if self.logica.remover_peer_de_espera(nome_peer):
                    print(f"[{timestamp_log()}][{self.nome}] ✓ Tenho respostas de todos os peers vivos necessários!")
                    self.evento_liberado.set()

    def _descobrir_peers_continuamente(self):
        print(f"[{timestamp_log()}][{self.nome}] Thread de descoberta iniciada!")
        ns_local = Pyro5.api.locate_ns()
        ciclo = 0
        
        while self.rodando:
            inicio_ciclo = time.time()
            ciclo += 1
            
            descobertos = 0
            for outro_peer in config.TODOS_PEERS:
                if outro_peer != self.nome:
                    try:
                        uri_outro = ns_local.lookup(outro_peer)
                        if outro_peer not in self.peer_uris:
                             self.peer_uris[outro_peer] = uri_outro
                             print(f"[{timestamp_log()}][{self.nome}] ✓ Peer '{outro_peer}' conectado!")
                             descobertos += 1
                    except Pyro5.errors.NamingError:
                        if outro_peer in self.peer_uris:
                            del self.peer_uris[outro_peer]
            
            with self.lock_contadores:
                self.contadores['descobertas'] += 1
            
            duracao_ciclo = (time.time() - inicio_ciclo) * 1000
            
            if ciclo % 10 == 0:
                print(f"[{timestamp_log()}][{self.nome}] 🔎 Descoberta ciclo {ciclo}: "
                      f"conectados={len(self.peer_uris)}, novos={descobertos}, "
                      f"tempo={duracao_ciclo:.1f}ms")
            
            time.sleep(3)

    def _enviar_heartbeats(self):
        print(f"[{timestamp_log()}][{self.nome}] Thread de envio de heartbeats iniciada!")
        ciclo = 0
        while self.rodando:
            inicio_ciclo = time.time()
            ciclo += 1
            
            time.sleep(config.INTERVALO_HEARTBEAT)
            
            inicio_envio = time.time()
            peers_para_enviar = list(self.peer_uris.keys())
            
            for nome_peer in peers_para_enviar:
                try:
                    t0 = time.time()
                    proxy = self.obter_proxy(nome_peer)
                    t1 = time.time()
                    proxy._pyroTimeout = 1.0
                    proxy.receber_heartbeat(self.nome)
                    t2 = time.time()
                    print(f"[DEBUG] {nome_peer}: criar_proxy={1000*(t1-t0):.1f}ms, call={1000*(t2-t1):.1f}ms")
                    with self.lock_contadores:
                        self.contadores['heartbeats_enviados'] += 1
                except Exception as e:
                    print(f"[{timestamp_log()}][{self.nome}] ⚠️ Erro ao enviar heartbeat para {nome_peer}: {e}")
            
            duracao_envio = (time.time() - inicio_envio) * 1000
            duracao_ciclo = (time.time() - inicio_ciclo) * 1000
            
            if ciclo % 10 == 0:
                print(f"[{timestamp_log()}][{self.nome}] 🔄 Heartbeat ciclo {ciclo}: "
                      f"envio={duracao_envio:.1f}ms, ciclo_total={duracao_ciclo:.1f}ms, "
                      f"peers={len(peers_para_enviar)}")

    def _verificar_heartbeats(self):
        print(f"[{timestamp_log()}][{self.nome}] Thread de verificação de heartbeats iniciada!")
        ciclo = 0
        while self.rodando:
            inicio_ciclo = time.time()
            ciclo += 1
            
            time.sleep(config.TIMEOUT_HEARTBEAT)
            
            tempo_atual = time.time()
            peers_mortos = []
            
            with self.logica.lock:
                for nome_peer, ultimo_heartbeat in self.ultimos_heartbeats.items():
                    tempo_desde_ultimo = tempo_atual - ultimo_heartbeat
                    if tempo_desde_ultimo > config.TIMEOUT_HEARTBEAT:
                        if nome_peer in self.peers_ativos:
                            peers_mortos.append((nome_peer, tempo_desde_ultimo))
            
            for nome_peer, tempo_desde in peers_mortos:
                print(f"[{timestamp_log()}][{self.nome}] ⚠️ Peer {nome_peer} sem heartbeat há {tempo_desde:.1f}s")
                self._remover_peer_morto(nome_peer)
            
            with self.lock_contadores:
                self.contadores['verificacoes_heartbeat'] += 1
            
            duracao_ciclo = (time.time() - inicio_ciclo) * 1000
            
            if ciclo % 3 == 0:
                with self.lock_contadores:
                    stats = self.contadores.copy()
                print(f"[{timestamp_log()}][{self.nome}] 🔍 Verificação {ciclo}: "
                      f"ativos={len(self.peers_ativos)}, mortos={len(peers_mortos)}, "
                      f"ciclo={duracao_ciclo:.1f}ms")
                print(f"[{timestamp_log()}][{self.nome}] 📊 Stats: "
                      f"HB_enviados={stats['heartbeats_enviados']}, "
                      f"HB_recebidos={stats['heartbeats_recebidos']}, "
                      f"verificações={stats['verificacoes_heartbeat']}")
    
    def obter_proxy(self, nome_peer):
        return Pyro5.api.Proxy(f"PYRONAME:{nome_peer}")

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