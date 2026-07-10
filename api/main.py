import os
import json
import redis
from contextlib import asynccontextmanager
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
redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# --- CICLO DE VIDA ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="API Backend - CI/CD 4", lifespan=lifespan)

def get_session():
    with Session(engine) as session:
        yield session

# --- RUTAS DE LA API ---
@app.post("/usuarios/")
def crear_usuario(usuario: Usuario, session: Session = Depends(get_session)):
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    redis_client.delete("lista_usuarios")
    return usuario

@app.get("/usuarios/")
def leer_usuarios(session: Session = Depends(get_session)):
    cached_users = redis_client.get("lista_usuarios")
    if cached_users:
        return {"origen": "⚡ Redis (Memoria RAM)", "datos": json.loads(cached_users)}

    usuarios = session.exec(select(Usuario)).all()
    usuarios_dict = [u.model_dump() for u in usuarios]
    redis_client.setex("lista_usuarios", 60, json.dumps(usuarios_dict))
    return {"origen": "🗄️ PostgreSQL (Disco)", "datos": usuarios}