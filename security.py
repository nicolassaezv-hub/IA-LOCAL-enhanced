try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    Fernet = None
    HAS_CRYPTOGRAPHY = False

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    bcrypt = None
    HAS_BCRYPT = False

try:
    import jwt
    HAS_JWT = True
except ImportError:
    jwt = None
    HAS_JWT = False

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    paramiko = None
    HAS_PARAMIKO = False

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    HAS_PASSLIB = True
except ImportError:
    CryptContext = None
    pwd_context = None
    HAS_PASSLIB = False


def cifra_archivo(ruta):
    if not HAS_CRYPTOGRAPHY:
        return "cryptography no disponible. Instale: pip install cryptography"
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


def hash_password(password: str):
    if not HAS_BCRYPT:
        return "bcrypt no disponible. Instale: pip install bcrypt"
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    except Exception as e:
        return f"Error al generar hash: {e}"


def verify_password(password: str, hashed: str):
    if not HAS_BCRYPT:
        return "bcrypt no disponible. Instale: pip install bcrypt"
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception as e:
        return f"Error al verificar contraseña: {e}"


def passlib_hash(password: str):
    if not HAS_PASSLIB:
        return "passlib no disponible. Instale: pip install passlib"
    try:
        return pwd_context.hash(password)
    except Exception as e:
        return f"Error en Passlib hash: {e}"


def passlib_verify(password: str, hashed: str):
    if not HAS_PASSLIB:
        return "passlib no disponible. Instale: pip install passlib"
    try:
        return pwd_context.verify(password, hashed)
    except Exception as e:
        return f"Error en Passlib verify: {e}"


def crear_jwt(payload: dict, secret: str = "mi_clave_secreta"):
    if not HAS_JWT:
        return "PyJWT no disponible. Instale: pip install PyJWT"
    try:
        token = jwt.encode(payload, secret, algorithm="HS256")
        return token
    except Exception as e:
        return f"Error al crear JWT: {e}"


def verificar_jwt(token: str, secret: str = "mi_clave_secreta"):
    if not HAS_JWT:
        return "PyJWT no disponible. Instale: pip install PyJWT"
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        return decoded
    except Exception as e:
        return f"Error al verificar JWT: {e}"


def paramiko_demo(host="localhost", user="usuario", password="clave"):
    if not HAS_PARAMIKO:
        return "paramiko no disponible. Instale: pip install paramiko"
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return "Cliente SSH inicializado con Paramiko."
    except Exception as e:
        return f"Error en Paramiko demo: {e}"
