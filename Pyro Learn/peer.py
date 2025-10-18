# peer.py - Implementação Completa do Peer (Sem UDP)

import Pyro5.api
import threading
import time
from threading import Timer
from datetime import datetime
<<<<<<< HEAD
=======

# Importações dos novos arquivos
from logic import RicartAgrawalaLogic
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
import config

def log():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

<<<<<<< HEAD
=======

>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
@Pyro5.api.expose
class Peer:
    def __init__(self, nome):
        self.nome = nome
        self.lock = threading.RLock()
        
        # Estado do algoritmo
        self.estado = "LIBERADO"
        self.relogio = 0
        self.timestamp_pedido = None
        self.fila_adiados = []
        self.respostas = set()
        self.peers_necessarios = set()
        
        # Rede
        self.peer_uris = {}
        self.ns = None
        self.evento_pronto = threading.Event()
        self.timer_sc = None
        
        # Heartbeats
        self.ultimos_hb = {}
        self.peers_ativos = set()
        self.rodando = True
<<<<<<< HEAD
        
        print(f"[{log()}][{self.nome}] Peer iniciado")
=======
        self.thread_descoberta = None
        self.thread_heartbeat_envio = None
        self.thread_heartbeat_verificacao = None
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5

    def configurar(self, ns):
        self.ns = ns
<<<<<<< HEAD
        threading.Thread(target=self._descobrir, daemon=True).start()
        threading.Thread(target=self._enviar_hb, daemon=True).start()
        threading.Thread(target=self._verificar_hb, daemon=True).start()
=======
        self.thread_descoberta = threading.Thread(target=self._descobrir_peers_continuamente, daemon=True)
        self.thread_descoberta.start()
        self.thread_heartbeat_envio = threading.Thread(target=self._enviar_heartbeats, daemon=True)
        self.thread_heartbeat_envio.start()
        self.thread_heartbeat_verificacao = threading.Thread(target=self._verificar_heartbeats, daemon=True)
        self.thread_heartbeat_verificacao.start()
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5

    # === Métodos Remotos ===
    
<<<<<<< HEAD
    def receber_pedido(self, ts_outro, nome_outro):
        with self.lock:
            self.relogio = max(self.relogio, ts_outro) + 1
            
            if nome_outro not in self.peers_ativos:
                return
            
            # Concede se estou livre OU se meu pedido tem prioridade menor
            conceder = (self.estado == "LIBERADO" or 
                       (self.estado == "QUERENDO" and 
                        (ts_outro, nome_outro) < (self.timestamp_pedido, self.nome)))
            
            if conceder:
                print(f"[{log()}][{self.nome}] → OK para {nome_outro}")
                threading.Thread(target=self._enviar_ok, args=(nome_outro,), daemon=True).start()
            else:
                print(f"[{log()}][{self.nome}] ⏸ Adiando {nome_outro}")
                self.fila_adiados.append((ts_outro, nome_outro))

    @Pyro5.api.oneway
    def receber_resposta(self, nome_outro):
        with self.lock:
            if self.estado != "QUERENDO":
                return
            
            self.respostas.add(nome_outro)
            print(f"[{log()}][{self.nome}] ✓ OK de {nome_outro} ({len(self.respostas)}/{len(self.peers_necessarios)})")
            
            if self.respostas >= self.peers_necessarios:
                print(f"[{log()}][{self.nome}] ✓ Tenho todos os OKs!")
                self.evento_pronto.set()

    @Pyro5.api.oneway
    def receber_heartbeat(self, nome_outro):
        with self.lock:
            self.ultimos_hb[nome_outro] = time.time()
            if nome_outro not in self.peers_ativos:
                self.peers_ativos.add(nome_outro)
                print(f"[{log()}][{self.nome}] 💚 {nome_outro} ativo!")
=======
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
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5

    # === Métodos Locais ===
    
    def solicitar_sc(self):
        self.evento_pronto.clear()
        
        with self.lock:
            if self.estado != "LIBERADO":
                print(f"[{log()}][{self.nome}] Erro: já estou {self.estado}")
                return
            
            self.estado = "QUERENDO"
            self.relogio += 1
            self.timestamp_pedido = self.relogio
            self.respostas.clear()
            self.peers_necessarios = self.peers_ativos.copy()
            
            ts = self.timestamp_pedido
            peers = list(self.peers_necessarios)
        
<<<<<<< HEAD
        print(f"[{log()}][{self.nome}] {'='*50}")
        print(f"[{log()}][{self.nome}] SOLICITANDO SC (ts={ts})")
        print(f"[{log()}][{self.nome}] {'='*50}")
        
        if not peers:
            print(f"[{log()}][{self.nome}] Sem peers ativos, entrando direto")
            self.evento_pronto.set()
        else:
            print(f"[{log()}][{self.nome}] Pedindo para {len(peers)} peers...")
            for p in peers:
                threading.Thread(target=self._pedir_para, args=(p, ts), daemon=True).start()
        
        if self.evento_pronto.wait():
            with self.lock:
                self.estado = "NA_SC"
            
            print(f"[{log()}][{self.nome}] {'='*50}")
            print(f"[{log()}][{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!")
            print(f"[{log()}][{self.nome}] {'='*50}")
            
            self.timer_sc = Timer(config.TEMPO_MAXIMO_SC, self.liberar_sc)
            self.timer_sc.start()
=======
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
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5

    def liberar_sc(self):
        if self.timer_sc:
            self.timer_sc.cancel()
