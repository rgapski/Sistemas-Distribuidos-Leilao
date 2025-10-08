import Pyro5.api
import threading
import time

@Pyro5.api.expose
class Peer:
    """
    Classe que representa um processo (peer) no sistema distribuído.
    Versão 1: Estrutura básica com comunicação.
    """
    
    def __init__(self, nome):
        """
        Inicializa um peer com seu nome único.
        
        Args:
            nome (str): Nome do peer (ex: "PeerA", "PeerB")
        """
        self.nome = nome
        self.peers = {}  # Dicionário para guardar referências aos outros peers
        self.ns = None  # Referência ao servidor de nomes
        self.todos_peers = []  # Lista de todos os peers do sistema
        self.thread_descoberta = None  # Thread de descoberta contínua
        self.rodando = True  # Flag para controlar threads
        
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
                if outro_peer != self.nome and outro_peer not in self.peers:
                    try:
                        uri_outro = ns_local.lookup(outro_peer)
                        proxy = Pyro5.api.Proxy(uri_outro)
                        self.registrar_peer(outro_peer, proxy)
                        novos_encontrados.append(outro_peer)
                    except:
                        pass  # Peer ainda não disponível
            
            # Só mostra mensagem se encontrou novos peers
            if novos_encontrados:
                print(f"[{self.nome}] Novos peers descobertos: {novos_encontrados}")
            
            time.sleep(3)  # Verifica a cada 3 segundos
    
    def registrar_peer(self, nome_peer, proxy_peer):
        """
        Registra a referência (proxy) de outro peer.
        
        Args:
            nome_peer (str): Nome do outro peer
            proxy_peer: Objeto proxy PyRO para comunicação
        """
        if nome_peer not in self.peers:
            self.peers[nome_peer] = proxy_peer
            print(f"[{self.nome}] ✓ Peer '{nome_peer}' conectado!")
    
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
        return list(self.peers.keys())
    
    def parar(self):
        """
        Para as threads do peer de forma limpa.
        """
        self.rodando = False
        if self.thread_descoberta:
            self.thread_descoberta.join(timeout=1)