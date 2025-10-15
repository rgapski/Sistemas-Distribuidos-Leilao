import Pyro5.api
import time

@Pyro5.api.expose
class Server:
    @Pyro5.api.oneway
    def ping(self):
        print(f"Ping recebido às {time.time()}")

daemon = Pyro5.api.Daemon(host="127.0.0.1")
uri = daemon.register(Server, "minimal.server")
print(f"Servidor pronto. URI = {uri}")
daemon.requestLoop()