# /cliente_tui/gerar_chaves.py

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def gerar_e_salvar_chaves(usuario_id: str):
    """Gera um par de chaves RSA e as salva em arquivos PEM."""
    
    # Gera a chave privada
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Serializa a chave privada para o formato PEM
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Salva a chave privada em um arquivo
    with open(f"{usuario_id}_private_key.pem", "wb") as f:
        f.write(pem_private)

    # Obtém a chave pública correspondente
    public_key = private_key.public_key()

    # Serializa a chave pública para o formato PEM
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Salva a chave pública em um arquivo
    with open(f"{usuario_id}_public_key.pem", "wb") as f:
        f.write(pem_public)
        
    print(f"Chaves para '{usuario_id}' geradas com sucesso!")
    print(f" - Chave Privada: {usuario_id}_private_key.pem")
    print(f" - Chave Pública:  {usuario_id}_public_key.pem")

if __name__ == "__main__":
    # Vamos criar chaves para um usuário chamado 'cliente_alpha'
    gerar_e_salvar_chaves("cliente_alpha")