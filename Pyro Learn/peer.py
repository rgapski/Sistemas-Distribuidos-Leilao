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
        self.lock = threading.Lock()  # Lock para proteger acesso concorrente
        self.evento_liberado = threading.Event()  # Para sincronização de threads
        
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
            for outro_peer in self.todos_peers:
                if outro_peer != self.nome and outro_peer not in self.peer_uris:
                    try:
                        uri_outro = ns_local.lookup(outro_peer)
                        self.registrar_peer(outro_peer, uri_outro)
                        novos_encontrados.append(outro_peer)
                    except:
                        pass  # Peer ainda não disponível
            
            # Só mostra mensagem se encontrou novos peers
            if novos_encontrados:
                print(f"[{self.nome}] Novos peers descobertos: {novos_encontrados}")
            
            time.sleep(3)  # Verifica a cada 3 segundos
    
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
            
            # Verifica se já recebeu todas as respostas necessárias
            peers_necessarios = set(self.peer_uris.keys())
            total_necessario = len(peers_necessarios)
            total_recebido = len(self.respostas_recebidas)
            
            print(f"[{self.nome}] Progresso: {total_recebido}/{total_necessario} respostas")
            
            if self.respostas_recebidas >= peers_necessarios:
                print(f"[{self.nome}] 🎉 Recebi OK de TODOS! Liberando para entrar na SC.")
                self.evento_liberado.set()  # Libera a thread que está esperando
    
    def solicitar_sc(self):
        """
        Método local: solicita acesso à Seção Crítica.
        Bloqueia até conseguir permissão de todos os peers.
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
            
            # Lista de peers para pedir permissão
            peers_para_pedir = list(self.peer_uris.keys())
            total_peers = len(peers_para_pedir)
        
        # Envia pedidos para todos (fora do lock para não travar)
        print(f"[{self.nome}] Enviando pedidos para {total_peers} peers...")
        for nome_peer in peers_para_pedir:
            try:
                proxy = self.obter_proxy(nome_peer)
                resultado = proxy.receber_pedido(self.meu_timestamp, self.nome)
                print(f"[{self.nome}] Resposta de {nome_peer}: {resultado}")
            except Exception as e:
                print(f"[{self.nome}] Erro ao pedir para {nome_peer}: {e}")
        
        # Aguarda todas as respostas
        with self.lock:
            respostas_atuais = len(self.respostas_recebidas)
        
        print(f"[{self.nome}] Aguardando respostas... ({respostas_atuais}/{total_peers})")
        self.evento_liberado.wait()  # Bloqueia até receber todas
        
        # Entra na SC
        with self.lock:
            self.estado = DENTRO_DA_SC
            print(f"\n[{self.nome}] {'='*50}")
            print(f"[{self.nome}] 🔒 ENTREI NA SEÇÃO CRÍTICA!")
            print(f"[{self.nome}] {'='*50}\n")
        
        return True
    
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
                "peers_conhecidos": len(self.peer_uris)
            }
        