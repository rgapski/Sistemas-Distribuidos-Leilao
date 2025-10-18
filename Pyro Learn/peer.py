# peer.py - Implementação Completa do Peer (Sem UDP)

import Pyro5.api
import threading
import time
from threading import Timer
from datetime import datetime
import config

def log():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

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
        
        print(f"[{log()}][{self.nome}] Peer iniciado")

    def configurar(self, ns):
        self.ns = ns
        threading.Thread(target=self._descobrir, daemon=True).start()
        threading.Thread(target=self._enviar_hb, daemon=True).start()
        threading.Thread(target=self._verificar_hb, daemon=True).start()

    # === Métodos Remotos ===
    
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

    def liberar_sc(self):
        if self.timer_sc:
            self.timer_sc.cancel()
        
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
            time.sleep(config.TIMEOUT_HEARTBEAT)
            tempo_atual = time.time()
            
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

    def parar(self):
        self.rodando = False
        if self.timer_sc:
            self.timer_sc.cancel()