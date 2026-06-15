# security.py
from cryptography.fernet import Fernet
import bcrypt
import jwt
import paramiko
from passlib.context import CryptContext

# Configuración de Passlib para hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# === Cifrado de archivos con Fernet ===
def cifra_archivo(ruta):
    """Cifra un archivo con Fernet y guarda la versión cifrada."""
    try:
        key = Fernet.generate_key()
        fernet = Fernet(key)
        with open(ruta, "rb") as f:
            data = f.read()
        cifrado = fernet.encrypt(data)
        salida = ruta + ".cifrado"
        with open(salida, "wb") as f:
            f.write(cifrado)
        return f"Archivo cifrado en {salida}\nClave: {key.decode()}"
    except Exception as e:
        return f"Error al cifrar archivo: {e}"

# === Hashing de contraseñas con bcrypt ===
def hash_password(password: str):
    """Genera un hash seguro de una contraseña usando bcrypt."""
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    except Exception as e:
        return f"Error al generar hash: {e}"

def verify_password(password: str, hashed: str):
    """Verifica una contraseña contra su hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception as e:
        return f"Error al verificar contraseña: {e}"

# === Hashing con Passlib ===
def passlib_hash(password: str):
    """Genera un hash usando Passlib."""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        return f"Error en Passlib hash: {e}"

def passlib_verify(password: str, hashed: str):
    """Verifica contraseña con Passlib."""
    try:
        return pwd_context.verify(password, hashed)
    except Exception as e:
        return f"Error en Passlib verify: {e}"

# === Tokens JWT ===
def crear_jwt(payload: dict, secret: str = "mi_clave_secreta"):
    """Crea un token JWT con un payload dado."""
    try:
        token = jwt.encode(payload, secret, algorithm="HS256")
        return token
    except Exception as e:
        return f"Error al crear JWT: {e}"

def verificar_jwt(token: str, secret: str = "mi_clave_secreta"):
    """Verifica y decodifica un token JWT."""
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        return decoded
    except Exception as e:
        return f"Error al verificar JWT: {e}"

# === Ejemplo con Paramiko (SSH) ===
def paramiko_demo(host="localhost", user="usuario", password="clave"):
    """Ejemplo simple de conexión SSH con Paramiko (no ejecuta comandos reales)."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        # No conectamos realmente, solo mostramos inicialización
        return "Cliente SSH inicializado con Paramiko."
    except Exception as e:
        return f"Error en Paramiko demo: {e}"
