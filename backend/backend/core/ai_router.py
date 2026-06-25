#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Router IA — Endpoints Groq avec fallback modèles et message IA indisponible.
"""

import os, sys
sys.path.insert(1, os.path.dirname(os.path.abspath(os.path.join(__file__, "..", ".."))))
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional, List
from backend.utils.limiter import limiter
from backend.core.db_manager import GoalStep, StepOrigin
from backend.core.router import get_db_manager, _verify_pin
from backend.core.llm_manager import get_llm_manager, IAUnavailableError

ai_router = APIRouter(prefix="/ai")

IA_UNAVAILABLE = {"ia_indisponible": True, "message": "L'IA se repose un peu ☕ Réessaie dans quelques minutes."}

# =============================================================================
# Pydantic models
# =============================================================================

class GenerateStepsData(BaseModel):
    pin: str
    goal_id: int

class GenerateTitleData(BaseModel):
    pin: str
    description: str

class SortBrainDumpData(BaseModel):
    pin: str
    items: List[dict]

class GenerateWhyData(BaseModel):
    pin: str
    objectif_titre: str
    objectif_description: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatData(BaseModel):
    pin: str
    messages: List[ChatMessage]

# =============================================================================
# Endpoints
# =============================================================================

@ai_router.post("/generate_steps")
@limiter.limit("20/minute")
async def _generate_steps(request: Request, data: GenerateStepsData):
    try:
        db  = get_db_manager()
        llm = get_llm_manager()
        _verify_pin(data.pin, db)
        goal = db.get_goal_by_id(data.goal_id)
        if not goal:
            raise HTTPException(status_code=404, detail="GOAL_NOT_FOUND")
        steps_data = llm.generate_goal_steps(
            description=goal.description,
            date_limite=str(goal.date_limite),
            titre=goal.titre
        )
        saved = []
        for i, s in enumerate(steps_data):
            step = GoalStep(goal_id=goal.id, titre=s.get("titre", f"Étape {i+1}"),
                            description=s.get("description"), ordre=i, origine=StepOrigin.ia)
            sv = db.add_step_to_goal(step)
            if sv:
                saved.append(db.to_dict(sv))
        goal_ref = db.get_goal_by_id(goal.id)
        return {"steps": saved, "goal": db.to_dict(goal_ref) if goal_ref else None}
    except IAUnavailableError:
        return IA_UNAVAILABLE
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ai_router.post("/generate_title")
@limiter.limit("20/minute")
async def _generate_title(request: Request, data: GenerateTitleData):
    try:
        db  = get_db_manager()
        llm = get_llm_manager()
        _verify_pin(data.pin, db)
        titre = llm.generate_goal_title(data.description)
        return {"titre": titre}
    except IAUnavailableError:
        return IA_UNAVAILABLE
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ai_router.post("/braindump_sort")
@limiter.limit("10/minute")
async def _braindump_sort(request: Request, data: SortBrainDumpData):
    try:
        db  = get_db_manager()
        llm = get_llm_manager()
        _verify_pin(data.pin, db)
        if not data.items:
            return {"sorted": []}
        return {"sorted": llm.sort_brain_dump(data.items)}
    except IAUnavailableError:
        return IA_UNAVAILABLE
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ai_router.post("/generate_why")
@limiter.limit("20/minute")
async def _generate_why(request: Request, data: GenerateWhyData):
    try:
        db  = get_db_manager()
        llm = get_llm_manager()
        _verify_pin(data.pin, db)
        return llm.generate_why_and_advantages(data.objectif_titre, data.objectif_description)
    except IAUnavailableError:
        return IA_UNAVAILABLE
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ai_router.post("/chat")
@limiter.limit("30/minute")
async def _chat(request: Request, data: ChatData):
    try:
        db  = get_db_manager()
        llm = get_llm_manager()
        _verify_pin(data.pin, db)

        # Récupère le contexte de l'utilisatrice
        from datetime import date
        cfg   = db.get_config()
        goals = db.get_active_goals()
        tasks = db.get_tasks_by_date(date.today())

        context = {
            "capital_points": cfg.capital_points if cfg else 0,
            "niveau_label":   cfg.niveau_label if cfg else "",
            "goals": [{"titre": g.titre, "description": g.description, "date_limite": str(g.date_limite)} for g in goals],
            "tasks": [{"titre": t.titre, "heure_debut": t.heure_debut, "heure_fin": t.heure_fin, "statut": t.statut} for t in tasks],
        }

        messages = [{"role": m.role, "content": m.content} for m in data.messages]
        reply = llm.chat(messages, context)
        return {"reply": reply}
    except IAUnavailableError:
        return {**IA_UNAVAILABLE, "reply": "Je suis temporairement indisponible ☕ Réessaie dans quelques minutes."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
