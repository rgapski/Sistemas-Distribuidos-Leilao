# /microservices/simulador-pagamento/simulador-pagamento.py

import time
import requests
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Configuração ---
# O endpoint para onde este simulador enviará o status (o webhook do MS Pagamento)
WEBHOOK_URL = "http://127.0.0.1:5003/webhook/status" # Assumindo que o MS Pagamento rodará na porta 5003

proximo_id_transacao = 1000

def enviar_webhook_assincrono(dados_webhook):
    """
    Esta função roda em uma thread separada para simular
    o processamento assíncrono e enviar o webhook.
    """
    global proximo_id_transacao
    
    print(f"[Simulador] Processando transação {dados_webhook['id_transacao']}...")
    
    # 1. Simula o tempo de processamento do pagamento (ex: 5 segundos)
    time.sleep(5) 
    
    # 2. Decide aleatoriamente se o pagamento foi aprovado ou recusado
    # Neste exemplo, vamos aprovar por padrão para facilitar o teste.
    dados_webhook["status"] = "aprovado" #
    
    print(f"[Simulador] Pagamento {dados_webhook['id_transacao']} {dados_webhook['status']}. Enviando webhook para {WEBHOOK_URL}...")
    
    # 3. Envia a notificação de webhook via HTTP POST
    try:
        requests.post(WEBHOOK_URL, json=dados_webhook)
        print(f"[Simulador] Webhook para {dados_webhook['id_transacao']} enviado com sucesso.")
    except requests.exceptions.ConnectionError:
        print(f"[Simulador] ERRO: Não foi possível conectar ao MS Pagamento em {WEBHOOK_URL}. O serviço está rodando?")

# --- Endpoint REST (Recebe o pedido do MS Pagamento) ---

@app.route('/iniciar_pagamento', methods=['POST'])
def iniciar_pagamento():
    """
    Recebe uma requisição REST do MS Pagamento para criar uma transação.
    Retorna imediatamente um link de pagamento.
    """
    global proximo_id_transacao
    dados = request.json # Deve conter 'valor', 'id_vencedor', 'id_leilao'
    
    # Cria uma nova transação
    id_transacao = proximo_id_transacao
    proximo_id_transacao += 1
    
    print(f"[Simulador] Recebido pedido de pagamento de R${dados.get('valor')} para o leilão {dados.get('id_leilao')}.")
    
    # 1. Gera um link de pagamento fictício
    link_pagamento = f"http://simulador.com/pagar/{id_transacao}" #
    
    # 2. Prepara os dados para o webhook que será enviado DEPOIS
    dados_webhook = {
        "id_transacao": id_transacao,
        "id_leilao": dados.get('id_leilao'),
        "id_comprador": dados.get('id_vencedor'), #
        "valor": dados.get('valor'), #
        "status": "pendente" # Será atualizado na thread
    }
    
    # 3. Inicia a thread que enviará o webhook assíncrono
    thread_webhook = threading.Thread(target=enviar_webhook_assincrono, args=(dados_webhook,))
    thread_webhook.start()
    
    # 4. Retorna o link de pagamento IMEDIATAMENTE para o MS Pagamento
    print(f"[Simulador] Retornando link de pagamento: {link_pagamento}")
    return jsonify({"link_pagamento": link_pagamento, "id_transacao": id_transacao}), 201

# --- Ponto de entrada ---
if __name__ == '__main__':
    print("[*] Iniciando Simulador de Pagamento Externo (porta 5004)...")
    app.run(port=5004, debug=True, use_reloader=False)