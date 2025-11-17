# /microservices/ms_leilao/ms-leilao.py

import pika
import json
import time
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'

# --- Configuração do Flask ---
app = Flask(__name__)

# --- "Banco de Dados" em memória ---
# Usaremos um dicionário para armazenar os leilões
# A chave será o 'id_leilao'
leiloes_db = {}
proximo_id_leilao = 1

# --- Lógica de Publicação (Modificada para Thread-safety) ---

def publicar_evento(routing_key: str, evento: dict):
    """
    Publica um evento na exchange principal.
    Cria uma nova conexão para garantir thread-safety com pika.
    """
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
        
        # Converte objetos datetime para string ISO (se houver)
        evento_serializavel = evento.copy()
        for key, value in evento_serializavel.items():
            if isinstance(value, datetime):
                evento_serializavel[key] = value.isoformat()

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(evento_serializavel),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f" [x] Evento '{routing_key}' publicado.")
        connection.close()
    except Exception as e:
        print(f"Erro ao publicar evento: {e}")

# --- Lógica de Agendamento (Substitui o 'while True') ---

def agendar_leilao(id_leilao):
    """
    Esta função roda em uma thread separada para um leilão específico.
    Ela gerencia o ciclo de vida do leilão e publica os eventos.
    """
    try:
        # Pega o leilão do nosso "banco"
        leilao = leiloes_db.get(id_leilao)
        if not leilao:
            print(f"Agendamento falhou: Leilão {id_leilao} não encontrado.")
            return

        agora = datetime.now()
        
        # 1. Espera até a data de início
        tempo_para_iniciar = (leilao['inicio'] - agora).total_seconds()
        if tempo_para_iniciar > 0:
            print(f"Leilão {id_leilao} esperando {tempo_para_iniciar:.0f}s para iniciar.")
            time.sleep(tempo_para_iniciar)
        
        # 2. Inicia o leilão
        leilao['status'] = 'ativo'
        print(f"Leilão {id_leilao} INICIADO.")
        publicar_evento('leilao.iniciado', leilao) # [cite: 56]
        
        # 3. Espera até a data de fim
        agora = datetime.now()
        tempo_para_finalizar = (leilao['fim'] - agora).total_seconds()
        if tempo_para_finalizar > 0:
            print(f"Leilão {id_leilao} esperando {tempo_para_finalizar:.0f}s para finalizar.")
            time.sleep(tempo_para_finalizar)

        # 4. Finaliza o leilão
        leilao['status'] = 'encerrado'
        print(f"Leilão {id_leilao} FINALIZADO.")
        publicar_evento('leilao.finalizado', {"id_leilao": leilao['id_leilao']}) # [cite: 57]

    except Exception as e:
        print(f"Erro na thread do leilão {id_leilao}: {e}")


# --- Endpoints da API REST ---

@app.route('/leiloes', methods=['POST'])
def criar_leilao(): # 
    """
    Cria um novo leilão.
    Recebe JSON com: nome_produto, descricao, valor_inicial, inicio, fim
    """
    global proximo_id_leilao
    dados = request.json

    try:
        novo_leilao = {
            "id_leilao": proximo_id_leilao,
            "nome_produto": dados['nome_produto'], # [cite: 37]
            "descricao": dados['descricao'], # [cite: 37]
            "valor_inicial": float(dados['valor_inicial']), # [cite: 37]
            "inicio": datetime.fromisoformat(dados['inicio']), # [cite: 37]
            "fim": datetime.fromisoformat(dados['fim']), # [cite: 37]
            "status": "agendado"
        }
        
        # Salva no "banco"
        leiloes_db[novo_leilao['id_leilao']] = novo_leilao
        proximo_id_leilao += 1
        
        # Inicia a thread de agendamento para este leilão
        thread_leilao = threading.Thread(target=agendar_leilao, args=(novo_leilao['id_leilao'],))
        thread_leilao.start()
        
        print(f"Leilão {novo_leilao['id_leilao']} criado e agendado.")
        return jsonify(novo_leilao), 201
        
    except Exception as e:
        return jsonify({"erro": str(e)}), 400

@app.route('/leiloes/ativos', methods=['GET'])
def consultar_leiloes_ativos(): # 
    """
    Retorna uma lista de todos os leilões com status 'ativo'.
    """
    agora = datetime.now()
    leiloes_ativos = []
    
    # Filtra o "banco"
    for leilao in leiloes_db.values():
        if leilao['status'] == 'ativo':
            # Prepara os dados para o formato de resposta
            leiloes_ativos.append({
                "id_leilao": leilao['id_leilao'],
                "nome_produto": leilao['nome_produto'], # [cite: 38]
                "descricao": leilao['descricao'], # [cite: 38]
                "valor_inicial": leilao['valor_inicial'], # [cite: 38]
                # "ultimo_lance" será gerenciado pelo MS-Lance, mas o requisito pede
                # valor inicial OU último lance. Por enquanto, enviamos o inicial.
                "valor_atual": leilao.get('valor_inicial'), # [cite: 38]
                "inicio": leilao['inicio'].isoformat(), # [cite: 38]
                "fim": leilao['fim'].isoformat(), # [cite: 38]
            })
            
    return jsonify(leiloes_ativos), 200


# --- Ponto de entrada ---
if __name__ == '__main__':
    # Inicia o servidor Flask.
    # O 'use_reloader=False' é importante para não duplicar as threads de agendamento
    app.run(port=5001, debug=True, use_reloader=False)