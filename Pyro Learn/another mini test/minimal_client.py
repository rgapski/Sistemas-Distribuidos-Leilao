import Pyro5.api
import time

proxy = Pyro5.api.Proxy("PYRONAME:minimal.server")

print("Iniciando teste de chamadas @oneway...")
for i in range(10):
    start_time = time.time()
    proxy.ping() # Chamada @oneway
    duration = (time.time() - start_time) * 1000
    print(f"Chamada {i+1} demorou {duration:.2f} ms")
    time.sleep(1)