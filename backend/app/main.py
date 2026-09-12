import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import init_db
from .routers import health, experiments

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="University Debate Evaluation API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router)
app.include_router(experiments.router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/questions")
def questions():
    from .dataset import QUESTIONS
    return QUESTIONS
