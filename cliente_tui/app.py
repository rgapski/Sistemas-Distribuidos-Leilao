# /cliente_tui/app.py

import pika
import json
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input, Button
from textual.containers import Horizontal, Vertical
from textual.worker import get_current_worker
from textual import work, on

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- Configurações ---
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'user'
RABBITMQ_PASS = 'password'
LEILOES_QUEUE = 'leilao_iniciado'
LANCES_QUEUE = 'lance_realizado'
USUARIO_ID = 'cliente_alpha'  # Identificador do nosso cliente
PRIVATE_KEY_FILE = f'{USUARIO_ID}_private_key.pem'

class LeilaoConsumerApp(App):
    """Uma aplicação Textual para participar de leilões em tempo real."""

    BINDINGS = [("d", "toggle_dark", "Alternar Modo Escuro")]
    CSS_PATH = "app.css"

    def __init__(self):
        super().__init__()
        self.leiloes_ativos = {}
        self.inscricoes = set()  # Conjunto para guardar leilões ativos
        # Carrega a chave privada ao iniciar
        try:
            with open(PRIVATE_KEY_FILE, "rb") as key_file:
                self.private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                )
        except FileNotFoundError:
            print(f"ERRO: Chave privada '{PRIVATE_KEY_FILE}' não encontrada. Execute 'gerar_chaves.py' primeiro.")
            self.exit()
            
    def compose(self) -> ComposeResult:
        """Cria os widgets da interface."""
        yield Header(show_clock=True)
        with Vertical(id="app-grid"):
            # MUDANÇA 2: Usar RichLog com markup=True
            yield RichLog(id="log_leiloes", auto_scroll=True, markup=True, highlight=True)
            with Horizontal(id="input-container"):
                yield Input(placeholder="ID do Leilão", id="input_leilao_id")
                yield Input(placeholder="Valor do Lance", id="input_valor")
                yield Button("Dar Lance", variant="success", id="btn_lance")
        yield Footer()

    def on_mount(self) -> None:
        """Inicia os consumidores de mensagens."""
        self.log_widget = self.query_one("#log_leiloes")
        # MUDANÇA 3: Usar .write()
        self.log_widget.write("Cliente TUI iniciado. Carregando...")
        self.consume_leiloes()

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
        leilao_id_str = self.query_one("#input_leilao_id").value
        valor_str = self.query_one("#input_valor").value

        if not leilao_id_str or not valor_str:
            self.log_widget.write("[bold red]ERRO: Preencha o ID do Leilão e o Valor.[/bold red]")
            return

        try:
            leilao_id = int(leilao_id_str)
            valor = float(valor_str)
        except ValueError:
            self.log_widget.write("[bold red]ERRO: ID do Leilão e Valor devem ser números.[/bold red]")
            return
        
        if leilao_id not in self.inscricoes:
            self.consume_notificacoes(leilao_id)
            self.inscricoes.add(leilao_id)

        dados_lance = {
            "id_leilao": leilao_id,
            "id_usuario": USUARIO_ID,
            "valor": valor
        }
        
        assinatura_hex = self.assinar_mensagem(dados_lance)
        
        payload_final = {
            "dados": dados_lance,
            "assinatura": assinatura_hex
        }

        # Publicar no RabbitMQ (idealmente, isso também deveria ser em um worker)
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=credentials))
            channel = connection.channel()
            channel.queue_declare(queue=LANCES_QUEUE, durable=True)
            channel.basic_publish(
                exchange='',
                routing_key=LANCES_QUEUE,
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
    def consume_leiloes(self) -> None:
        """Consome a fila 'leilao_iniciado'."""
        worker = get_current_worker()
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
            channel = connection.channel()
            channel.queue_declare(queue=LEILOES_QUEUE, durable=True)

            def callback(ch, method, properties, body):
                leilao = json.loads(body.decode())
                self.leiloes_ativos[leilao['id_leilao']] = leilao
                
                # Melhorando a formatação da mensagem
                log_message = f"""
[green]Novo Leilão Iniciado![/green]
  [b]ID:[/b] {leilao.get('id_leilao')}
  [b]Descrição:[/b] {leilao.get('descricao')}
--------------------"""
                
                if not worker.is_cancelled:
                    self.call_from_thread(self.log_widget.write, log_message)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=LEILOES_QUEUE, on_message_callback=callback)
            
            self.call_from_thread(self.log_widget.write, f"[*] Conectado à fila '{LEILOES_QUEUE}'.")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            self.call_from_thread(self.log_widget.write, f"[bold red]Erro de conexão (Leilões): {e}[/bold red]")
            self.call_from_thread(self.log_widget.write, f"[bold red]Erro de conexão (Leilões): {e}[/bold red]")

    @work(thread=True)
    def consume_notificacoes(self, leilao_id: int) -> None:
        q_name = f"leilao_{leilao_id}"
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=credentials))
            channel = connection.channel()
            channel.queue_declare(queue=q_name, durable=True)
            def callback(ch, method, properties, body):
                notificacao = json.loads(body.decode()); log_message = ""
                if 'vencedor' in notificacao: # Mensagem de vencedor
                    log_message = f"[bold magenta]Leilão {leilao_id} Encerrado![/bold magenta]\n  [b]Vencedor:[/b] {notificacao['vencedor']}\n  [b]Valor Final:[/b] R$ {notificacao['valor']:.2f}\n--------------------"
                else: # Mensagem de novo lance
                    log_message = f"[cyan]Lance no leilão {leilao_id}![/cyan]\n  [b]Usuário:[/b] {notificacao['id_usuario']} | [b]Valor:[/b] R$ {notificacao['valor']:.2f}\n--------------------"
                self.call_from_thread(self.log_widget.write, log_message)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            channel.basic_consume(queue=q_name, on_message_callback=callback)
            self.call_from_thread(self.log_widget.write, f"[*] Inscrito no leilão {leilao_id}.")
            channel.start_consuming()
        except Exception as e:
            self.call_from_thread(self.log_widget.write, f"[bold red]Erro (notificações {leilao_id}): {e}[/bold red]")

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark

if __name__ == "__main__":
    app = LeilaoConsumerApp()
    app.run()
