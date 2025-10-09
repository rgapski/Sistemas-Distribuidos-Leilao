import Pyro5.api
import threading
import time
from threading import Timer # Importado para o timeout da SC

# Estados possíveis do peer
LIBERADO = "LIBERADO"
QUERENDO_ENTRAR = "QUERENDO_ENTRAR"
DENTRO_DA_SC = "DENTRO_DA_SC"

@Pyro5.api.expose
class Peer:
    """
    Classe que representa um processo (peer) no sistema distribuído.
    """
    
    def __init__(self, nome):
        """
        Inicializa um peer com seu nome único.
        
        Args:
            nome (str): Nome do peer (ex: "PeerA", "PeerB")
        """
        self.nome = nome
        self.peer_uris = {}  # Dicionário para guardar URIs dos outros peers
        self.ns = None  # Referência ao servidor de nomes
        self.todos_peers = []  # Lista de todos os peers do sistema
        self.thread_descoberta = None  # Thread de descoberta contínua
        self.rodando = True  # Flag para controlar threads
        
        # === ATRIBUTOS PARA EXCLUSÃO MÚTUA ===
        self.estado = LIBERADO  # Estado atual do peer
        self.relogio_logico = 0  # Relógio lógico de Lamport
        self.meu_timestamp = None  # Timestamp do meu pedido atual
        self.fila_pedidos = []  # Pedidos pendentes: [(timestamp, nome_peer), ...]
        self.respostas_recebidas = set()  # Conjunto de peers que responderam OK
        self.peers_necessarios = set()  # Conjunto de peers dos quais esperamos resposta
        self.lock = threading.Lock()  # Lock para proteger acesso concorrente
        self.evento_liberado = threading.Event()  # Para sincronização de threads
        
        # === ATRIBUTOS PARA DETECÇÃO DE FALHAS ===
        self.ultimos_heartbeats = {}  # {nome_peer: timestamp_ultimo_heartbeat}
        self.peers_ativos = set()  # Conjunto de peers considerados ativos
        self.thread_heartbeat_envio = None  # Thread que envia heartbeats
        self.thread_heartbeat_verificacao = None  # Thread que verifica heartbeats
        self.INTERVALO_HEARTBEAT = 2  # Envia heartbeat a cada 2 segundos
        self.TIMEOUT_HEARTBEAT = 6  # Considera morto após 6 segundos sem heartbeat
        self.TEMPO_MAXIMO_SC = 10  # Tempo em segundos
        self.timer_sc = None       # Objeto do temporizador
        
        print(f"[{self.nome}] Peer inicializado!")
    
    def configurar_descoberta(self, ns, todos_peers):
        self.ns = ns
        self.todos_peers = todos_peers
        self.thread_descoberta = threading.Thread(target=self._descobrir_peers_continuamente, daemon=True)
        self.thread_descoberta.start()
        self.thread_heartbeat_envio = threading.Thread(target=self._enviar_heartbeats, daemon=True)
        self.thread_heartbeat_envio.start()
        self.thread_heartbeat_verificacao = threading.Thread(target=self._verificar_heartbeats, daemon=True)
        self.thread_heartbeat_verificacao.start()
    
    def _descobrir_peers_continuamente(self):
        print(f"[{self.nome}] Thread de descoberta iniciada!")
        ns_local = Pyro5.api.locate_ns()
        while self.rodando:
            novos_encontrados = []
            uris_atualizadas = []
            for outro_peer in self.todos_peers:
                if outro_peer != self.nome:
                    try:
                        uri_outro = ns_local.lookup(outro_peer)
                        if outro_peer not in self.peer_uris:
                            self.registrar_peer(outro_peer, uri_outro)
                            novos_encontrados.append(outro_peer)
                        elif self.peer_uris[outro_peer] != uri_outro:
                            with self.lock:
                                self.peer_uris[outro_peer] = uri_outro
                            uris_atualizadas.append(outro_peer)
                            print(f"[{self.nome}] 🔄 URI de {outro_peer} atualizada (peer reiniciou)")
                    except:
                        pass
            if novos_encontrados:
                print(f"[{self.nome}] Novos peers descobertos: {novos_encontrados}")
            time.sleep(3)
    
    def _enviar_heartbeats(self):
        print(f"[{self.nome}] Thread de envio de heartbeats iniciada!")
        while self.rodando:
            peers_para_enviar = list(self.peer_uris.keys())
            for nome_peer in peers_para_enviar:
                try:
                    proxy = self.obter_proxy(nome_peer)
                    proxy.receber_heartbeat(self.nome)
                except Exception as e:
                    pass
            time.sleep(self.INTERVALO_HEARTBEAT)
    
    def _verificar_heartbeats(self):
        print(f"[{self.nome}] Thread de verificação de heartbeats iniciada!")
        while self.rodando:
            time.sleep(self.INTERVALO_HEARTBEAT)
            tempo_atual = time.time()
            peers_mortos = []
            with self.lock:
                for nome_peer, ultimo_heartbeat in self.ultimos_heartbeats.items():
                    if (tempo_atual - ultimo_heartbeat) > self.TIMEOUT_HEARTBEAT:
                        if nome_peer in self.peers_ativos:
                            peers_mortos.append(nome_peer)
            for nome_peer in peers_mortos:
                self._remover_peer_morto(nome_peer)
    
    def receber_heartbeat(self, nome_peer):
        with self.lock:
            self.ultimos_heartbeats[nome_peer] = time.time()
            if nome_peer not in self.peers_ativos:
                self.peers_ativos.add(nome_peer)
                print(f"[{self.nome}] 💚 {nome_peer} está ativo!")
                try:
                    ns_local = Pyro5.api.locate_ns()
                    uri_atualizada = ns_local.lookup(nome_peer)
                    if self.peer_uris.get(nome_peer) != uri_atualizada:
                        self.peer_uris[nome_peer] = uri_atualizada
                        print(f"[{self.nome}] 🔄 URI de {nome_peer} atualizada!")
                except:
                    pass
    
    def _remover_peer_morto(self, nome_peer):
        with self.lock:
            if nome_peer in self.peers_ativos:
                self.peers_ativos.discard(nome_peer)
                print(f"[{self.nome}] ☠️  {nome_peer} detectado como MORTO (sem heartbeat)")
                if nome_peer in self.peers_necessarios:
                    self.peers_necessarios.discard(nome_peer)
                if self.estado == QUERENDO_ENTRAR and self.respostas_recebidas >= self.peers_necessarios:
                    print(f"[{self.nome}] ✓ Tenho respostas de todos os peers vivos necessários!")
                    self.evento_liberado.set()
    
    def registrar_peer(self, nome_peer, uri_peer):
        if nome_peer not in self.peer_uris:
            self.peer_uris[nome_peer] = uri_peer
            print(f"[{self.nome}] ✓ Peer '{nome_peer}' conectado!")
    
    def obter_proxy(self, nome_peer):
        """
        Cria um proxy para comunicação com outro peer usando o protocolo PYRONAME.
        O próprio Pyro se encarrega de localizar o Name Server e procurar o nome.
        
        Args:
            nome_peer (str): Nome do peer
            
        Returns:
            Proxy PyRO. Pode levantar uma exceção NamingError se o nome não for encontrado.
        """
        return Pyro5.api.Proxy(f"PYRONAME:{nome_peer}")
    
    def mensagem_teste(self, mensagem, remetente):
        print(f"[{self.nome}] Recebi mensagem de {remetente}: '{mensagem}'")
        return f"OK! {self.nome} recebeu sua mensagem."
    
    def listar_peers_conhecidos(self):
        return list(self.peer_uris.keys())
    
    def parar(self):
        self.rodando = False
        if self.thread_descoberta:
            self.thread_descoberta.join(timeout=1)
    
    def receber_pedido(self, timestamp_outro, nome_outro):
        with self.lock:
            self.relogio_logico = max(self.relogio_logico, timestamp_outro) + 1
            print(f"[{self.nome}] Recebi pedido de {nome_outro} (ts={timestamp_outro})")
            if nome_outro not in self.peers_ativos:
                print(f"[{self.nome}] ⚠️  Ignorando pedido de {nome_outro} (peer não está ativo)")
                return "IGNORADO"
            conceder_agora = False
            if self.estado == LIBERADO:
                print(f"[{self.nome}] → Concedendo OK para {nome_outro} (estou liberado)")
                conceder_agora = True
            elif self.estado == DENTRO_DA_SC:
                print(f"[{self.nome}] → Adiando resposta para {nome_outro} (estou usando a SC)")
                self.fila_pedidos.append((timestamp_outro, nome_outro))
                return "ADIADO"
            elif self.estado == QUERENDO_ENTRAR:
                meu_pedido = (self.meu_timestamp, self.nome)
                pedido_outro = (timestamp_outro, nome_outro)
                if meu_pedido < pedido_outro:
                    print(f"[{self.nome}] → Adiando resposta para {nome_outro} (meu pedido é prioritário)")
                    self.fila_pedidos.append((timestamp_outro, nome_outro))
                    return "ADIADO"
                else:
                    print(f"[{self.nome}] → Concedendo OK para {nome_outro} (pedido dele é prioritário)")
                    conceder_agora = True
        if conceder_agora:
            try:
                proxy = self.obter_proxy(nome_outro)
                proxy.receber_resposta(self.nome)
                print(f"[{self.nome}] ✓ OK enviado para {nome_outro}")
                return "OK_ENVIADO"
            except Exception as e:
                print(f"[{self.nome}] ✗ Erro ao enviar OK para {nome_outro}: {e}")
                return "ERRO"
        return "ADIADO"
    
    def receber_resposta(self, nome_outro):
        with self.lock:
            if self.estado != QUERENDO_ENTRAR:
                print(f"[{self.nome}] ℹ️  Recebi OK tardio de {nome_outro}, mas não estou mais esperando. Ignorando.")
                return
            print(f"[{self.nome}] ✓ Recebi OK de {nome_outro}")
            self.respostas_recebidas.add(nome_outro)
            total_necessario = len(self.peers_necessarios)
            total_recebido = len(self.respostas_recebidas)
            print(f"[{self.nome}] Progresso: {total_recebido}/{total_necessario} respostas")
            if self.respostas_recebidas >= self.peers_necessarios:
                print(f"[{self.nome}] 🎉 Recebi OK de TODOS! Liberando para entrar na SC.")
                self.evento_liberado.set()
    
    def solicitar_sc(self):
        with self.lock:
            if self.estado != LIBERADO:
                print(f"[{self.nome}] Erro: já estou em outro estado ({self.estado})")
                return False
            self.estado = QUERENDO_ENTRAR
            self.relogio_logico += 1
            self.meu_timestamp = self.relogio_logico
            self.respostas_recebidas.clear()
            self.evento_liberado.clear()
            print(f"\n[{self.nome}] {'='*50}")
            print(f"[{self.nome}] SOLICITANDO ACESSO À SC (timestamp={self.meu_timestamp})")
            print(f"[{self.nome}] {'='*50}")
            self.peers_necessarios = self.peers_ativos.intersection(set(self.peer_uris.keys()))
            peers_para_pedir = list(self.peers_necessarios)
            total_peers = len(peers_para_pedir)
            if total_peers == 0:
                print(f"[{self.nome}] ⚠️  Nenhum peer ativo detectado! Entrando direto na SC.")
                self.estado = DENTRO_DA_SC
                print(f"\n[{self.nome}] {'='*50}")
                print(f"[{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!")
                print(f"[{self.nome}] {'='*50}\n")
                
                # <<< ALTERAÇÃO: Inicia o timer de liberação automática >>>
                print(f"[{self.nome}] ⏳ O recurso será liberado automaticamente em {self.TEMPO_MAXIMO_SC} segundos.")
                self.timer_sc = Timer(self.TEMPO_MAXIMO_SC, self.liberar_sc)
                self.timer_sc.start()
                # <<< FIM DA ALTERAÇÃO >>>
                return True
        
        print(f"[{self.nome}] Enviando pedidos para {total_peers} peers ativos...")
        for nome_peer in peers_para_pedir:
            threading.Thread(target=self._enviar_pedido_com_timeout, 
                           args=(nome_peer, self.meu_timestamp), 
                           daemon=True).start()
        
        sucesso = self.evento_liberado.wait(timeout=10)
        
        if not sucesso:
            with self.lock:
                peers_ainda_vivos = self.peers_necessarios.intersection(self.peers_ativos)
                if self.respostas_recebidas >= peers_ainda_vivos:
                    sucesso = True
                    print(f"[{self.nome}] ✓ Tenho respostas de todos os peers vivos!")
        
        if not sucesso:
            with self.lock:
                self.estado = LIBERADO
                print(f"[{self.nome}] ✗ Falha ao obter acesso à SC")
                return False
        
        with self.lock:
            self.estado = DENTRO_DA_SC
            print(f"\n[{self.nome}] {'='*50}")
            print(f"[{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!")
            print(f"[{self.nome}] {'='*50}\n")
            
            # <<< ALTERAÇÃO: Inicia o timer de liberação automática >>>
            print(f"[{self.nome}] ⏳ O recurso será liberado automaticamente em {self.TEMPO_MAXIMO_SC} segundos.")
            self.timer_sc = Timer(self.TEMPO_MAXIMO_SC, self.liberar_sc)
            self.timer_sc.start()
            # <<< FIM DA ALTERAÇÃO >>>
            
        return True
    
    def _enviar_pedido_com_timeout(self, nome_peer, timestamp):
        try:
            proxy = self.obter_proxy(nome_peer)
            proxy._pyroTimeout = 5
            resultado = proxy.receber_pedido(timestamp, self.nome)
            print(f"[{self.nome}] Resposta de {nome_peer}: {resultado}")
        except Exception as e:
            print(f"[{self.nome}] ⚠️  Timeout/Erro com {nome_peer}: {e}")
            self._remover_peer_morto(nome_peer)
    
    def liberar_sc(self):
        with self.lock:
            # <<< ALTERAÇÃO: Cancela o timer se ele existir e estiver ativo >>>
            if self.timer_sc and self.timer_sc.is_alive():
                self.timer_sc.cancel()
                print(f"[{self.nome}] ℹ️ Liberação manual. Timer de liberação automática cancelado.")
            # <<< FIM DA ALTERAÇÃO >>>
            
            if self.estado != DENTRO_DA_SC:
                # Evita printar erro se a liberação for chamada pelo timer
                # logo após uma liberação manual.
                return False
            
            print(f"\n[{self.nome}] {'='*50}")
            print(f"[{self.nome}] 🔓 SAINDO DA SEÇÃO CRÍTICA")
            print(f"[{self.nome}] {'='*50}")
            
            pedidos_pendentes = self.fila_pedidos.copy()
            self.fila_pedidos.clear()
            
            self.estado = LIBERADO
            self.meu_timestamp = None
        
        for timestamp, nome_peer in pedidos_pendentes:
            try:
                print(f"[{self.nome}] → Enviando OK adiado para {nome_peer}")
                proxy = self.obter_proxy(nome_peer)
                proxy.receber_resposta(self.nome)
            except Exception as e:
                print(f"[{self.nome}] Erro ao enviar resposta para {nome_peer}: {e}")
        
        print(f"[{self.nome}] ✓ Liberado! Estado: {self.estado}\n")
        return True

    def obter_estado(self):
        with self.lock:
            return {
                "nome": self.nome,
                "estado": self.estado,
                "relogio": self.relogio_logico,
                "timestamp_pedido": self.meu_timestamp,
                "respostas": len(self.respostas_recebidas),
                "fila_pedidos": len(self.fila_pedidos),
                "peers_conhecidos": len(self.peer_uris),
                "peers_ativos": list(self.peers_ativos)
            }
