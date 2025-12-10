# /microservices/ms-leilao/ms-leilao.py

import pika
import json
import time
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timezone

# --- Configurações ---
RABBITMQ_HOST = '127.0.0.1'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'

#Publica 2 eventos: leilao.iniciado e leilao.finalizado

app = Flask(__name__)

# --- Banco em Memória ---
leiloes_db = {}
proximo_id_leilao = 1
db_lock = threading.Lock() # Protege o acesso concorrente ao dicionário

# --- Publicação (Apenas Publisher) ---
def publicar_evento(routing_key: str, evento: dict):
    try:
        creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds))
        channel = conn.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
        
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
        conn.close()
    except Exception as e:
        print(f"Erro ao publicar evento: {e}")

# --- Agendamento de Ciclo de Vida ---
def agendar_leilao(id_leilao):
    try:
        with db_lock:
            leilao = leiloes_db.get(id_leilao)
        if not leilao: return

        agora = datetime.now(timezone.utc)
        
        # 1. Espera iniciar
        tempo_para_iniciar = (leilao['inicio'] - agora).total_seconds()
        if tempo_para_iniciar > 0:
            time.sleep(tempo_para_iniciar) # dorme até o início do leilão
        
        # 2. Inicia
        with db_lock: leilao['status'] = 'ativo'
        print(f"Leilão {id_leilao} INICIADO.")
        publicar_evento('leilao.iniciado', leilao)
        
        # 3. Espera finalizar
        agora = datetime.now(timezone.utc) 
        tempo_para_finalizar = (leilao['fim'] - agora).total_seconds()
        if tempo_para_finalizar > 0:
            time.sleep(tempo_para_finalizar)

        # 4. Finaliza
        with db_lock: leilao['status'] = 'encerrado'
        print(f"Leilão {id_leilao} FINALIZADO.")
        publicar_evento('leilao.finalizado', {"id_leilao": leilao['id_leilao']})

    except Exception as e:
        print(f"Erro na thread do leilão {id_leilao}: {e}")

# --- Endpoints REST ---

@app.route('/leiloes', methods=['POST'])
def criar_leilao():
    global proximo_id_leilao
    dados = request.json

    try:
        # Tratamento de fuso horário
        inicio_dt = datetime.fromisoformat(dados['inicio'].replace('Z', '+00:00'))
        fim_dt = datetime.fromisoformat(dados['fim'].replace('Z', '+00:00'))

        novo_leilao = {
            "id_leilao": proximo_id_leilao,
            "nome_produto": dados['nome_produto'],
            "descricao": dados['descricao'],
            "valor_inicial": float(dados['valor_inicial']),
            "valor_atual": float(dados['valor_inicial']), # Inicializa igual ao inicial
            "inicio": inicio_dt,
            "fim": fim_dt,
            "status": "agendado"
        }
        
        with db_lock:
            leiloes_db[novo_leilao['id_leilao']] = novo_leilao
            proximo_id_leilao += 1
        
        thread_leilao = threading.Thread(target=agendar_leilao, args=(novo_leilao['id_leilao'],))
        thread_leilao.start()
        
        return jsonify({"msg": "Leilão agendado", "id": novo_leilao['id_leilao']}), 201
        
    except Exception as e:
        return jsonify({"erro": str(e)}), 400

@app.route('/leiloes/ativos', methods=['GET'])
def consultar_leiloes_ativos():
    leiloes_ativos = []
    with db_lock:
        for leilao in leiloes_db.values():
            if leilao['status'] == 'ativo':
                leiloes_ativos.append({
                    "id_leilao": leilao['id_leilao'],
                    "nome_produto": leilao['nome_produto'],
                    "descricao": leilao['descricao'],
                    "valor_inicial": leilao['valor_inicial'],
                    "valor_atual": leilao['valor_atual'], # Retorna o valor atualizado
                    "inicio": leilao['inicio'].isoformat(),
                    "fim": leilao['fim'].isoformat(),
                })
    return jsonify(leiloes_ativos), 200

# Novo Endpoint para receber atualização do Gateway
@app.route('/leiloes/<int:id_leilao>', methods=['PATCH'])
def atualizar_valor_leilao(id_leilao):
    dados = request.json
    novo_valor = dados.get('valor')
    
    with db_lock:
        if id_leilao in leiloes_db:
            leiloes_db[id_leilao]['valor_atual'] = float(novo_valor)
            print(f" [REST] Valor do leilão {id_leilao} atualizado para R${novo_valor}")
            return jsonify({"status": "atualizado"}), 200
        else:
            return jsonify({"erro": "leilao nao encontrado"}), 404

if __name__ == '__main__':
    app.run(port=5001, debug=True, use_reloader=False)