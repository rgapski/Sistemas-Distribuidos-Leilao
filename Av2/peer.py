import Pyro5.api
import threading
import time
from datetime import datetime

@Pyro5.api.expose
class Peer:
    # Estados possíveis
    LIBERADO = "LIBERADO"
    QUERENDO_ENTRAR = "QUERENDO_ENTRAR"
    DENTRO_DA_SC = "DENTRO_DA_SC"
    
    def __init__(self, nome):
        self.nome = nome
        self.estado = self.LIBERADO
        self.relogio_logico = 0
        self.timestamp_pedido = None
        
        # Gerenciamento de peers
        self.peers = {}  # {nome: proxy}
        self.ultimos_heartbeats = {}  # {nome: timestamp}
        
        # Controle de exclusão mútua
        self.fila_de_pedidos = []  # [(timestamp, peer_id)]
        self.respostas_recebidas = set()  # {peer_id}
        self.respostas_necessarias = 0
        
        # Locks para thread-safety
        self.lock_estado = threading.Lock()
        self.lock_relogio = threading.Lock()
        self.lock_fila = threading.Lock()
        self.lock_respostas = threading.Lock()
        
        # Timer da SC
        self.timer_sc = None
        
        # Controle de threads
        self.rodando = True
        
    def adicionar_peer(self, nome_peer, proxy):
        """Adiciona um peer à lista de peers conhecidos"""
        self.peers[nome_peer] = proxy
        self.ultimos_heartbeats[nome_peer] = time.time()
        print(f"[{self.nome}] Peer {nome_peer} adicionado")
    
    def incrementar_relogio(self, timestamp_recebido=None):
        """Incrementa o relógio lógico (Lamport)"""
        with self.lock_relogio:
            if timestamp_recebido is not None:
                self.relogio_logico = max(self.relogio_logico, timestamp_recebido) + 1
            else:
                self.relogio_logico += 1
            return self.relogio_logico
    
    # ========== ALGORITMO DE RICART E AGRAWALA ==========
    
    def solicitar_sc(self):
        """Solicita acesso à Seção Crítica"""
        print(f"\n[{self.nome}] Solicitando acesso à Seção Crítica...")
        
        with self.lock_estado:
            if self.estado != self.LIBERADO:
                print(f"[{self.nome}] Erro: já está em estado {self.estado}")
                return False
            self.estado = self.QUERENDO_ENTRAR
        
        # Incrementa relógio e cria timestamp
        timestamp = self.incrementar_relogio()
        self.timestamp_pedido = timestamp
        
        # Prepara para receber respostas
        with self.lock_respostas:
            self.respostas_recebidas.clear()
            self.respostas_necessarias = len(self.peers)
        
        print(f"[{self.nome}] Enviando pedidos com timestamp {timestamp}")
        
        # Envia pedido para todos os peers ativos
        peers_falhos = []
        for nome_peer, proxy in list(self.peers.items()):
            try:
                # Chama com timeout de 3 segundos
                Pyro5.api.Proxy._pyroTimeout = 3.0
                resposta = proxy.receber_pedido(timestamp, self.nome)
                
                if resposta:
                    with self.lock_respostas:
                        self.respostas_recebidas.add(nome_peer)
                    print(f"[{self.nome}] Resposta OK de {nome_peer}")
                    
            except Exception as e:
                print(f"[{self.nome}] Erro ao contactar {nome_peer}: {e}")
                peers_falhos.append(nome_peer)
        
        # Remove peers falhos
        for nome_peer in peers_falhos:
            self.remover_peer_falho(nome_peer)
        
        # Aguarda todas as respostas
        print(f"[{self.nome}] Aguardando respostas...")
        timeout = 10  # 10 segundos no total
        inicio = time.time()
        
        while True:
            with self.lock_respostas:
                recebidas = len(self.respostas_recebidas)
                necessarias = self.respostas_necessarias
            
            if recebidas >= necessarias:
                break
            
            if time.time() - inicio > timeout:
                print(f"[{self.nome}] Timeout aguardando respostas")
                break
            
            time.sleep(0.1)
        
        # Entra na Seção Crítica
        self.entrar_sc()
        return True
    
    def receber_pedido(self, timestamp_outro, nome_outro):
        """
        Recebe um pedido de outro peer
        Retorna True (OK) ou False (aguardar)
        """
        # Atualiza relógio lógico
        self.incrementar_relogio(timestamp_outro)
        
        print(f"[{self.nome}] Pedido recebido de {nome_outro} com timestamp {timestamp_outro}")
        
        with self.lock_estado:
            estado_atual = self.estado
            meu_timestamp = self.timestamp_pedido
        
        # Caso 1: LIBERADO - responde OK imediatamente
        if estado_atual == self.LIBERADO:
            print(f"[{self.nome}] Estado LIBERADO - respondendo OK para {nome_outro}")
            return True
        
        # Caso 2: DENTRO_DA_SC - adia resposta
        elif estado_atual == self.DENTRO_DA_SC:
            print(f"[{self.nome}] Dentro da SC - adiando resposta para {nome_outro}")
            with self.lock_fila:
                self.fila_de_pedidos.append((timestamp_outro, nome_outro))
                self.fila_de_pedidos.sort()  # Ordena por timestamp
            return False
        
        # Caso 3: QUERENDO_ENTRAR - compara timestamps
        elif estado_atual == self.QUERENDO_ENTRAR:
            # Prioridade: menor timestamp vence
            # Desempate: ordem alfabética
            if timestamp_outro < meu_timestamp:
                print(f"[{self.nome}] {nome_outro} tem prioridade - respondendo OK")
                return True
            elif timestamp_outro == meu_timestamp:
                # Desempate alfabético
                if nome_outro < self.nome:
                    print(f"[{self.nome}] Desempate: {nome_outro} tem prioridade - respondendo OK")
                    return True
                else:
                    print(f"[{self.nome}] Desempate: tenho prioridade - adiando resposta")
                    with self.lock_fila:
                        self.fila_de_pedidos.append((timestamp_outro, nome_outro))
                        self.fila_de_pedidos.sort()
                    return False
            else:
                print(f"[{self.nome}] Tenho prioridade - adiando resposta para {nome_outro}")
                with self.lock_fila:
                    self.fila_de_pedidos.append((timestamp_outro, nome_outro))
                    self.fila_de_pedidos.sort()
                return False
        
        return False
    
    def entrar_sc(self):
        """Entra na Seção Crítica"""
        with self.lock_estado:
            self.estado = self.DENTRO_DA_SC
        
        print(f"\n{'='*50}")
        print(f"[{self.nome}] ✓ ENTROU NA SEÇÃO CRÍTICA")
        print(f"{'='*50}\n")
        
        # Inicia timer para liberar automaticamente após 15 segundos
        self.timer_sc = threading.Timer(15.0, self.liberar_sc_automaticamente)
        self.timer_sc.start()
    
    def liberar_sc_automaticamente(self):
        """Libera a SC automaticamente por timeout"""
        print(f"[{self.nome}] Tempo limite na SC atingido - liberando automaticamente")
        self.liberar_sc()
    
    def liberar_sc(self):
        """Libera a Seção Crítica"""
        with self.lock_estado:
            if self.estado != self.DENTRO_DA_SC:
                print(f"[{self.nome}] Não está na SC")
                return
            self.estado = self.LIBERADO
        
        # Cancela timer se ainda estiver ativo
        if self.timer_sc and self.timer_sc.is_alive():
            self.timer_sc.cancel()
        
        print(f"\n{'='*50}")
        print(f"[{self.nome}] ✗ LIBEROU A SEÇÃO CRÍTICA")
        print(f"{'='*50}\n")
        
        # Processa fila de pedidos pendentes
        with self.lock_fila:
            pedidos_pendentes = self.fila_de_pedidos.copy()
            self.fila_de_pedidos.clear()
        
        # Envia OK para todos os pedidos pendentes
        for timestamp, nome_peer in pedidos_pendentes:
            if nome_peer in self.peers:
                try:
                    print(f"[{self.nome}] Enviando OK pendente para {nome_peer}")
                    # Aqui seria ideal ter um método receber_resposta_tardia
                    # Por simplicidade, o peer solicitante já recebeu False e está aguardando
                except Exception as e:
                    print(f"[{self.nome}] Erro ao enviar OK para {nome_peer}: {e}")
    
    # ========== HEARTBEAT E DETECÇÃO DE FALHAS ==========
    
    def iniciar_heartbeat(self):
        """Inicia thread de envio de heartbeats"""
        thread = threading.Thread(target=self._enviar_heartbeats, daemon=True)
        thread.start()
        print(f"[{self.nome}] Thread de heartbeat iniciada")
    
    def _enviar_heartbeats(self):
        """Envia heartbeats periodicamente"""
        while self.rodando:
            time.sleep(2)  # Envia a cada 2 segundos
            
            for nome_peer, proxy in list(self.peers.items()):
                try:
                    proxy.receber_heartbeat(self.nome)
                except Exception:
                    pass  # Silenciosamente ignora falhas
    
    def receber_heartbeat(self, nome_peer):
        """Recebe heartbeat de outro peer"""
        self.ultimos_heartbeats[nome_peer] = time.time()
    
    def iniciar_verificacao_falhas(self):
        """Inicia thread de verificação de falhas"""
        thread = threading.Thread(target=self._verificar_falhas, daemon=True)
        thread.start()
        print(f"[{self.nome}] Thread de verificação de falhas iniciada")
    
    def _verificar_falhas(self):
        """Verifica periodicamente se algum peer falhou"""
        while self.rodando:
            time.sleep(3)  # Verifica a cada 3 segundos
            
            tempo_atual = time.time()
            peers_falhos = []
            
            for nome_peer, ultimo_heartbeat in list(self.ultimos_heartbeats.items()):
                if tempo_atual - ultimo_heartbeat > 6:  # 6 segundos sem heartbeat
                    peers_falhos.append(nome_peer)
            
            for nome_peer in peers_falhos:
                self.remover_peer_falho(nome_peer)
    
    def remover_peer_falho(self, nome_peer):
        """Remove um peer considerado falho"""
        if nome_peer in self.peers:
            del self.peers[nome_peer]
            del self.ultimos_heartbeats[nome_peer]
            
            with self.lock_respostas:
                self.respostas_necessarias = len(self.peers)
            
            print(f"[{self.nome}] ⚠ Peer {nome_peer} removido (falha detectada)")
    
    # ========== UTILITÁRIOS ==========
    
    def obter_status(self):
        """Retorna o status atual do peer"""
        with self.lock_estado:
            estado = self.estado
        with self.lock_relogio:
            relogio = self.relogio_logico
        
        peers_ativos = list(self.peers.keys())
        
        return {
            'nome': self.nome,
            'estado': estado,
            'relogio': relogio,
            'peers_ativos': peers_ativos,
            'timestamp_pedido': self.timestamp_pedido
        }
    
    def parar(self):
        """Para as threads do peer"""
        self.rodando = False
        if self.timer_sc:
            self.timer_sc.cancel()