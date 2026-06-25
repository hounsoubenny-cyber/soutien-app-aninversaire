#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Router FastAPI - App de planning/objectifs/focus.
"""

import os, sys
sys.path.insert(1, os.path.dirname(os.path.abspath(os.path.join(__file__, "..", ".."))))
import bcrypt
from datetime import date as date_type
from fastapi import status, Request, APIRouter, HTTPException
from pydantic import BaseModel
from backend.api.api_config import LIMITE
from backend.utils.limiter import limiter
from backend.core.db_manager import (
    DBManager, AppConfig, Goal, GoalStep, Task, Tag,
    DoubtLog, FocusSession, PointsHistory, BrainDumpItem,
    TaskStatus, GoalStatus, PointsReason, BrainDumpStatus, StepOrigin,
    POINTS_GAIN_FOCUS
)
from typing import List, Optional

router = APIRouter()
db_manager = None


# =============================================================================
# Fonctions utilitaires
# =============================================================================

def get_db_manager() -> DBManager:
    """
    Fonction pour obtenir l'instance du gestionnaire de base de données.

    Returns
    -------
    DBManager
        L'instance du DBManager.
    """
    global db_manager
    if db_manager is None:
        db_manager = DBManager()
    return db_manager


def _verify_pin(pin: str, db_manager: DBManager):
    """
    Fonction utilitaire pour vérifier le PIN de l'app.

    Parameters
    ----------
    pin : str
        Le PIN fourni en clair.
    db_manager : DBManager
        Le gestionnaire de base de données.

    Raises
    ------
    HTTPException
        Si le PIN est incorrect ou non configuré.
    """
    cfg = db_manager.get_config()
    if not cfg or not cfg.pin_hash:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="PIN_NOT_CONFIGURED"
        )
    if not bcrypt.checkpw(pin.encode(), cfg.pin_hash.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="BAD_PIN"
        )


# =============================================================================
# Classes de données (Pydantic)
# =============================================================================

class SetPinData(BaseModel):
    pin: str


class CheckPinData(BaseModel):
    pin: str


class UpdateSettingsData(BaseModel):
    pin: str
    bloquer_notifications: Optional[bool] = None
    apps_bloquees: Optional[str] = None


class CreateTaskData(BaseModel):
    pin: str
    titre: str
    description: Optional[str] = None
    date: date_type
    heure_debut: str
    heure_fin: str
    report_auto: bool = False
    rappel_minutes_avant: Optional[int] = 10
    recurrence_jours: Optional[str] = None
    step_id: Optional[int] = None
    tag_noms: Optional[List[str]] = None
    force: bool = False


class UpdateTaskTimeData(BaseModel):
    pin: str
    task_id: int
    heure_debut: str
    heure_fin: str
    force: bool = False


class TaskIdData(BaseModel):
    pin: str
    task_id: int


class GetTasksByDateData(BaseModel):
    pin: str
    date: date_type


class GetTasksByRangeData(BaseModel):
    pin: str
    date_debut: date_type
    date_fin: date_type


class CreateGoalData(BaseModel):
    pin: str
    titre: Optional[str] = None
    description: str
    avantages: Optional[str] = None
    date_limite: date_type
    titre_genere_ia: bool = False
    steps_titres: Optional[List[str]] = None  # pour création rapide avec étapes déjà connues


class GoalIdData(BaseModel):
    pin: str
    goal_id: int


class AddStepData(BaseModel):
    pin: str
    goal_id: int
    titre: str
    description: Optional[str] = None
    origine: str = StepOrigin.manuelle.value
    date_limite: Optional[date_type] = None


class UpdateStepData(BaseModel):
    pin: str
    step_id: int
    titre: Optional[str] = None
    description: Optional[str] = None
    date_limite: Optional[date_type] = None


class StepIdData(BaseModel):
    pin: str
    step_id: int


class LogDoubtData(BaseModel):
    pin: str
    goal_id: Optional[int] = None
    note_libre: Optional[str] = None


class StartFocusData(BaseModel):
    pin: str
    duree_secondes: int
    points_mis_en_jeu: int = POINTS_GAIN_FOCUS


class UseFocusPauseData(BaseModel):
    pin: str
    focus_session_id: int
    secondes: int


class EndFocusData(BaseModel):
    pin: str
    focus_session_id: int
    succes: bool


class AddBrainDumpData(BaseModel):
    pin: str
    textes: List[str]


class ApplySortData(BaseModel):
    pin: str
    item_id: int
    statut: str  # "utile" ou "futile"
    explication_ia: Optional[str] = None
    dependances_ia: Optional[str] = None


class MoveBrainDumpData(BaseModel):
    pin: str
    item_id: int
    nouveau_statut: str


class LinkBrainDumpToGoalData(BaseModel):
    pin: str
    item_id: int
    goal_id: int


class PinOnlyData(BaseModel):
    pin: str


# =============================================================================
# PIN / Config
# =============================================================================

@router.post("/config/set_pin")
@limiter.limit(f"{LIMITE}/minute")
async def _set_pin(request: Request, data: SetPinData):
    """
    Endpoint pour définir le PIN de l'app (première configuration ou changement).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : SetPinData
        Le PIN en clair à hasher et enregistrer.

    Returns
    -------
    dict
        {"success": bool}
    """
    try:
        db_manager = get_db_manager()
        pin_hash = bcrypt.hashpw(data.pin.encode(), bcrypt.gensalt()).decode()
        success = db_manager.set_pin(pin_hash)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/config/check_pin")
@limiter.limit(f"{LIMITE}/minute")
async def _check_pin(request: Request, data: CheckPinData):
    """
    Endpoint pour vérifier le PIN saisi (ouverture de l'app).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : CheckPinData
        Le PIN en clair à vérifier.

    Returns
    -------
    dict
        {"valid": bool}
    """
    try:
        db_manager = get_db_manager()
        try:
            _verify_pin(data.pin, db_manager)
            return {"valid": True}
        except HTTPException as e:
            if e.detail == "PIN_NOT_CONFIGURED":
                r = await _set_pin(request, data)
                return {"valid": r["success"]}
            return {"valid": False}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/config/get")
@limiter.limit(f"{LIMITE}/minute")
async def _get_config(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer la configuration de l'app (capital, niveau, settings).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        La configuration de l'app.
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        cfg = db_manager.get_config()
        return db_manager.to_dict(cfg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/config/update_settings")
@limiter.limit(f"{LIMITE}/minute")
async def _update_settings(request: Request, data: UpdateSettingsData):
    """
    Endpoint pour mettre à jour les réglages (blocage notifications en focus).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : UpdateSettingsData
        Les réglages à mettre à jour.

    Returns
    -------
    dict
        La configuration mise à jour.
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        cfg = db_manager.update_settings(
            bloquer_notifications=data.bloquer_notifications,
            apps_bloquees=data.apps_bloquees
        )
        if not cfg:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="UPDATE_FAILED")
        return db_manager.to_dict(cfg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/points/history")
@limiter.limit(f"{LIMITE}/minute")
async def _get_points_history(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer l'historique des mouvements de points (courbe de progression).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"history": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        history = db_manager.get_points_history()
        return {"history": [db_manager.to_dict(h) for h in history]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


# =============================================================================
# Tasks (Planning journalier)
# =============================================================================

@router.post("/tasks/create")
@limiter.limit(f"{LIMITE}/minute")
async def _create_task(request: Request, data: CreateTaskData):
    """
    Endpoint pour créer une tâche dans le planning journalier.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : CreateTaskData
        Les données de la tâche à créer.

    Returns
    -------
    dict
        {"success": bool, "task": dict | None, "conflict": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)

        task = Task(
            titre=data.titre,
            description=data.description,
            date=data.date,
            heure_debut=data.heure_debut,
            heure_fin=data.heure_fin,
            report_auto=data.report_auto,
            rappel_minutes_avant=data.rappel_minutes_avant,
            recurrence_jours=data.recurrence_jours,
            step_id=data.step_id,
        )
        result = db_manager.create_task(task, tag_noms=data.tag_noms, force=data.force)
        return {
            "success": result["success"],
            "task": db_manager.to_dict(result["task"]) if result["task"] else None,
            "conflict": db_manager.to_dict(result["conflict"]) if result["conflict"] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/tasks/update_time")
@limiter.limit(f"{LIMITE}/minute")
async def _update_task_time(request: Request, data: UpdateTaskTimeData):
    """
    Endpoint pour modifier l'heure d'une tâche, avec détection de conflit.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : UpdateTaskTimeData
        L'ID de la tâche et les nouvelles heures.

    Returns
    -------
    dict
        {"success": bool, "task": dict | None, "conflict": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        result = db_manager.update_task_time(data.task_id, data.heure_debut, data.heure_fin, force=data.force)
        return {
            "success": result["success"],
            "task": db_manager.to_dict(result["task"]) if result["task"] else None,
            "conflict": db_manager.to_dict(result["conflict"]) if result["conflict"] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/tasks/mark_done")
@limiter.limit(f"{LIMITE}/minute")
async def _mark_task_done(request: Request, data: TaskIdData):
    """
    Endpoint pour marquer une tâche comme terminée (attribue des points).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : TaskIdData
        L'ID de la tâche.

    Returns
    -------
    dict
        {"success": bool, "task": dict | None, "points": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        result = db_manager.mark_task_done(data.task_id)
        return {
            "success": result["success"],
            "task": db_manager.to_dict(result["task"]) if result["task"] else None,
            "points": result["points"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/tasks/mark_failed")
@limiter.limit(f"{LIMITE}/minute")
async def _mark_task_failed(request: Request, data: TaskIdData):
    """
    Endpoint pour marquer une tâche comme ratée (délai dépassé) et appliquer la pénalité.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : TaskIdData
        L'ID de la tâche.

    Returns
    -------
    dict
        {"success": bool, "task": dict | None, "points": dict | None, "reported": bool}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        result = db_manager.mark_task_failed(data.task_id)
        return {
            "success": result["success"],
            "task": db_manager.to_dict(result["task"]) if result["task"] else None,
            "points": result["points"],
            "reported": result["reported"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/tasks/by_date")
@limiter.limit(f"{LIMITE}/minute")
async def _get_tasks_by_date(request: Request, data: GetTasksByDateData):
    """
    Endpoint pour récupérer les tâches d'une date donnée (vue jour).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : GetTasksByDateData
        La date à consulter.

    Returns
    -------
    dict
        {"tasks": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        tasks = db_manager.get_tasks_by_date(data.date)
        return {"tasks": [db_manager.to_dict(t) for t in tasks]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/tasks/by_range")
@limiter.limit(f"{LIMITE}/minute")
async def _get_tasks_by_range(request: Request, data: GetTasksByRangeData):
    """
    Endpoint pour récupérer les tâches sur une plage de dates (vue semaine/mois).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : GetTasksByRangeData
        La plage de dates à consulter.

    Returns
    -------
    dict
        {"tasks": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        tasks = db_manager.get_tasks_by_range(data.date_debut, data.date_fin)
        return {"tasks": [db_manager.to_dict(t) for t in tasks]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/tasks/delete")
@limiter.limit(f"{LIMITE}/minute")
async def _delete_task(request: Request, data: TaskIdData):
    """
    Endpoint pour supprimer une tâche.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : TaskIdData
        L'ID de la tâche à supprimer.

    Returns
    -------
    dict
        {"success": bool}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        success = db_manager.delete_task(data.task_id)
        return {"success": success}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/tags/all")
@limiter.limit(f"{LIMITE}/minute")
async def _get_all_tags(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer tous les tags existants (pour autocomplete).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"tags": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        tags = db_manager.get_all_tags()
        return {"tags": [db_manager.to_dict(t, exclude=["tasks"]) for t in tags]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


# =============================================================================
# Goals (Objectifs) & Steps
# =============================================================================

@router.post("/goals/create")
@limiter.limit(f"{LIMITE}/minute")
async def _create_goal(request: Request, data: CreateGoalData):
    """
    Endpoint pour créer un objectif, avec ses étapes si déjà connues.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : CreateGoalData
        Les données de l'objectif (titre optionnel, description/pourquoi obligatoire, date limite obligatoire).

    Returns
    -------
    dict
        {"goal": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)

        goal = Goal(
            titre=data.titre,
            description=data.description,
            avantages=data.avantages,
            date_limite=data.date_limite,
            titre_genere_ia=data.titre_genere_ia,
        )
        steps = None
        if data.steps_titres:
            steps = [GoalStep(titre=t, origine=StepOrigin.manuelle) for t in data.steps_titres]

        goal = db_manager.create_goal(goal, steps=steps)
        return {"goal": db_manager.to_dict(goal) if goal else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/goals/add_step")
@limiter.limit(f"{LIMITE}/minute")
async def _add_step(request: Request, data: AddStepData):
    """
    Endpoint pour ajouter une étape à un objectif (manuelle ou validée depuis l'IA).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : AddStepData
        Les données de l'étape.

    Returns
    -------
    dict
        {"step": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)

        step = GoalStep(
            goal_id=data.goal_id,
            titre=data.titre,
            description=data.description,
            origine=data.origine,
            date_limite=data.date_limite,
        )
        step = db_manager.add_step_to_goal(step)
        return {"step": db_manager.to_dict(step) if step else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/goals/update_step")
@limiter.limit(f"{LIMITE}/minute")
async def _update_step(request: Request, data: UpdateStepData):
    """
    Endpoint pour modifier librement une étape, même après validation IA.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : UpdateStepData
        Les nouvelles valeurs de l'étape.

    Returns
    -------
    dict
        {"step": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        step = db_manager.update_step(
            data.step_id, titre=data.titre, description=data.description, date_limite=data.date_limite
        )
        return {"step": db_manager.to_dict(step) if step else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/goals/delete_step")
@limiter.limit(f"{LIMITE}/minute")
async def _delete_step(request: Request, data: StepIdData):
    """
    Endpoint pour supprimer une étape d'un objectif.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : StepIdData
        L'ID de l'étape à supprimer.

    Returns
    -------
    dict
        {"success": bool}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        success = db_manager.delete_step(data.step_id)
        return {"success": success}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/goals/mark_step_done")
@limiter.limit(f"{LIMITE}/minute")
async def _mark_step_done(request: Request, data: StepIdData):
    """
    Endpoint pour marquer une étape comme terminée (attribue des points, peut compléter l'objectif).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : StepIdData
        L'ID de l'étape.

    Returns
    -------
    dict
        {"success": bool, "step": dict | None, "points": dict | None, "goal_completed": bool}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        result = db_manager.mark_step_done(data.step_id)
        return {
            "success": result["success"],
            "step": db_manager.to_dict(result["step"]) if result["step"] else None,
            "points": result["points"],
            "goal_completed": result["goal_completed"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/goals/active")
@limiter.limit(f"{LIMITE}/minute")
async def _get_active_goals(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer les objectifs actifs (plusieurs en parallèle possibles).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"goals": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        goals = db_manager.get_active_goals()
        return {"goals": [db_manager.to_dict(g) for g in goals]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/goals/all")
@limiter.limit(f"{LIMITE}/minute")
async def _get_all_goals(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer tous les objectifs, quel que soit leur statut.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"goals": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        goals = db_manager.get_all_goals()
        return {"goals": [db_manager.to_dict(g) for g in goals]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/goals/progress")
@limiter.limit(f"{LIMITE}/minute")
async def _get_goal_progress(request: Request, data: GoalIdData):
    """
    Endpoint pour récupérer la progression d'un objectif (pour le chemin/arbre visuel).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : GoalIdData
        L'ID de l'objectif.

    Returns
    -------
    dict
        {"total_steps": int, "completed_steps": int, "percent": int}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        return db_manager.compute_goal_progress(data.goal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


# =============================================================================
# Me ressourcer (DoubtLog)
# =============================================================================

@router.post("/doubt/log")
@limiter.limit(f"{LIMITE}/minute")
async def _log_doubt(request: Request, data: LogDoubtData):
    """
    Endpoint pour enregistrer un moment de doute ("Me ressourcer").

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : LogDoubtData
        L'objectif concerné et la note libre éventuelle.

    Returns
    -------
    dict
        {"entry": dict | None, "goal": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        entry = db_manager.log_doubt(goal_id=data.goal_id, note_libre=data.note_libre)
        goal = db_manager.get_goal_by_id(data.goal_id) if data.goal_id else None
        return {
            "entry": db_manager.to_dict(entry) if entry else None,
            "goal": db_manager.to_dict(goal) if goal else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/doubt/history")
@limiter.limit(f"{LIMITE}/minute")
async def _get_doubt_history(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer l'historique des moments de doute, avec tendance auto-générée.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"history": [...], "tendance": dict}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        history = db_manager.get_doubt_history()
        tendance = db_manager.compute_doubt_tendency()
        return {
            "history": [db_manager.to_dict(h) for h in history],
            "tendance": tendance,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


# =============================================================================
# Mode focus (FocusSession)
# =============================================================================

@router.post("/focus/start")
@limiter.limit(f"{LIMITE}/minute")
async def _start_focus(request: Request, data: StartFocusData):
    """
    Endpoint pour démarrer une session focus.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : StartFocusData
        Durée prévue et points mis en jeu.

    Returns
    -------
    dict
        {"session": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        fs = db_manager.start_focus_session(data.duree_secondes, points_mis_en_jeu=data.points_mis_en_jeu)
        return {"session": db_manager.to_dict(fs) if fs else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/focus/use_pause")
@limiter.limit(f"{LIMITE}/minute")
async def _use_focus_pause(request: Request, data: UseFocusPauseData):
    """
    Endpoint pour consommer du temps de pause sur une session focus en cours (10% du temps total dispo).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : UseFocusPauseData
        L'ID de session et le nombre de secondes de pause à consommer.

    Returns
    -------
    dict
        {"success": bool, "pause_restante_secondes": int}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        result = db_manager.use_focus_pause(data.focus_session_id, data.secondes)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/focus/end")
@limiter.limit(f"{LIMITE}/minute")
async def _end_focus(request: Request, data: EndFocusData):
    """
    Endpoint pour clôturer une session focus (réussie ou ratée), attribue les points.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : EndFocusData
        L'ID de session et le résultat (succès ou échec).

    Returns
    -------
    dict
        {"success": bool, "session": dict | None, "points": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        result = db_manager.end_focus_session(data.focus_session_id, data.succes)
        return {
            "success": result["success"],
            "session": db_manager.to_dict(result["session"]) if result["session"] else None,
            "points": result["points"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/focus/history")
@limiter.limit(f"{LIMITE}/minute")
async def _get_focus_history(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer l'historique des sessions focus.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"sessions": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        sessions = db_manager.get_focus_sessions()
        return {"sessions": [db_manager.to_dict(s) for s in sessions]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


# =============================================================================
# Brain dump
# =============================================================================

@router.post("/braindump/add")
@limiter.limit(f"{LIMITE}/minute")
async def _add_brain_dump(request: Request, data: AddBrainDumpData):
    """
    Endpoint pour ajouter un ou plusieurs items au brain dump.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : AddBrainDumpData
        Liste des textes/idées à ajouter.

    Returns
    -------
    dict
        {"items": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        items = db_manager.add_brain_dump_items(data.textes)
        return {"items": [db_manager.to_dict(i) for i in items]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/braindump/pending")
@limiter.limit(f"{LIMITE}/minute")
async def _get_pending_brain_dump(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer les items du brain dump pas encore triés.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"items": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        items = db_manager.get_pending_brain_dump_items()
        return {"items": [db_manager.to_dict(i) for i in items]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/braindump/apply_sort")
@limiter.limit(f"{LIMITE}/minute")
async def _apply_sort(request: Request, data: ApplySortData):
    """
    Endpoint pour appliquer le résultat du tri IA (ou manuel) sur un item du brain dump.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : ApplySortData
        Le statut à appliquer (utile/futile) et les explications IA éventuelles.

    Returns
    -------
    dict
        {"item": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        item = db_manager.apply_sort_result(
            data.item_id, BrainDumpStatus(data.statut),
            explication_ia=data.explication_ia, dependances_ia=data.dependances_ia
        )
        return {"item": db_manager.to_dict(item) if item else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/braindump/move")
@limiter.limit(f"{LIMITE}/minute")
async def _move_brain_dump(request: Request, data: MoveBrainDumpData):
    """
    Endpoint pour déplacer manuellement un item entre les listes utile/futile.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : MoveBrainDumpData
        L'item à déplacer et son nouveau statut.

    Returns
    -------
    dict
        {"item": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        item = db_manager.move_brain_dump_item(data.item_id, BrainDumpStatus(data.nouveau_statut))
        return {"item": db_manager.to_dict(item) if item else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/braindump/useful")
@limiter.limit(f"{LIMITE}/minute")
async def _get_useful_brain_dump(request: Request, data: PinOnlyData):
    """
    Endpoint pour récupérer les items classés "utile" du brain dump.

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : PinOnlyData
        Le PIN pour authentification.

    Returns
    -------
    dict
        {"items": [...]}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        items = db_manager.get_useful_brain_dump_items()
        return {"items": [db_manager.to_dict(i) for i in items]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")


@router.post("/braindump/link_to_goal")
@limiter.limit(f"{LIMITE}/minute")
async def _link_brain_dump_to_goal(request: Request, data: LinkBrainDumpToGoalData):
    """
    Endpoint pour lier un item du brain dump à l'objectif généré depuis celui-ci
    (après clic sur "Transformer en objectif" et création de l'objectif via /goals/create).

    Parameters
    ----------
    request : Request
        La requête HTTP.
    data : LinkBrainDumpToGoalData
        L'item du brain dump et l'objectif nouvellement créé.

    Returns
    -------
    dict
        {"item": dict | None}
    """
    try:
        db_manager = get_db_manager()
        _verify_pin(data.pin, db_manager)
        item = db_manager.link_brain_dump_to_goal(data.item_id, data.goal_id)
        return {"item": db_manager.to_dict(item) if item else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur interne: {str(e)}")
