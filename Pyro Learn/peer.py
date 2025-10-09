import Pyro5.api
import threading
import time

# Estados possíveis do peer
LIBERADO = "LIBERADO"
QUERENDO_ENTRAR = "QUERENDO_ENTRAR"
DENTRO_DA_SC = "DENTRO_DA_SC"

@Pyro5.api.expose
class Peer:
    """
    Classe que representa um processo (peer) no sistema distribuído.
    Versão 2: Com algoritmo de Ricart e Agrawala.
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
        
        print(f"[{self.nome}] Peer inicializado!")
    
    def configurar_descoberta(self, ns, todos_peers):
        """
        Configura a descoberta contínua de peers.
        
        Args:
            ns: Referência ao servidor de nomes
            todos_peers (list): Lista com nomes de todos os peers
        """
        self.ns = ns
        self.todos_peers = todos_peers
        
        # Inicia thread de descoberta contínua
        self.thread_descoberta = threading.Thread(target=self._descobrir_peers_continuamente, daemon=True)
        self.thread_descoberta.start()
        
        # Inicia threads de heartbeat
        self.thread_heartbeat_envio = threading.Thread(target=self._enviar_heartbeats, daemon=True)
        self.thread_heartbeat_envio.start()
        
        self.thread_heartbeat_verificacao = threading.Thread(target=self._verificar_heartbeats, daemon=True)
        self.thread_heartbeat_verificacao.start()
    
    def _descobrir_peers_continuamente(self):
        """
        Thread que fica continuamente procurando por novos peers.
        Roda a cada 3 segundos.
        """
        print(f"[{self.nome}] Thread de descoberta iniciada!")
        
        # IMPORTANTE: Esta thread precisa de sua própria conexão com o nameserver!
        ns_local = Pyro5.api.locate_ns()
        
        while self.rodando:
            novos_encontrados = []
            uris_atualizadas = []
            
            for outro_peer in self.todos_peers:
                if outro_peer != self.nome:
                    try:
                        uri_outro = ns_local.lookup(outro_peer)
                        
                        # Verifica se é um peer novo ou se a URI mudou
                        if outro_peer not in self.peer_uris:
                            self.registrar_peer(outro_peer, uri_outro)
                            novos_encontrados.append(outro_peer)
                        elif self.peer_uris[outro_peer] != uri_outro:
                            # URI mudou (peer reiniciou)
                            with self.lock:
                                self.peer_uris[outro_peer] = uri_outro
                            uris_atualizadas.append(outro_peer)
                            print(f"[{self.nome}] 🔄 URI de {outro_peer} atualizada (peer reiniciou)")
                    except:
                        pass  # Peer ainda não disponível
            
            # Só mostra mensagem se encontrou novos peers
            if novos_encontrados:
                print(f"[{self.nome}] Novos peers descobertos: {novos_encontrados}")
            
            time.sleep(3)  # Verifica a cada 3 segundos
    
    def _enviar_heartbeats(self):
        """
        Thread que envia heartbeats periodicamente para todos os peers.
        """
        print(f"[{self.nome}] Thread de envio de heartbeats iniciada!")
        
        while self.rodando:
            peers_para_enviar = list(self.peer_uris.keys())
            
            for nome_peer in peers_para_enviar:
                try:
                    proxy = self.obter_proxy(nome_peer)
                    proxy.receber_heartbeat(self.nome)
                except Exception as e:
                    # Silenciosamente ignora erros (peer pode estar temporariamente indisponível)
                    pass
            
            time.sleep(self.INTERVALO_HEARTBEAT)
    
    def _verificar_heartbeats(self):
        """
        Thread que verifica se os peers estão enviando heartbeats.
        Remove peers que não respondem há muito tempo.
        """
        print(f"[{self.nome}] Thread de verificação de heartbeats iniciada!")
        
        while self.rodando:
            time.sleep(self.INTERVALO_HEARTBEAT)
            
            tempo_atual = time.time()
            peers_mortos = []
            
            with self.lock:
                for nome_peer, ultimo_heartbeat in self.ultimos_heartbeats.items():
                    tempo_sem_resposta = tempo_atual - ultimo_heartbeat
                    
                    if tempo_sem_resposta > self.TIMEOUT_HEARTBEAT:
                        if nome_peer in self.peers_ativos:
                            peers_mortos.append(nome_peer)
            
            # Remove peers mortos (fora do lock para evitar deadlock)
            for nome_peer in peers_mortos:
                self._remover_peer_morto(nome_peer)
    
    def receber_heartbeat(self, nome_peer):
        """
        Método remoto: recebe um heartbeat de outro peer.
        
        Args:
            nome_peer (str): Nome do peer que enviou o heartbeat
        """
        with self.lock:
            self.ultimos_heartbeats[nome_peer] = time.time()
            
            # Se o peer não estava na lista de ativos, adiciona
            if nome_peer not in self.peers_ativos:
                self.peers_ativos.add(nome_peer)
                print(f"[{self.nome}] 💚 {nome_peer} está ativo!")
                
                # IMPORTANTE: Atualiza a URI do peer (pode ter mudado se ele reiniciou)
                try:
                    ns_local = Pyro5.api.locate_ns()
                    uri_atualizada = ns_local.lookup(nome_peer)
                    uri_antiga = self.peer_uris.get(nome_peer)
                    
                    if uri_antiga != uri_atualizada:
                        self.peer_uris[nome_peer] = uri_atualizada
                        print(f"[{self.nome}] 🔄 URI de {nome_peer} atualizada!")
                except:
                    pass
    
    def _remover_peer_morto(self, nome_peer):
        """
        Remove um peer que foi detectado como morto.
        
        Args:
            nome_peer (str): Nome do peer a ser removido
        """
        with self.lock:
            if nome_peer in self.peers_ativos:
                self.peers_ativos.discard(nome_peer)
                print(f"[{self.nome}] ☠️  {nome_peer} detectado como MORTO (sem heartbeat)")
                
                # Remove das respostas esperadas se estava esperando
                if nome_peer in self.peers_necessarios:
                    self.peers_necessarios.discard(nome_peer)
                
                # Verifica se agora temos todas as respostas dos peers vivos necessários
                if self.estado == QUERENDO_ENTRAR and self.respostas_recebidas >= self.peers_necessarios:
                    print(f"[{self.nome}] ✓ Tenho respostas de todos os peers vivos necessários!")
                    self.evento_liberado.set()
    
    def registrar_peer(self, nome_peer, uri_peer):
        """
        Registra a URI de outro peer.
        
        Args:
            nome_peer (str): Nome do outro peer
            uri_peer (str): URI do peer para comunicação
        """
        if nome_peer not in self.peer_uris:
            self.peer_uris[nome_peer] = uri_peer
            print(f"[{self.nome}] ✓ Peer '{nome_peer}' conectado!")
    
    def obter_proxy(self, nome_peer):
        """
        Cria um proxy para comunicação com outro peer.
        Cada chamada cria um novo proxy, seguro para usar em qualquer thread.
        
        Args:
            nome_peer (str): Nome do peer
            
        Returns:
            Proxy PyRO ou None se o peer não for conhecido
        """
        if nome_peer in self.peer_uris:
            return Pyro5.api.Proxy(self.peer_uris[nome_peer])
        return None
    
    def mensagem_teste(self, mensagem, remetente):
        """
        Método remoto para testar comunicação entre peers.
        
        Args:
            mensagem (str): Mensagem recebida
            remetente (str): Nome do peer que enviou
        
        Returns:
            str: Resposta à mensagem
        """
        print(f"[{self.nome}] Recebi mensagem de {remetente}: '{mensagem}'")
        return f"OK! {self.nome} recebeu sua mensagem."
    
    def listar_peers_conhecidos(self):
        """
        Lista todos os peers que este peer conhece.
        
        Returns:
            list: Lista com nomes dos peers conhecidos
        """
        return list(self.peer_uris.keys())
    
    def parar(self):
        """
        Para as threads do peer de forma limpa.
        """
        self.rodando = False
        if self.thread_descoberta:
            self.thread_descoberta.join(timeout=1)
    
    # ========== MÉTODOS DO ALGORITMO DE RICART E AGRAWALA ==========
    
    def receber_pedido(self, timestamp_outro, nome_outro):
        """
        Método remoto: recebe um pedido de acesso à SC de outro peer.
        
        Args:
            timestamp_outro (int): Timestamp do pedido do outro peer
            nome_outro (str): Nome do peer que está pedindo
            
        Returns:
            str: Status da resposta
        """
        with self.lock:
            # Atualiza o relógio lógico (regra de Lamport)
            self.relogio_logico = max(self.relogio_logico, timestamp_outro) + 1
            
            print(f"[{self.nome}] Recebi pedido de {nome_outro} (ts={timestamp_outro})")
            
            # Verifica se o peer solicitante está ativo (recebeu heartbeat recentemente)
            if nome_outro not in self.peers_ativos:
                print(f"[{self.nome}] ⚠️  Ignorando pedido de {nome_outro} (peer não está ativo)")
                return "IGNORADO"
            
            conceder_agora = False
            
            # CASO 1: Estou LIBERADO - concedo imediatamente
            if self.estado == LIBERADO:
                print(f"[{self.nome}] → Concedendo OK para {nome_outro} (estou liberado)")
                conceder_agora = True
            
            # CASO 2: Estou DENTRO_DA_SC - guardo o pedido para responder depois
            elif self.estado == DENTRO_DA_SC:
                print(f"[{self.nome}] → Adiando resposta para {nome_outro} (estou usando a SC)")
                self.fila_pedidos.append((timestamp_outro, nome_outro))
                return "ADIADO"
            
            # CASO 3: Estou QUERENDO_ENTRAR - comparo timestamps
            elif self.estado == QUERENDO_ENTRAR:
                # Compara: (timestamp, nome) - menor tem prioridade
                meu_pedido = (self.meu_timestamp, self.nome)
                pedido_outro = (timestamp_outro, nome_outro)
                
                if meu_pedido < pedido_outro:
                    # Meu pedido é mais antigo/prioritário - adio resposta
                    print(f"[{self.nome}] → Adiando resposta para {nome_outro} (meu pedido é prioritário)")
                    self.fila_pedidos.append((timestamp_outro, nome_outro))
                    return "ADIADO"
                else:
                    # Pedido dele é prioritário - concedo imediatamente
                    print(f"[{self.nome}] → Concedendo OK para {nome_outro} (pedido dele é prioritário)")
                    conceder_agora = True
        
        # Se decidiu conceder, envia a resposta via receber_resposta (fora do lock)
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
        """
        Método remoto: recebe uma resposta OK de outro peer.
        
        Args:
            nome_outro (str): Nome do peer que concedeu permissão
        """
        with self.lock:
            print(f"[{self.nome}] ✓ Recebi OK de {nome_outro}")
            self.respostas_recebidas.add(nome_outro)
            
            # Usa os peers necessários definidos no momento do pedido
            total_necessario = len(self.peers_necessarios)
            total_recebido = len(self.respostas_recebidas)
            
            print(f"[{self.nome}] Progresso: {total_recebido}/{total_necessario} respostas")
            
            if self.respostas_recebidas >= self.peers_necessarios:
                print(f"[{self.nome}] 🎉 Recebi OK de TODOS! Liberando para entrar na SC.")
                self.evento_liberado.set()  # Libera a thread que está esperando
    
    def solicitar_sc(self):
        """
        Método local: solicita acesso à Seção Crítica.
        Bloqueia até conseguir permissão de todos os peers ATIVOS.
        """
        with self.lock:
            if self.estado != LIBERADO:
                print(f"[{self.nome}] Erro: já estou em outro estado ({self.estado})")
                return False
            
            # Muda estado e prepara para solicitar
            self.estado = QUERENDO_ENTRAR
            self.relogio_logico += 1
            self.meu_timestamp = self.relogio_logico
            self.respostas_recebidas.clear()
            self.evento_liberado.clear()
            
            print(f"\n[{self.nome}] {'='*50}")
            print(f"[{self.nome}] SOLICITANDO ACESSO À SC (timestamp={self.meu_timestamp})")
            print(f"[{self.nome}] {'='*50}")
            
            # Lista de peers ATIVOS para pedir permissão (snapshot no momento do pedido)
            self.peers_necessarios = self.peers_ativos.intersection(set(self.peer_uris.keys()))
            peers_para_pedir = list(self.peers_necessarios)
            total_peers = len(peers_para_pedir)
            
            if total_peers == 0:
                print(f"[{self.nome}] ⚠️  Nenhum peer ativo detectado! Entrando direto na SC.")
                self.estado = DENTRO_DA_SC
                print(f"\n[{self.nome}] {'='*50}")
                print(f"[{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!")
                print(f"[{self.nome}] {'='*50}\n")
                return True
        
        # Envia pedidos para todos os peers ativos (fora do lock para não travar)
        print(f"[{self.nome}] Enviando pedidos para {total_peers} peers ativos...")
        for nome_peer in peers_para_pedir:
            threading.Thread(target=self._enviar_pedido_com_timeout, 
                           args=(nome_peer, self.meu_timestamp), 
                           daemon=True).start()
        
        # Aguarda todas as respostas com timeout
        with self.lock:
            respostas_atuais = len(self.respostas_recebidas)
        
        print(f"[{self.nome}] Aguardando respostas... ({respostas_atuais}/{total_peers})")
        
        # Aguarda com timeout de 10 segundos
        sucesso = self.evento_liberado.wait(timeout=10)
        
        if not sucesso:
            print(f"[{self.nome}] ⚠️  Timeout! Verificando peers ativos...")
            with self.lock:
                # Recalcula peers necessários considerando os que ainda estão ativos
                peers_ainda_vivos = self.peers_necessarios.intersection(self.peers_ativos)
                if self.respostas_recebidas >= peers_ainda_vivos:
                    sucesso = True
                    print(f"[{self.nome}] ✓ Tenho respostas de todos os peers vivos!")
        
        if not sucesso:
            with self.lock:
                self.estado = LIBERADO
                print(f"[{self.nome}] ✗ Falha ao obter acesso à SC")
                return False
        
        # Entra na SC
        with self.lock:
            self.estado = DENTRO_DA_SC
            print(f"\n[{self.nome}] {'='*50}")
            print(f"[{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!")
            print(f"[{self.nome}] {'='*50}\n")
        
        return True
    
    def _enviar_pedido_com_timeout(self, nome_peer, timestamp):
        """
        Envia um pedido para um peer com timeout.
        
        Args:
            nome_peer (str): Nome do peer destinatário
            timestamp (int): Timestamp do pedido
        """
        try:
            proxy = self.obter_proxy(nome_peer)
            # Configura timeout de 5 segundos na chamada remota
            proxy._pyroTimeout = 5
            resultado = proxy.receber_pedido(timestamp, self.nome)
            print(f"[{self.nome}] Resposta de {nome_peer}: {resultado}")
        except Exception as e:
            print(f"[{self.nome}] ⚠️  Timeout/Erro com {nome_peer}: {e}")
            # Remove o peer da lista de ativos
            self._remover_peer_morto(nome_peer)
    
    def liberar_sc(self):
        """
        Método local: libera a Seção Crítica.
        Envia respostas OK para todos os pedidos pendentes.
        """
        with self.lock:
            if self.estado != DENTRO_DA_SC:
                print(f"[{self.nome}] Erro: não estou na SC (estado={self.estado})")
                return False
            
            print(f"\n[{self.nome}] {'='*50}")
            print(f"[{self.nome}] 🔓 SAINDO DA SEÇÃO CRÍTICA")
            print(f"[{self.nome}] {'='*50}")
            
            # Copia a fila de pedidos pendentes
            pedidos_pendentes = self.fila_pedidos.copy()
            self.fila_pedidos.clear()
            
            # Volta para o estado LIBERADO
            self.estado = LIBERADO
            self.meu_timestamp = None
        
        # Envia respostas para todos os pedidos pendentes (fora do lock)
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
        """
        Retorna informações sobre o estado atual do peer.
        
        Returns:
            dict: Dicionário com informações do estado
        """
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