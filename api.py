from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent
NLP_CLIN_DIR = ROOT_DIR / "nlp_clin"
if str(NLP_CLIN_DIR) not in sys.path:
    sys.path.insert(0, str(NLP_CLIN_DIR))

from src.run_pipeline_debug import run_pipeline_debug  # noqa: E402


class PipelineInput(BaseModel):
    text: str


app = FastAPI(title="Clinical NLP Debug API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/pipeline/debug")
def pipeline_debug(payload: PipelineInput) -> dict:
    try:
        return run_pipeline_debug(payload.text)
    except Exception as exc:  # pragma: no cover - minimal debug endpoint
        raise HTTPException(status_code=500, detail=str(exc)) from exc