<<<<<<< HEAD
        
        with self.lock:
            if self.estado != "NA_SC":
                print(f"[{log()}][{self.nome}] Não estou na SC")
                return
            
            self.estado = "LIBERADO"
            self.timestamp_pedido = None
            adiados = self.fila_adiados.copy()
            self.fila_adiados.clear()
        
        print(f"[{log()}][{self.nome}] {'='*50}")
        print(f"[{log()}][{self.nome}] SAINDO DA SC")
        print(f"[{log()}][{self.nome}] {'='*50}")
        
        for _, nome in adiados:
            threading.Thread(target=self._enviar_ok, args=(nome,), daemon=True).start()

    # === Métodos Auxiliares ===
    
    def _pedir_para(self, nome, ts):
        try:
            uri = self.peer_uris.get(nome)
            if not uri:
                print(f"[{log()}][{self.nome}] ✗ URI não encontrada para {nome}")
                return
            
            proxy = Pyro5.api.Proxy(uri)
            proxy._pyroTimeout = config.TIMEOUT_PEDIDO
            proxy.receber_pedido(ts, self.nome)
        except Exception as e:
            print(f"[{log()}][{self.nome}] ✗ Erro com {nome}: {e}")
            self._marcar_morto(nome)

    def _enviar_ok(self, nome):
        try:
            uri = self.peer_uris.get(nome)
            if not uri:
                return
            
            proxy = Pyro5.api.Proxy(uri)
            proxy._pyroTimeout = 1.0
            proxy.receber_resposta(self.nome)
        except Exception as e:
            print(f"[{log()}][{self.nome}] ✗ Erro enviando OK para {nome}: {e}")

    def _marcar_morto(self, nome):
        with self.lock:
            if nome in self.peers_ativos:
                self.peers_ativos.discard(nome)
                print(f"[{log()}][{self.nome}] ⌫ {nome} MORTO")
                
                if nome in self.peers_necessarios:
                    self.peers_necessarios.discard(nome)
                    if self.estado == "QUERENDO" and self.respostas >= self.peers_necessarios:
                        print(f"[{log()}][{self.nome}] ✓ Tenho todos os OKs dos peers vivos!")
                        self.evento_pronto.set()

    # === Threads de Background ===
    
    def _descobrir(self):
        print(f"[{log()}][{self.nome}] Thread de descoberta iniciada")
        # Cria proxy do nameserver nesta thread
        ns_local = Pyro5.api.locate_ns(host="127.0.0.1")
        
        while self.rodando:
            try:
                # Lista todos os peers registrados no nameserver
                registrados = ns_local.list()
                
                for outro in config.TODOS_PEERS:
                    if outro != self.nome:
                        if outro in registrados:
                            # Peer está registrado
                            if outro not in self.peer_uris:
                                try:
                                    uri = ns_local.lookup(outro)
                                    self.peer_uris[outro] = str(uri)
                                    print(f"[{log()}][{self.nome}] ✓ Descoberto: {outro}")
                                except Exception as e:
                                    print(f"[{log()}][{self.nome}] Erro ao conectar {outro}: {e}")
                        else:
                            # Peer não está mais registrado
                            if outro in self.peer_uris:
                                del self.peer_uris[outro]
                                print(f"[{log()}][{self.nome}] ✗ Perdido: {outro}")
                
            except Exception as e:
                print(f"[{log()}][{self.nome}] Erro na descoberta: {e}")
            
            time.sleep(3)

    def _enviar_hb(self):
        print(f"[{log()}][{self.nome}] Thread de heartbeat iniciada")
        while self.rodando:
            time.sleep(config.INTERVALO_HEARTBEAT)
            
            peers_conhecidos = list(self.peer_uris.keys())
            if peers_conhecidos:
                for nome in peers_conhecidos:
                    try:
                        uri = self.peer_uris.get(nome)
                        if uri:
                            proxy = Pyro5.api.Proxy(uri)
                            proxy._pyroTimeout = 1.0
                            proxy.receber_heartbeat(self.nome)
                    except:
                        pass

    def _verificar_hb(self):
        print(f"[{log()}][{self.nome}] Thread de verificação iniciada")
        while self.rodando:
=======

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
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
            time.sleep(config.TIMEOUT_HEARTBEAT)
            tempo_atual = time.time()
            
<<<<<<< HEAD
            with self.lock:
                mortos = [nome for nome, ultimo in self.ultimos_hb.items()
                         if tempo_atual - ultimo > config.TIMEOUT_HEARTBEAT 
                         and nome in self.peers_ativos]
            
            for nome in mortos:
                self._marcar_morto(nome)

    # === Métodos de Interface ===
    
    def status(self):
        with self.lock:
            print(f"\n--- {self.nome} ---")
            print(f"  Estado: {self.estado}")
            print(f"  Relógio: {self.relogio}")
            print(f"  Timestamp: {self.timestamp_pedido}")
            print(f"  Peers Ativos: {list(self.peers_ativos)}")
            print(f"  Respostas: {len(self.respostas)}/{len(self.peers_necessarios)}\n")
=======
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
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5

    def parar(self):
        self.rodando = False
        if self.timer_sc:
<<<<<<< HEAD
            self.timer_sc.cancel()
=======
            self.timer_sc.cancel()

    def obter_estado_completo(self):
        estado_logica = self.logica.obter_estado()
        estado_logica['peers_ativos'] = list(self.peers_ativos)
        estado_logica['peers_conhecidos'] = len(self.peer_uris)
        estado_logica['nome'] = self.nome
        return estado_logica
>>>>>>> 55de030dbda72fdf17cddbecf8f10de25e0119b5
