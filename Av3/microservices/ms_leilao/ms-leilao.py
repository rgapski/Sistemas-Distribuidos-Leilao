# /microservices/ms_leilao/ms-leilao.py

import pika
import json
import time
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone # <--- ADICIONADO timezone

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'

app = Flask(__name__)

# --- Banco em Memória ---
leiloes_db = {}
proximo_id_leilao = 1

# --- Publicação ---
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

# --- Agendamento ---
def agendar_leilao(id_leilao):
    try:
        leilao = leiloes_db.get(id_leilao)
        if not leilao: return
        agora = datetime.now(timezone.utc)
        
        # 1. Espera iniciar
        tempo_para_iniciar = (leilao['inicio'] - agora).total_seconds()
        if tempo_para_iniciar > 0:
            print(f"Leilão {id_leilao} aguardando {tempo_para_iniciar:.1f}s para iniciar.")
            time.sleep(tempo_para_iniciar)
        
        # 2. Inicia
        leilao['status'] = 'ativo'
        print(f"Leilão {id_leilao} INICIADO.")
        publicar_evento('leilao.iniciado', leilao)
        
        # 3. Espera finalizar
        # Recalcula 'agora' porque o tempo passou
        agora = datetime.now(timezone.utc) 
        tempo_para_finalizar = (leilao['fim'] - agora).total_seconds()
        
        if tempo_para_finalizar > 0:
            print(f"Leilão {id_leilao} ativo por mais {tempo_para_finalizar:.1f}s.")
            time.sleep(tempo_para_finalizar)

        # 4. Finaliza
        leilao['status'] = 'encerrado'
        print(f"Leilão {id_leilao} FINALIZADO.")
        publicar_evento('leilao.finalizado', {"id_leilao": leilao['id_leilao']})

    except Exception as e:
        print(f"Erro na thread do leilão {id_leilao}: {e}")

# --- Endpoints ---
@app.route('/leiloes', methods=['POST'])
def criar_leilao():
    global proximo_id_leilao
    dados = request.json

    try:
        # O replace('Z', '+00:00') garante compatibilidade com python < 3.11 se necessário
        inicio_dt = datetime.fromisoformat(dados['inicio'].replace('Z', '+00:00'))
        fim_dt = datetime.fromisoformat(dados['fim'].replace('Z', '+00:00'))

        novo_leilao = {
            "id_leilao": proximo_id_leilao,
            "nome_produto": dados['nome_produto'],
            "descricao": dados['descricao'],
            "valor_inicial": float(dados['valor_inicial']),
            "inicio": inicio_dt,
            "fim": fim_dt,
            "status": "agendado"
        }
        
        leiloes_db[novo_leilao['id_leilao']] = novo_leilao
        proximo_id_leilao += 1
        
        # Inicia thread
        thread_leilao = threading.Thread(target=agendar_leilao, args=(novo_leilao['id_leilao'],))
        thread_leilao.start()
        
        return jsonify({"msg": "Leilão agendado", "id": novo_leilao['id_leilao']}), 201
        
    except Exception as e:
        print(e)
        return jsonify({"erro": str(e)}), 400

@app.route('/leiloes/ativos', methods=['GET'])
def consultar_leiloes_ativos():
    leiloes_ativos = []    
    for leilao in leiloes_db.values():
        if leilao['status'] == 'ativo':
            leiloes_ativos.append({
                "id_leilao": leilao['id_leilao'],
                "nome_produto": leilao['nome_produto'],
                "descricao": leilao['descricao'],
                "valor_inicial": leilao['valor_inicial'],
                "valor_atual": leilao.get('valor_inicial'),
                "inicio": leilao['inicio'].isoformat(),
                "fim": leilao['fim'].isoformat(),
            })
            
    return jsonify(leiloes_ativos), 200

if __name__ == '__main__':
    app.run(port=5001, debug=True, use_reloader=False)