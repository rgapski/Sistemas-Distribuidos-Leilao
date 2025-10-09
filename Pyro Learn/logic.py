# Arquivo: logic.py

import threading

# Constantes de estado para clareza
LIBERADO = "LIBERADO"
QUERENDO_ENTRAR = "QUERENDO_ENTRAR"
DENTRO_DA_SC = "DENTRO_DA_SC"

class RicartAgrawalaLogic:
    """
    Contém a lógica pura e o estado do algoritmo de Ricart e Agrawala.
    Esta classe é agnóstica a qualquer tecnologia de rede (não conhece PyRO).
    """
    def __init__(self, nome):
        self.nome = nome
        self.estado = LIBERADO
        self.relogio_logico = 0
        self.meu_timestamp = None
        self.fila_pedidos = []
        self.respostas_recebidas = set()
        self.peers_necessarios = set()
        # <<< ALTERAÇÃO: Trocado Lock por RLock para permitir locks aninhados >>>
        self.lock = threading.RLock()

    def iniciar_pedido_sc(self, peers_ativos):
        with self.lock:
            if self.estado != LIBERADO:
                return None, None # Já está em outro processo

            self.estado = QUERENDO_ENTRAR
            self.relogio_logico += 1
            self.meu_timestamp = self.relogio_logico
            
            self.respostas_recebidas.clear()
            self.peers_necessarios = peers_ativos.copy()
            
            return self.meu_timestamp, list(self.peers_necessarios)

    def receber_pedido(self, timestamp_outro, nome_outro):
        with self.lock:
            self.relogio_logico = max(self.relogio_logico, timestamp_outro) + 1

            if self.estado == LIBERADO or \
               (self.estado == QUERENDO_ENTRAR and (timestamp_outro, nome_outro) < (self.meu_timestamp, self.nome)):
                return "CONCEDER_AGORA"
            else:
                self.fila_pedidos.append((timestamp_outro, nome_outro))
                return "ADIAR"

    def receber_resposta(self, nome_outro):
        with self.lock:
            if self.estado != QUERENDO_ENTRAR:
                return False, "TARDIO" # Resposta tardia, não estamos mais esperando

            self.respostas_recebidas.add(nome_outro)
            
            if self.respostas_recebidas >= self.peers_necessarios:
                return True, "COMPLETO" # Condição para entrar na SC foi atingida
            
            return False, "PARCIAL" # Ainda faltam respostas

    def entrar_sc(self):
        with self.lock:
            self.estado = DENTRO_DA_SC

    def falhar_pedido(self):
        with self.lock:
            self.estado = LIBERADO

    def liberar_sc(self):
        with self.lock:
            if self.estado != DENTRO_DA_SC:
                return []
                
            self.estado = LIBERADO
            self.meu_timestamp = None
            pedidos_pendentes = self.fila_pedidos.copy()
            self.fila_pedidos.clear()
            return pedidos_pendentes

    def remover_peer_de_espera(self, nome_peer):
        with self.lock:
            if self.estado == QUERENDO_ENTRAR and nome_peer in self.peers_necessarios:
                self.peers_necessarios.discard(nome_peer)
                # Verifica se a condição de entrada na SC foi atingida após a remoção
                return self.respostas_recebidas >= self.peers_necessarios
        return False

    def obter_estado(self):
        with self.lock:
            return {
                "estado": self.estado,
                "relogio": self.relogio_logico,
                "timestamp_pedido": self.meu_timestamp,
                "respostas": len(self.respostas_recebidas),
                "fila_pedidos": len(self.fila_pedidos)
            }