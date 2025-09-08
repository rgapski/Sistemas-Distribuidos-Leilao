# /microservices/ms_lance/main.py

import pika
import json
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
LANCES_QUEUE = 'lance_realizado'
PUBLIC_KEYS_DIR = '.' # O diretório onde as chaves públicas estão

# --- Lógica de Negócio ---
chaves_publicas = {}

def carregar_chaves_publicas():
    """Carrega todas as chaves públicas .pem do diretório configurado."""
    print("Carregando chaves públicas...")
    for filename in os.listdir(PUBLIC_KEYS_DIR):
        if filename.endswith("_public_key.pem"):
            usuario_id = filename.replace("_public_key.pem", "")
            try:
                with open(os.path.join(PUBLIC_KEYS_DIR, filename), "rb") as key_file:
                    chaves_publicas[usuario_id] = serialization.load_pem_public_key(
                        key_file.read()
                    )
                print(f"  - Chave de '{usuario_id}' carregada.")
            except Exception as e:
                print(f"  - Falha ao carregar chave de '{usuario_id}': {e}")

def verificar_lance(payload: dict) -> bool:
    """Verifica a assinatura digital de um lance."""
    try:
        dados = payload['dados']
        assinatura_hex = payload['assinatura']
        assinatura_bytes = bytes.fromhex(assinatura_hex)
        
        usuario_id = dados['id_usuario']
        
        # 1. Encontrar a chave pública do usuário
        public_key = chaves_publicas.get(usuario_id)
        if not public_key:
            print(f"  [!] Assinatura inválida: Chave pública para '{usuario_id}' não encontrada.")
            return False
            
        # 2. Preparar a mensagem original
        mensagem_bytes = json.dumps(dados, sort_keys=True).encode('utf-8')

        # 3. Verificar a assinatura
        public_key.verify(
            assinatura_bytes,
            mensagem_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        print("  [✓] Assinatura VÁLIDA.")
        return True

    except InvalidSignature:
        print("  [!] Assinatura INVÁLIDA: A assinatura não corresponde aos dados.")
        return False
    except (KeyError, ValueError) as e:
        print(f"  [!] Formato de mensagem inválido: {e}")
        return False

# --- Conexão RabbitMQ ---
def main():
    carregar_chaves_publicas()
    
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=LANCES_QUEUE, durable=True)

        def callback(ch, method, properties, body):
            print(f"\n[x] Lance recebido de '{LANCES_QUEUE}':")
            payload = json.loads(body.decode())
            print(json.dumps(payload, indent=2))
            
            # TODO: Aqui entrará a lógica completa de validação (leilão ativo, valor maior, etc.)
            # Por enquanto, apenas verificamos a assinatura.
            if verificar_lance(payload):
                # Se for válido, futuramente publicaremos em 'lance_validado'
                print("  --> Lance OK. (Próximo passo: publicar validação)")
            else:
                print("  --> Lance Descartado.")
                
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=LANCES_QUEUE, on_message_callback=callback)

        print(f'[*] MS Lance aguardando lances na fila "{LANCES_QUEUE}". Para sair, pressione CTRL+C')
        channel.start_consuming()
    
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Erro ao conectar ao RabbitMQ: {e}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrompido')
        exit(0)