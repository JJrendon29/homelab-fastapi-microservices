import os
import json
import redis
from fastapi import FastAPI, Depends
from sqlmodel import Field, Session, SQLModel, create_engine, select

# --- ESTRUCTURA DE LA BD ---
class Usuario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    especialidad: str

# --- CONEXIONES ---
db_url = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(db_url)

# Conexión a Redis usando la variable de tu docker-compose
redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

app = FastAPI(title="API Backend - Alta Concurrencia")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

def get_session():
    with Session(engine) as session:
        yield session

# --- RUTAS DE LA API ---

@app.post("/usuarios/")
def crear_usuario(usuario: Usuario, session: Session = Depends(get_session)):
    # 1. Guardamos el nuevo usuario en PostgreSQL
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    
    # 2. ¡Importante! Borramos la caché antigua de Redis porque los datos cambiaron
    redis_client.delete("lista_usuarios")
    
    return usuario

@app.get("/usuarios/")
def leer_usuarios(session: Session = Depends(get_session)):
    # 1. Intentamos leer los datos desde la memoria ultrarrápida de Redis
    cached_users = redis_client.get("lista_usuarios")
    
    if cached_users:
        # Si existen en Redis, los devolvemos de inmediato
        return {
            "origen": "⚡ Redis (Memoria RAM)", 
            "datos": json.loads(cached_users)
        }

    # 2. Si no existen en Redis, hacemos la consulta pesada a PostgreSQL
    usuarios = session.exec(select(Usuario)).all()
    
    # 3. Preparamos los datos y guardamos una copia en Redis por 60 segundos
    usuarios_dict = [u.model_dump() for u in usuarios]
    redis_client.setex("lista_usuarios", 60, json.dumps(usuarios_dict))
    
    return {
        "origen": "🗄️ PostgreSQL (Disco)", 
        "datos": usuarios
    }