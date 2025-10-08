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
        
        print(f"[{self.nome}] Peer inicializado!")
    
    def registrar_peer(self, nome_peer, proxy_peer):
        """
        Registra a referência (proxy) de outro peer.
        
        Args:
            nome_peer (str): Nome do outro peer
            proxy_peer: Objeto proxy PyRO para comunicação
        """
        self.peers[nome_peer] = proxy_peer
        print(f"[{self.nome}] Peer '{nome_peer}' registrado!")
    
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