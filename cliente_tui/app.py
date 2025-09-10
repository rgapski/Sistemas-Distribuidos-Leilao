# /cliente_tui/app.py

import pika
import json
import argparse
from pathlib import Path
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input, Button, Static
from textual.containers import Horizontal, Vertical
from textual import work, on

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
EXCHANGE_NAME = 'leilao_topic_exchange'
LANCES_ROUTING_KEY = 'lance.realizado'  # Chave para publicar lances na exchange
USUARIO_ID = 'cliente_alpha'  # Identificador do nosso cliente
PRIVATE_KEY_FILE = f'{USUARIO_ID}_private_key.pem'
SCRIPT_DIR = Path(__file__).parent
CSS_PATH = SCRIPT_DIR / "app.css"

class LeilaoConsumerApp(App):
    """Uma aplicação Textual para participar de leilões em tempo real."""

    BINDINGS = [("d", "toggle_dark", "Alternar Modo Escuro")]
    CSS_PATH = "app.css"

    def __init__(self, usuario_id: str):
        super().__init__()
        self.usuario_id = usuario_id # Armazena o ID do usuário na instância
        self.inscricoes = set()  # Conjunto para guardar leilões que o cliente participa
        private_key_file = SCRIPT_DIR / f'{self.usuario_id}_private_key.pem'
        try:
            with open(private_key_file, "rb") as key_file:
                self.private_key = serialization.load_pem_private_key(key_file.read(), password=None)
        except FileNotFoundError:
            print(f"ERRO: Chave privada para o usuário '{self.usuario_id}' não encontrada em '{private_key_file}'.")
            print("Verifique se você executou 'gerar_chaves.py' para este usuário.")
            input("Pressione Enter para sair.")
            self.exit()
            
    def compose(self) -> ComposeResult:
        """Cria os widgets da interface."""
        yield Header(show_clock=True) 
        yield Static(f"Usuário: [b]{self.usuario_id}[/b]", id="user-display") 
        with Vertical(id="app-grid"):
            yield RichLog(id="log_leiloes", auto_scroll=True, markup=True, highlight=True)
            with Horizontal(id="input-container"):
                yield Input(placeholder="ID do Leilão", id="input_leilao_id", type="integer")
                yield Input(placeholder="Valor do Lance", id="input_valor", type="number")
                yield Button("Dar Lance", variant="success", id="btn_lance")
        yield Footer()

    def on_mount(self) -> None:
        """Inicia os consumidores de mensagens."""
        self.log_widget = self.query_one("#log_leiloes")
        self.log_widget.write("Cliente TUI iniciado. Aguardando leilões...")
        self.consume_leiloes_iniciados()

    def assinar_mensagem(self, mensagem: dict) -> str:
        """Assina uma mensagem (dicionário) com a chave privada e retorna a assinatura em hexadecimal."""
        mensagem_bytes = json.dumps(mensagem, sort_keys=True).encode('utf-8')
        assinatura = self.private_key.sign(
            mensagem_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return assinatura.hex()

    @on(Button.Pressed, "#btn_lance")
    def dar_lance(self) -> None:
        """Chamado quando o botão 'Dar Lance' é pressionado."""
        leilao_id_input = self.query_one("#input_leilao_id")
        valor_input = self.query_one("#input_valor")
        leilao_id_str = leilao_id_input.value
        valor_str = valor_input.value

        if not leilao_id_str or not valor_str:
            self.log_widget.write("[bold red]ERRO: Preencha o ID do Leilão e o Valor.[/bold red]")
            return

        try:
            leilao_id = int(leilao_id_str)
            valor = float(valor_str)
        except ValueError:
            self.log_widget.write("[bold red]ERRO: ID do Leilão e Valor devem ser números válidos.[/bold red]")
            return
        
        # Se for o primeiro lance neste leilão, inscreve-se para notificações
        if leilao_id not in self.inscricoes:
            self.consume_notificacoes(leilao_id)
            self.inscricoes.add(leilao_id)

        dados_lance = {
            "id_leilao": leilao_id,
            "id_usuario": self.usuario_id,
            "valor": valor,
        }
        
        assinatura_hex = self.assinar_mensagem(dados_lance)
        
        payload_final = {
            "dados": dados_lance,
            "assinatura": assinatura_hex
        }

        # Publica o lance na exchange principal
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=credentials))
            channel = connection.channel()
            
            # Garante que a exchange existe e publica a mensagem com a routing key correta
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=LANCES_ROUTING_KEY,
                body=json.dumps(payload_final),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            connection.close()
            self.log_widget.write(f"[yellow]Lance de R${valor:.2f} enviado para o leilão {leilao_id}. Aguardando validação...[/yellow]")
            leilao_id_input.value = ""
            valor_input.value = ""
            leilao_id_input.focus()
        except pika.exceptions.AMQPConnectionError as e:
            self.log_widget.write(f"[bold red]Erro ao enviar lance: Não foi possível conectar ao RabbitMQ. {e}[/bold red]")

    @work(exclusive=True, thread=True)
    def consume_leiloes_iniciados(self) -> None:
        """Consome da exchange os eventos de leilão iniciado."""
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
            result = channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue

            # CORREÇÃO: Usando a binding key com padrão de pontos
            binding_key = 'leilao.iniciado'
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=binding_key)
            
            def callback(ch, method, properties, body):
                leilao = json.loads(body.decode())
                
                # MELHORIA: Formatação da data para melhor leitura
                try:
                    fim_dt = datetime.fromisoformat(leilao['fim'])
                    fim_formatado = fim_dt.strftime('%d/%m/%Y %H:%M:%S')
                except (ValueError, KeyError):
                    fim_formatado = leilao.get('fim', 'Data inválida')
                
                log_message = f"[green]Leilão {leilao['id_leilao']} Iniciado: {leilao['descricao']}[/green]\n  Fim: {fim_formatado}\n--------------------"
                self.call_from_thread(self.log_widget.write, log_message)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            self.call_from_thread(self.log_widget.write, f"[*] Escutando por eventos de '{binding_key}'.")
            channel.start_consuming()

        except Exception as e:
            self.call_from_thread(self.log_widget.write, f"[bold red]Erro (worker leilões): {e}[/bold red]")

    @work(thread=True)
    def consume_notificacoes(self, leilao_id: int) -> None:
        """
        Cria um consumidor para TODAS as notificações de um leilão específico
        usando uma inscrição de tópico com wildcard.
        """
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=credentials))
            channel = connection.channel()

            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic')
            result = channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue

            binding_key = f"notificacao.*.{leilao_id}"
            
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=binding_key)
            
            def callback(ch, method, body):
                notificacao = json.loads(body.decode())
                log_message = ""
                
                # Usamos a routing_key para saber que tipo de notificação é
                if method.routing_key.startswith('notificacao.vencedor'):
                    # Formata a mensagem de vencedor
                    if notificacao['vencedor'] == self.usuario_id:
                        log_message = f"[bold green]Parabéns! Você venceu o leilão {leilao_id}![/bold green]\n  [b]Valor Final:[/b] R$ {notificacao['valor']:.2f}\n--------------------"
                    else:
                        log_message = f"[bold magenta]Leilão {leilao_id} Encerrado![/bold magenta]\n  [b]Vencedor:[/b] {notificacao['vencedor']}\n  [b]Valor Final:[/b] R$ {notificacao['valor']:.2f}\n--------------------"

                else: # Assume que é uma notificação de lance
                    # Se o lance validado for do próprio usuário, mostra uma confirmação especial
                    if notificacao['id_usuario'] == self.usuario_id:
                        log_message = f"[bold green]Seu lance de R$ {notificacao['valor']:.2f} foi aceito como o mais alto no leilão {leilao_id}![/bold green]\n--------------------"
                    else:
                    # Se for de outro usuário, mostra a notificação padrão
                        log_message = f"[cyan]Lance no leilão {leilao_id}![/cyan]\n  [b]Usuário:[/b] {notificacao['id_usuario']} | [b]Valor:[/b] R$ {notificacao['valor']:.2f}\n--------------------"
                
                self.call_from_thread(self.log_widget.write, log_message)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            self.call_from_thread(self.log_widget.write, f"[*] Inscrito para notificações do leilão {leilao_id} (Padrão: {binding_key}).")
            channel.start_consuming()
        except Exception as e:
            self.call_from_thread(self.log_widget.write, f"[bold red]Erro (notificações {leilao_id}): {e}[/bold red]")

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente TUI para o sistema de leilão.")
    parser.add_argument("usuario", type=str, help="O ID do usuário para este cliente (ex: cliente_alpha).")
    args = parser.parse_args()
    app = LeilaoConsumerApp(usuario_id=args.usuario)
    app.run()