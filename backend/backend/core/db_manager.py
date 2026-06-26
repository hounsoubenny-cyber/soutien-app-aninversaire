#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DB Manager - App de planning/objectifs/focus.
Mono-utilisateur, protégée par PIN.
"""

import os, sys
import enum
sys.path.insert(1, os.path.dirname(os.path.abspath(os.path.join(__file__, "..", ".."))))
from sqlmodel import SQLModel, create_engine, select, Session, func, Field, Relationship, and_, or_
from sqlalchemy import UniqueConstraint
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date as date_type
from backend.api.api_config import DBPATH

# =============================================================================
# Les classes enum
# =============================================================================

class Days(str, enum.Enum):
    lundi: str = "lundi"
    mardi: str = "mardi"
    mercredi: str = "mercredi"
    jeudi: str = "jeudi"
    vendredi: str = "vendredi"
    samedi: str = "samedi"
    dimanche: str = "dimanche"


class TaskStatus(str, enum.Enum):
    a_faire: str = "a_faire"
    terminee: str = "terminee"
    reportee: str = "reportee"


class GoalStatus(str, enum.Enum):
    actif: str = "actif"
    atteint: str = "atteint"
    abandonne: str = "abandonne"


class PointsReason(str, enum.Enum):
    task_done: str = "task_done"
    task_failed: str = "task_failed"
    step_done: str = "step_done"
    step_failed: str = "step_failed"
    focus_success: str = "focus_success"
    focus_failed: str = "focus_failed"
    bonus: str = "bonus"


class BrainDumpStatus(str, enum.Enum):
    en_attente: str = "en_attente"
    utile: str = "utile"
    futile: str = "futile"


class StepOrigin(str, enum.Enum):
    manuelle: str = "manuelle"
    ia: str = "ia"


# =============================================================================
# Constantes du système de points (capital confiance)
# =============================================================================

POINTS_CAPITAL_DEPART = 100
POINTS_PLANCHER = 20
POINTS_GAIN_TASK = 10
POINTS_PERTE_TASK = 5
POINTS_GAIN_STEP = 15
POINTS_PERTE_STEP = 7
POINTS_GAIN_FOCUS = 10
POINTS_PERTE_FOCUS = 5


# =============================================================================
# Les classes (tables sql) sqlmodel
# =============================================================================

def _is_loaded(obj, relation: str) -> bool:
    """Vérifie si une relation est chargée sans déclencher le lazy load."""
    return relation in obj.__dict__ and obj.__dict__[relation] is not None


class TaskTagLink(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "task_tag_link"

    task_id: Optional[int] = Field(default=None, foreign_key="task.id", primary_key=True, ondelete="CASCADE")
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.id", primary_key=True, ondelete="CASCADE")


class Tag(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("nom"), {"extend_existing": True})
    __tablename__ = "tag"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(max_length=50, min_length=1)
    created_at: datetime = Field(default_factory=datetime.now)
    tasks: List["Task"] = Relationship(back_populates="tags", link_model=TaskTagLink, sa_relationship_kwargs={"lazy": "selectin"})

    def model_dump(self, skip_relation: str = None, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        exclude = kwargs.get("exclude", []) or []
        if skip_relation != 'tasks' and "tasks" not in exclude and _is_loaded(self, 'tasks'):
            data['tasks'] = [t.model_dump(skip_relation='tags', **kwargs) for t in self.__dict__['tasks']]
        else:
            data['tasks'] = []
        return data


class AppConfig(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "app_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    pin_hash: str = Field(exclude=True)
    capital_points: int = Field(default=POINTS_CAPITAL_DEPART)
    niveau_label: str = Field(default="Apprentie organisée")
    bloquer_notifications: bool = Field(default=True)
    apps_bloquees: Optional[str] = Field(default=None)  # liste séparée par virgules
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Goal(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "goal"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: Optional[str] = Field(default=None, max_length=200)
    description: str = Field(min_length=1, max_length=1000)  # le "pourquoi"
    avantages: Optional[str] = Field(default=None, max_length=1000)
    date_limite: date_type
    statut: GoalStatus = Field(default=GoalStatus.actif)
    titre_genere_ia: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    steps: List["GoalStep"] = Relationship(back_populates="goal", sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan", "order_by": "GoalStep.ordre"})
    doubt_logs: List["DoubtLog"] = Relationship(back_populates="goal", sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"})

    def model_dump(self, skip_relation: str = None, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        exclude = kwargs.get("exclude", []) or []
        if skip_relation != 'steps' and "steps" not in exclude and _is_loaded(self, 'steps'):
            data['steps'] = [s.model_dump(skip_relation='goal', **kwargs) for s in self.__dict__['steps']]
        else:
            data['steps'] = []
        return data


class GoalStep(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "goal_step"

    id: Optional[int] = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goal.id", ondelete="CASCADE")
    titre: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    ordre: int = Field(default=0)
    terminee: bool = Field(default=False)
    origine: StepOrigin = Field(default=StepOrigin.manuelle)
    date_limite: Optional[date_type] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)

    goal: Optional[Goal] = Relationship(back_populates="steps", sa_relationship_kwargs={"lazy": "selectin"})
    tasks: List["Task"] = Relationship(back_populates="step", sa_relationship_kwargs={"lazy": "selectin"})

    def model_dump(self, skip_relation: str = None, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        exclude = kwargs.get("exclude", []) or []
        if skip_relation != 'goal' and "goal" not in exclude and _is_loaded(self, 'goal'):
            data['goal'] = self.__dict__['goal'].model_dump(skip_relation='steps', **kwargs)
        return data


class Task(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "task"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    date: date_type
    heure_debut: str = Field(max_length=5, min_length=1)  # "HH:MM"
    heure_fin: str = Field(max_length=5, min_length=1)
    statut: TaskStatus = Field(default=TaskStatus.a_faire)
    report_auto: bool = Field(default=False)
    rappel_minutes_avant: Optional[int] = Field(default=10)
    recurrence_jours: Optional[str] = Field(default=None)  # ex: "lundi,mercredi" ou "quotidien"
    step_id: Optional[int] = Field(default=None, foreign_key="goal_step.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    step: Optional[GoalStep] = Relationship(back_populates="tasks", sa_relationship_kwargs={"lazy": "selectin"})
    tags: List[Tag] = Relationship(back_populates="tasks", link_model=TaskTagLink, sa_relationship_kwargs={"lazy": "selectin"})

    def model_dump(self, skip_relation: str = None, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        exclude = kwargs.get("exclude", []) or []
        if skip_relation != 'tags' and "tags" not in exclude and _is_loaded(self, 'tags'):
            data['tags'] = [t.model_dump(skip_relation='tasks', **kwargs) for t in self.__dict__['tags']]
        else:
            data['tags'] = []
        if skip_relation != 'step' and "step" not in exclude and _is_loaded(self, 'step'):
            data['step'] = self.__dict__['step'].model_dump(skip_relation='tasks', **kwargs) if self.__dict__['step'] else None
        return data


class DoubtLog(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "doubt_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    goal_id: Optional[int] = Field(default=None, foreign_key="goal.id", ondelete="CASCADE")
    note_libre: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=datetime.now)

    goal: Optional[Goal] = Relationship(back_populates="doubt_logs", sa_relationship_kwargs={"lazy": "selectin"})

    def model_dump(self, skip_relation: str = None, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        exclude = kwargs.get("exclude", []) or []
        if skip_relation != 'goal' and "goal" not in exclude and _is_loaded(self, 'goal'):
            data['goal'] = self.__dict__['goal'].model_dump(skip_relation='doubt_logs', **kwargs) if self.__dict__['goal'] else None
        return data


class FocusSession(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "focus_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    duree_prevue_secondes: int
    duree_pause_dispo_secondes: int  # 10% de la durée prévue
    duree_pause_utilisee_secondes: int = Field(default=0)
    points_mis_en_jeu: int = Field(default=POINTS_GAIN_FOCUS)
    terminee_avec_succes: Optional[bool] = Field(default=None)  # None = en cours
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = Field(default=None)


class PointsHistory(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "points_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    montant: int  # positif ou négatif
    raison: PointsReason
    capital_apres: int
    task_id: Optional[int] = Field(default=None, foreign_key="task.id", ondelete="SET NULL")
    step_id: Optional[int] = Field(default=None, foreign_key="goal_step.id", ondelete="SET NULL")
    focus_session_id: Optional[int] = Field(default=None, foreign_key="focus_session.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=datetime.now)


class BrainDumpItem(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "brain_dump_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    texte: str = Field(min_length=1, max_length=500)
    statut: BrainDumpStatus = Field(default=BrainDumpStatus.en_attente)
    explication_ia: Optional[str] = Field(default=None, max_length=1000)
    dependances_ia: Optional[str] = Field(default=None, max_length=1000)
    transforme_en_goal_id: Optional[int] = Field(default=None, foreign_key="goal.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# DB MANAGER
# =============================================================================

class DBManager:
    def __init__(self, db_url: str = None):
        if not db_url:
            db_file = os.path.join(DBPATH, "soutien_app.db")
            self.db_url = f"sqlite:///{db_file}"
            self.engine = create_engine(
                f"sqlite:///{db_file}",
                connect_args={"check_same_thread": False},
                echo=False,
            )

        SQLModel.metadata.create_all(self.engine)
        self._ensure_config_exists()

    def get_session(self) -> Session:
        return Session(self.engine)

    # =============================================================================
    # AppConfig (PIN + capital confiance)
    # =============================================================================

    def _ensure_config_exists(self):
        """
        Crée la config par défaut si elle n'existe pas encore (id=1 unique).
        """
        with self.get_session() as session:
            cfg = session.get(AppConfig, 1)
            if not cfg:
                cfg = AppConfig(pin_hash='$2b$12$ENDzYasQ10X0/9xn7NiRIOFVxZAniNs5dLzqtGS9uiwEPsAVAoJO2')
                session.add(cfg)
                session.commit()

    def get_config(self) -> Optional[AppConfig]:
        """
        Méthode pour récupérer la configuration de l'app (singleton id=1).

        Returns
        -------
        Optional[AppConfig]
            La config de l'app.
        """
        with self.get_session() as session:
            return session.get(AppConfig, 1)

    def set_pin(self, pin_hash: str) -> bool:
        """
        Méthode pour définir/mettre à jour le PIN de l'app.

        Parameters
        ----------
        pin_hash : str
            Le hash du PIN (déjà hashé en amont, ex: bcrypt).

        Returns
        -------
        bool
            True si succès, False sinon.
        """
        with self.get_session() as session:
            try:
                cfg = session.get(AppConfig, 1)
                cfg.pin_hash = pin_hash
                cfg.updated_at = datetime.now()
                session.add(cfg)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR set_pin: {e}")
                return False

    def update_settings(self, bloquer_notifications: bool = None, apps_bloquees: str = None) -> Optional[AppConfig]:
        """
        Méthode pour mettre à jour les réglages de l'app (blocage notifs).

        Parameters
        ----------
        bloquer_notifications : bool, optional
            Active/désactive le blocage des notifications en focus.
        apps_bloquees : str, optional
            Liste des apps à bloquer, séparées par virgules.

        Returns
        -------
        Optional[AppConfig]
            La config mise à jour.
        """
        with self.get_session() as session:
            try:
                cfg = session.get(AppConfig, 1)
                if bloquer_notifications is not None:
                    cfg.bloquer_notifications = bloquer_notifications
                if apps_bloquees is not None:
                    cfg.apps_bloquees = apps_bloquees
                cfg.updated_at = datetime.now()
                session.add(cfg)
                session.commit()
                session.refresh(cfg)
                return cfg
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR update_settings: {e}")
                return None

    def _compute_niveau_label(self, capital: int) -> str:
        """
        Méthode interne pour déduire le label du niveau symbolique selon le capital.

        Parameters
        ----------
        capital : int
            Le capital de points actuel.

        Returns
        -------
        str
            Le label du niveau.
        """
        if capital >= 250:
            return "Stratège du quotidien"
        elif capital >= 180:
            return "Organisatrice confirmée"
        elif capital >= 120:
            return "En pleine progression"
        elif capital >= 70:
            return "Apprentie organisée"
        else:
            return "Je me reconstruis, doucement"

    def add_points(
        self,
        montant: int,
        raison: PointsReason,
        task_id: int = None,
        step_id: int = None,
        focus_session_id: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Méthode pour ajouter ou retirer des points au capital confiance,
        avec respect du plancher minimum, et log dans l'historique.

        Parameters
        ----------
        montant : int
            Le montant à ajouter (peut être négatif).
        raison : PointsReason
            La raison du mouvement de points.
        task_id : int, optional
            La tâche liée, si applicable.
        step_id : int, optional
            L'étape liée, si applicable.
        focus_session_id : int, optional
            La session focus liée, si applicable.

        Returns
        -------
        Optional[Dict[str, Any]]
            Dictionnaire avec 'capital_avant', 'capital_apres', 'niveau_label'.
        """
        with self.get_session() as session:
            try:
                cfg = session.get(AppConfig, 1)
                capital_avant = cfg.capital_points
                nouveau_capital = capital_avant + montant
                if nouveau_capital < POINTS_PLANCHER:
                    nouveau_capital = POINTS_PLANCHER

                cfg.capital_points = nouveau_capital
                cfg.niveau_label = self._compute_niveau_label(nouveau_capital)
                cfg.updated_at = datetime.now()
                session.add(cfg)

                history = PointsHistory(
                    montant=montant,
                    raison=raison,
                    capital_apres=nouveau_capital,
                    task_id=task_id,
                    step_id=step_id,
                    focus_session_id=focus_session_id
                )
                session.add(history)
                session.commit()

                return {
                    "capital_avant": capital_avant,
                    "capital_apres": nouveau_capital,
                    "niveau_label": cfg.niveau_label
                }
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR add_points: {e}")
                return None

    def get_points_history(self, limit: int = 50) -> List[PointsHistory]:
        """
        Méthode pour récupérer l'historique des mouvements de points.

        Parameters
        ----------
        limit : int, optional
            Nombre maximum d'entrées à retourner.

        Returns
        -------
        List[PointsHistory]
            Liste triée par date décroissante.
        """
        with self.get_session() as session:
            return session.exec(
                select(PointsHistory)
                .order_by(PointsHistory.created_at.desc())
                .limit(limit)
            ).all()

    # =============================================================================
    # Tags
    # =============================================================================

    def get_or_create_tag(self, nom: str) -> Optional[Tag]:
        """
        Méthode pour récupérer un tag existant par son nom, ou le créer.

        Parameters
        ----------
        nom : str
            Le nom du tag.

        Returns
        -------
        Optional[Tag]
            Le tag récupéré ou créé.
        """
        with self.get_session() as session:
            try:
                tag = session.exec(select(Tag).where(Tag.nom == nom)).first()
                if tag:
                    return tag
                tag = Tag(nom=nom)
                session.add(tag)
                session.commit()
                session.refresh(tag)
                return tag
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR get_or_create_tag: {e}")
                return None

    def get_all_tags(self) -> List[Tag]:
        """
        Méthode pour récupérer tous les tags existants.

        Returns
        -------
        List[Tag]
            Liste des tags.
        """
        with self.get_session() as session:
            return session.exec(select(Tag)).all()

    # =============================================================================
    # Tasks (Planning journalier)
    # =============================================================================

    def _check_conflict(self, date: date_type, heure_debut: str, heure_fin: str, exclude_task_id: int = None) -> Optional[Task]:
        """
        Méthode interne pour détecter un conflit de créneau avec une tâche non terminée existante.

        Parameters
        ----------
        date : date
            La date du créneau à vérifier.
        heure_debut : str
            Heure de début du créneau ("HH:MM").
        heure_fin : str
            Heure de fin du créneau ("HH:MM").
        exclude_task_id : int, optional
            ID de tâche à exclure de la vérification (utile lors d'une édition).

        Returns
        -------
        Optional[Task]
            La tâche en conflit si trouvée, sinon None.
        """
        with self.get_session() as session:
            query = select(Task).where(
                Task.date == date,
                Task.statut != TaskStatus.terminee,
                Task.heure_debut < heure_fin,
                Task.heure_fin > heure_debut
            )
            if exclude_task_id:
                query = query.where(Task.id != exclude_task_id)
            return session.exec(query).first()

    def create_task(self, task: Task, tag_noms: List[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        Méthode pour créer une tâche, avec détection de conflit de créneau.

        Parameters
        ----------
        task : Task
            La tâche à créer.
        tag_noms : List[str], optional
            Liste des noms de tags à associer (créés si besoin).
        force : bool, optional
            Si True, ignore le conflit détecté et crée quand même.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'success', 'task' et 'conflict' (tâche en conflit si applicable).
        """
        result = {"success": False, "task": None, "conflict": None}
        try:
            conflict = self._check_conflict(task.date, task.heure_debut, task.heure_fin)
            if conflict and not force:
                result["conflict"] = conflict
                return result

            with self.get_session() as session:
                if tag_noms:
                    tags = [self.get_or_create_tag(nom) for nom in tag_noms]
                    task.tags = [t for t in tags if t]
                session.add(task)
                session.commit()
                session.refresh(task)
                result["success"] = True
                result["task"] = task
                return result
        except Exception as e:
            print(f"❌ ERREUR create_task: {e}")
            return result

    def update_task_time(self, task_id: int, heure_debut: str, heure_fin: str, force: bool = False) -> Dict[str, Any]:
        """
        Méthode pour modifier l'heure d'une tâche, avec détection de conflit.

        Parameters
        ----------
        task_id : int
            L'ID de la tâche à modifier.
        heure_debut : str
            Nouvelle heure de début.
        heure_fin : str
            Nouvelle heure de fin.
        force : bool, optional
            Si True, ignore le conflit détecté.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'success', 'task' et 'conflict'.
        """
        result = {"success": False, "task": None, "conflict": None}
        with self.get_session() as session:
            try:
                task = session.get(Task, task_id)
                if not task:
                    return result

                conflict = self._check_conflict(task.date, heure_debut, heure_fin, exclude_task_id=task_id)
                if conflict and not force:
                    result["conflict"] = conflict
                    return result

                task.heure_debut = heure_debut
                task.heure_fin = heure_fin
                task.updated_at = datetime.now()
                session.add(task)
                session.commit()
                session.refresh(task)
                result["success"] = True
                result["task"] = task
                return result
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR update_task_time: {e}")
                return result

    def mark_task_done(self, task_id: int) -> Dict[str, Any]:
        """
        Méthode pour marquer une tâche comme terminée et attribuer les points.

        Parameters
        ----------
        task_id : int
            L'ID de la tâche.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'success', 'task' et 'points' (résultat de add_points).
        """
        result = {"success": False, "task": None, "points": None}
        with self.get_session() as session:
            try:
                task = session.get(Task, task_id)
                if not task:
                    return result
                task.statut = TaskStatus.terminee
                task.updated_at = datetime.now()
                session.add(task)
                session.commit()
                session.refresh(task)
                result["success"] = True
                result["task"] = task
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR mark_task_done: {e}")
                return result

        result["points"] = self.add_points(POINTS_GAIN_TASK, PointsReason.task_done, task_id=task_id)
        return result

    def mark_task_failed(self, task_id: int) -> Dict[str, Any]:
        """
        Méthode pour marquer une tâche comme ratée (délai dépassé, non faite) et appliquer la pénalité.
        Gère le report automatique si configuré sur la tâche.

        Parameters
        ----------
        task_id : int
            L'ID de la tâche.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'success', 'task', 'points' et 'reported' (bool).
        """
        result = {"success": False, "task": None, "points": None, "reported": False}
        with self.get_session() as session:
            try:
                task = session.get(Task, task_id)
                if not task:
                    return result

                if task.report_auto:
                    task.statut = TaskStatus.reportee
                    result["reported"] = True
                else:
                    task.statut = TaskStatus.a_faire
                task.updated_at = datetime.now()
                session.add(task)
                session.commit()
                session.refresh(task)
                result["success"] = True
                result["task"] = task
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR mark_task_failed: {e}")
                return result

        result["points"] = self.add_points(-POINTS_PERTE_TASK, PointsReason.task_failed, task_id=task_id)
        return result

    def get_tasks_by_date(self, date: date_type) -> List[Task]:
        """
        Méthode pour récupérer toutes les tâches d'une date donnée (vue jour).

        Parameters
        ----------
        date : date
            La date à consulter.

        Returns
        -------
        List[Task]
            Liste des tâches triées par heure de début.
        """
        with self.get_session() as session:
            return session.exec(
                select(Task)
                .where(Task.date == date)
                .order_by(Task.heure_debut)
            ).all()

    def get_tasks_by_range(self, date_debut: date_type, date_fin: date_type) -> List[Task]:
        """
        Méthode pour récupérer les tâches sur une plage de dates (vue semaine/mois).

        Parameters
        ----------
        date_debut : date
            Date de début de la plage (incluse).
        date_fin : date
            Date de fin de la plage (incluse).

        Returns
        -------
        List[Task]
            Liste des tâches triées par date puis heure de début.
        """
        with self.get_session() as session:
            return session.exec(
                select(Task)
                .where(Task.date >= date_debut, Task.date <= date_fin)
                .order_by(Task.date, Task.heure_debut)
            ).all()

    def delete_task(self, task_id: int) -> bool:
        """
        Méthode pour supprimer une tâche.

        Parameters
        ----------
        task_id : int
            L'ID de la tâche à supprimer.

        Returns
        -------
        bool
            True si succès, False sinon.
        """
        with self.get_session() as session:
            try:
                task = session.get(Task, task_id)
                if not task:
                    return False
                session.delete(task)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR delete_task: {e}")
                return False

    # =============================================================================
    # Goals (Objectifs) & GoalSteps
    # =============================================================================

    def create_goal(self, goal: Goal, steps: List[GoalStep] = None) -> Optional[Goal]:
        """
        Méthode pour créer un objectif, avec ses étapes optionnelles (manuelles ou IA).

        Parameters
        ----------
        goal : Goal
            L'objectif à créer.
        steps : List[GoalStep], optional
            Liste des étapes à associer directement.

        Returns
        -------
        Optional[Goal]
            L'objectif créé, ou None si échec.
        """
        with self.get_session() as session:
            try:
                session.add(goal)
                session.commit()
                session.refresh(goal)

                if steps:
                    for i, step in enumerate(steps):
                        step.goal_id = goal.id
                        step.ordre = i
                        session.add(step)
                    session.commit()
                    session.refresh(goal)

                return goal
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR create_goal: {e}")
                return None

    def add_step_to_goal(self, step: GoalStep) -> Optional[GoalStep]:
        """
        Méthode pour ajouter une étape à un objectif existant (manuelle ou après validation IA).

        Parameters
        ----------
        step : GoalStep
            L'étape à ajouter (goal_id doit être renseigné).

        Returns
        -------
        Optional[GoalStep]
            L'étape créée, ou None si échec.
        """
        with self.get_session() as session:
            try:
                if step.ordre == 0:
                    max_ordre = session.exec(
                        select(func.max(GoalStep.ordre)).where(GoalStep.goal_id == step.goal_id)
                    ).first()
                    step.ordre = (max_ordre or 0) + 1
                session.add(step)
                session.commit()
                session.refresh(step)
                return step
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR add_step_to_goal: {e}")
                return None

    def update_step(self, step_id: int, titre: str = None, description: str = None, date_limite: date_type = None) -> Optional[GoalStep]:
        """
        Méthode pour modifier une étape existante.

        Parameters
        ----------
        step_id : int
            L'ID de l'étape.
        titre : str, optional
            Nouveau titre.
        description : str, optional
            Nouvelle description.
        date_limite : date, optional
            Nouvelle date limite.

        Returns
        -------
        Optional[GoalStep]
            L'étape mise à jour, ou None si échec.
        """
        with self.get_session() as session:
            try:
                step = session.get(GoalStep, step_id)
                if not step:
                    return None
                if titre is not None:
                    step.titre = titre
                if description is not None:
                    step.description = description
                if date_limite is not None:
                    step.date_limite = date_limite
                session.add(step)
                session.commit()
                session.refresh(step)
                return step
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR update_step: {e}")
                return None

    def delete_step(self, step_id: int) -> bool:
        """
        Méthode pour supprimer une étape d'un objectif.

        Parameters
        ----------
        step_id : int
            L'ID de l'étape à supprimer.

        Returns
        -------
        bool
            True si succès, False sinon.
        """
        with self.get_session() as session:
            try:
                step = session.get(GoalStep, step_id)
                if not step:
                    return False
                session.delete(step)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR delete_step: {e}")
                return False

    def mark_step_done(self, step_id: int) -> Dict[str, Any]:
        """
        Méthode pour marquer une étape comme terminée et attribuer les points.
        Si toutes les étapes d'un objectif sont terminées, l'objectif passe à "atteint".

        Parameters
        ----------
        step_id : int
            L'ID de l'étape.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'success', 'step', 'points' et 'goal_completed' (bool).
        """
        result = {"success": False, "step": None, "points": None, "goal_completed": False}
        with self.get_session() as session:
            try:
                step = session.get(GoalStep, step_id)
                if not step:
                    return result
                step.terminee = True
                session.add(step)
                session.commit()
                session.refresh(step)
                result["success"] = True
                result["step"] = step

                goal = session.get(Goal, step.goal_id)
                if goal and goal.steps and all(s.terminee for s in goal.steps):
                    goal.statut = GoalStatus.atteint
                    goal.updated_at = datetime.now()
                    session.add(goal)
                    session.commit()
                    result["goal_completed"] = True
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR mark_step_done: {e}")
                return result

        result["points"] = self.add_points(POINTS_GAIN_STEP, PointsReason.step_done, step_id=step_id)
        return result

    def get_goal_by_id(self, goal_id: int) -> Optional[Goal]:
        """
        Méthode pour récupérer un objectif par son ID, avec ses étapes.

        Parameters
        ----------
        goal_id : int
            L'ID de l'objectif.

        Returns
        -------
        Optional[Goal]
            L'objectif trouvé, ou None.
        """
        with self.get_session() as session:
            return session.get(Goal, goal_id)

    def get_active_goals(self) -> List[Goal]:
        """
        Méthode pour récupérer tous les objectifs actifs (plusieurs en parallèle possible).

        Returns
        -------
        List[Goal]
            Liste des objectifs actifs.
        """
        with self.get_session() as session:
            return session.exec(
                select(Goal).where(Goal.statut == GoalStatus.actif).order_by(Goal.date_limite)
            ).all()

    def get_all_goals(self) -> List[Goal]:
        """
        Méthode pour récupérer tous les objectifs, quel que soit leur statut.

        Returns
        -------
        List[Goal]
            Liste de tous les objectifs.
        """
        with self.get_session() as session:
            return session.exec(select(Goal).order_by(Goal.created_at.desc())).all()

    def compute_goal_progress(self, goal_id: int) -> Dict[str, Any]:
        """
        Méthode pour calculer la progression d'un objectif (pour la visualisation chemin/arbre).

        Parameters
        ----------
        goal_id : int
            L'ID de l'objectif.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'total_steps', 'completed_steps', 'percent'.
        """
        goal = self.get_goal_by_id(goal_id)
        if not goal or not goal.steps:
            return {"total_steps": 0, "completed_steps": 0, "percent": 0}

        total = len(goal.steps)
        completed = sum(1 for s in goal.steps if s.terminee)
        return {
            "total_steps": total,
            "completed_steps": completed,
            "percent": round((completed / total) * 100) if total else 0
        }

    # =============================================================================
    # DoubtLog (Me ressourcer)
    # =============================================================================

    def log_doubt(self, goal_id: int = None, note_libre: str = None) -> Optional[DoubtLog]:
        """
        Méthode pour enregistrer un moment de doute dans le journal ("Me ressourcer").

        Parameters
        ----------
        goal_id : int, optional
            L'objectif concerné par le doute.
        note_libre : str, optional
            Note libre sur ce qu'elle ressentait.

        Returns
        -------
        Optional[DoubtLog]
            L'entrée créée, ou None si échec.
        """
        with self.get_session() as session:
            try:
                entry = DoubtLog(goal_id=goal_id, note_libre=note_libre)
                session.add(entry)
                session.commit()
                session.refresh(entry)
                return entry
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR log_doubt: {e}")
                return None

    def get_doubt_history(self, limit: int = 50) -> List[DoubtLog]:
        """
        Méthode pour récupérer l'historique des moments de doute.

        Parameters
        ----------
        limit : int, optional
            Nombre maximum d'entrées.

        Returns
        -------
        List[DoubtLog]
            Liste triée par date décroissante.
        """
        with self.get_session() as session:
            return session.exec(
                select(DoubtLog).order_by(DoubtLog.created_at.desc()).limit(limit)
            ).all()

    def compute_doubt_tendency(self) -> Dict[str, Any]:
        """
        Méthode pour calculer une tendance simple sur les moments de doute
        (fréquence par objectif), utilisée pour le résumé auto-généré.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'total', 'par_goal' (Dict[goal_id, count]) et 'goal_le_plus_frequent'.
        """
        logs = self.get_doubt_history(limit=500)
        total = len(logs)
        par_goal: Dict[int, int] = {}
        for log in logs:
            if log.goal_id:
                par_goal[log.goal_id] = par_goal.get(log.goal_id, 0) + 1

        goal_frequent = max(par_goal, key=par_goal.get) if par_goal else None
        return {
            "total": total,
            "par_goal": par_goal,
            "goal_le_plus_frequent": goal_frequent
        }

    # =============================================================================
    # FocusSession (Mode focus)
    # =============================================================================

    def start_focus_session(self, duree_secondes: int, points_mis_en_jeu: int = POINTS_GAIN_FOCUS) -> Optional[FocusSession]:
        """
        Méthode pour démarrer une session focus.

        Parameters
        ----------
        duree_secondes : int
            Durée prévue de la session, en secondes.
        points_mis_en_jeu : int, optional
            Points à gagner/perdre selon le résultat de la session.

        Returns
        -------
        Optional[FocusSession]
            La session créée, ou None si échec.
        """
        with self.get_session() as session:
            try:
                fs = FocusSession(
                    duree_prevue_secondes=duree_secondes,
                    duree_pause_dispo_secondes=int(duree_secondes * 0.10),
                    points_mis_en_jeu=points_mis_en_jeu
                )
                session.add(fs)
                session.commit()
                session.refresh(fs)
                return fs
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR start_focus_session: {e}")
                return None

    def use_focus_pause(self, focus_session_id: int, secondes: int) -> Dict[str, Any]:
        """
        Méthode pour consommer du temps de pause sur une session focus en cours.

        Parameters
        ----------
        focus_session_id : int
            L'ID de la session.
        secondes : int
            Nombre de secondes de pause à consommer.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'success', 'pause_restante_secondes'.
        """
        result = {"success": False, "pause_restante_secondes": 0}
        with self.get_session() as session:
            try:
                fs = session.get(FocusSession, focus_session_id)
                if not fs:
                    return result
                restante = fs.duree_pause_dispo_secondes - fs.duree_pause_utilisee_secondes
                if secondes > restante:
                    secondes = restante
                fs.duree_pause_utilisee_secondes += secondes
                session.add(fs)
                session.commit()
                session.refresh(fs)
                result["success"] = True
                result["pause_restante_secondes"] = fs.duree_pause_dispo_secondes - fs.duree_pause_utilisee_secondes
                return result
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR use_focus_pause: {e}")
                return result

    def end_focus_session(self, focus_session_id: int, succes: bool) -> Dict[str, Any]:
        """
        Méthode pour clôturer une session focus (réussie ou ratée) et attribuer les points.

        Parameters
        ----------
        focus_session_id : int
            L'ID de la session.
        succes : bool
            True si la session s'est terminée dans le temps imparti.

        Returns
        -------
        Dict[str, Any]
            Dictionnaire avec 'success', 'session', 'points'.
        """
        result = {"success": False, "session": None, "points": None}
        with self.get_session() as session:
            try:
                fs = session.get(FocusSession, focus_session_id)
                if not fs:
                    return result
                fs.terminee_avec_succes = succes
                fs.ended_at = datetime.now()
                session.add(fs)
                session.commit()
                session.refresh(fs)
                result["success"] = True
                result["session"] = fs
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR end_focus_session: {e}")
                return result

        if succes:
            result["points"] = self.add_points(fs.points_mis_en_jeu, PointsReason.focus_success, focus_session_id=focus_session_id)
        else:
            result["points"] = self.add_points(-POINTS_PERTE_FOCUS, PointsReason.focus_failed, focus_session_id=focus_session_id)
        return result

    def get_focus_sessions(self, limit: int = 50) -> List[FocusSession]:
        """
        Méthode pour récupérer l'historique des sessions focus.

        Parameters
        ----------
        limit : int, optional
            Nombre maximum d'entrées.

        Returns
        -------
        List[FocusSession]
            Liste triée par date décroissante.
        """
        with self.get_session() as session:
            return session.exec(
                select(FocusSession).order_by(FocusSession.started_at.desc()).limit(limit)
            ).all()

    # =============================================================================
    # BrainDumpItem (Brain dump)
    # =============================================================================

    def add_brain_dump_items(self, textes: List[str]) -> List[BrainDumpItem]:
        """
        Méthode pour ajouter un ou plusieurs items au brain dump (saisie en bloc ou un par un).

        Parameters
        ----------
        textes : List[str]
            Liste des textes/idées à ajouter.

        Returns
        -------
        List[BrainDumpItem]
            Liste des items créés.
        """
        created = []
        with self.get_session() as session:
            try:
                for texte in textes:
                    if texte and texte.strip():
                        item = BrainDumpItem(texte=texte.strip())
                        session.add(item)
                        created.append(item)
                session.commit()
                for item in created:
                    session.refresh(item)
                return created
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR add_brain_dump_items: {e}")
                return []

    def get_pending_brain_dump_items(self) -> List[BrainDumpItem]:
        """
        Méthode pour récupérer les items du brain dump pas encore triés.

        Returns
        -------
        List[BrainDumpItem]
            Liste des items en attente de tri.
        """
        with self.get_session() as session:
            return session.exec(
                select(BrainDumpItem).where(BrainDumpItem.statut == BrainDumpStatus.en_attente)
            ).all()

    def apply_sort_result(self, item_id: int, statut: BrainDumpStatus, explication_ia: str = None, dependances_ia: str = None) -> Optional[BrainDumpItem]:
        """
        Méthode pour appliquer le résultat du tri IA (ou manuel) sur un item du brain dump.

        Parameters
        ----------
        item_id : int
            L'ID de l'item.
        statut : BrainDumpStatus
            Le nouveau statut (utile/futile).
        explication_ia : str, optional
            Explication générée par l'IA pour cette idée.
        dependances_ia : str, optional
            Dépendances/interactions générées par l'IA.

        Returns
        -------
        Optional[BrainDumpItem]
            L'item mis à jour, ou None si échec.
        """
        with self.get_session() as session:
            try:
                item = session.get(BrainDumpItem, item_id)
                if not item:
                    return None
                item.statut = statut
                if explication_ia is not None:
                    item.explication_ia = explication_ia
                if dependances_ia is not None:
                    item.dependances_ia = dependances_ia
                item.updated_at = datetime.now()
                session.add(item)
                session.commit()
                session.refresh(item)
                return item
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR apply_sort_result: {e}")
                return None

    def move_brain_dump_item(self, item_id: int, nouveau_statut: BrainDumpStatus) -> Optional[BrainDumpItem]:
        """
        Méthode pour déplacer manuellement un item entre les listes utile/futile.

        Parameters
        ----------
        item_id : int
            L'ID de l'item.
        nouveau_statut : BrainDumpStatus
            Le nouveau statut souhaité.

        Returns
        -------
        Optional[BrainDumpItem]
            L'item mis à jour, ou None si échec.
        """
        return self.apply_sort_result(item_id, nouveau_statut)

    def link_brain_dump_to_goal(self, item_id: int, goal_id: int) -> Optional[BrainDumpItem]:
        """
        Méthode pour lier un item du brain dump à l'objectif généré depuis celui-ci
        (bouton "Transformer en objectif").

        Parameters
        ----------
        item_id : int
            L'ID de l'item du brain dump.
        goal_id : int
            L'ID de l'objectif nouvellement créé.

        Returns
        -------
        Optional[BrainDumpItem]
            L'item mis à jour, ou None si échec.
        """
        with self.get_session() as session:
            try:
                item = session.get(BrainDumpItem, item_id)
                if not item:
                    return None
                item.transforme_en_goal_id = goal_id
                item.updated_at = datetime.now()
                session.add(item)
                session.commit()
                session.refresh(item)
                return item
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR link_brain_dump_to_goal: {e}")
                return None

    def get_useful_brain_dump_items(self) -> List[BrainDumpItem]:
        """
        Méthode pour récupérer les items classés "utile" du brain dump.

        Returns
        -------
        List[BrainDumpItem]
            Liste des items utiles.
        """
        with self.get_session() as session:
            return session.exec(
                select(BrainDumpItem).where(BrainDumpItem.statut == BrainDumpStatus.utile)
            ).all()

    # =============================================================================
    # Utilitaire générique
    # =============================================================================

    def to_dict(self, obj, **kwargs) -> Dict:
        """
        Méthode utilitaire pour transformer une table en dictionnaire propre.

        Parameters
        ----------
        obj : Any
            Une instance des tables.
        **kwargs : dict
            Arguments nommés supplémentaires.

        Returns
        -------
        Dict
            Dictionnaire final.
        """
        with self.get_session() as session:
            try:
                merged = session.merge(obj)
                session.refresh(merged)
                return merged.model_dump(**kwargs)
            except:
                return {}


if __name__ == "__main__":
    import bcrypt

    db = DBManager()
    SQLModel.metadata.drop_all(db.engine)
    SQLModel.metadata.create_all(db.engine)
    db._ensure_config_exists()

    # =========================================================================
    # PIN
    # =========================================================================
    pin_hash = bcrypt.hashpw("1234".encode(), bcrypt.gensalt()).decode()
    db.set_pin(pin_hash)
    print(f"PIN configuré, capital de départ: {db.get_config().capital_points}")

    # =========================================================================
    # Objectif + étapes
    # =========================================================================
    goal = Goal(
        description="Dans 2 ans je veux maîtriser la couture",
        avantages="Pouvoir créer mes propres vêtements, gagner en confiance créative",
        date_limite=date_type(2028, 6, 20),
    )
    steps = [
        GoalStep(titre="Apprendre les bases de la machine à coudre", origine=StepOrigin.ia),
        GoalStep(titre="Réaliser des patrons simples", origine=StepOrigin.ia),
        GoalStep(titre="Faire un premier vêtement complet", origine=StepOrigin.ia),
    ]
    goal = db.create_goal(goal, steps=steps)
    print(f"\nObjectif créé : id={goal.id}, {len(goal.steps)} étapes")

    # =========================================================================
    # Tâche journalière liée à une étape
    # =========================================================================
    first_step = goal.steps[0]
    task = Task(
        titre="Regarder un tuto enfilage machine à coudre",
        date=date_type.today(),
        heure_debut="14:00",
        heure_fin="15:00",
        report_auto=True,
        step_id=first_step.id,
    )
    res = db.create_task(task, tag_noms=["couture", "apprentissage"])
    print(f"Tâche créée : success={res['success']}, id={res['task'].id if res['task'] else None}")

    # Conflit volontaire
    task2 = Task(
        titre="Conflit test",
        date=date_type.today(),
        heure_debut="14:30",
        heure_fin="15:30",
    )
    res2 = db.create_task(task2)
    print(f"Test conflit : success={res2['success']}, conflict détecté={res2['conflict'] is not None}")

    # =========================================================================
    # Marquer terminé -> points
    # =========================================================================
    done = db.mark_task_done(res["task"].id)
    print(f"\nTâche terminée, points: {done['points']}")

    step_done = db.mark_step_done(first_step.id)
    print(f"Étape terminée, points: {step_done['points']}, progress: {db.compute_goal_progress(goal.id)}")

    # =========================================================================
    # Me ressourcer
    # =========================================================================
    doubt = db.log_doubt(goal_id=goal.id, note_libre="Je doute de réussir à temps")
    print(f"\nDoute loggé : id={doubt.id}")
    print(f"Tendance doute : {db.compute_doubt_tendency()}")

    # =========================================================================
    # Mode focus
    # =========================================================================
    fs = db.start_focus_session(duree_secondes=1500)  # 25 min
    print(f"\nFocus session démarrée : id={fs.id}, pause dispo={fs.duree_pause_dispo_secondes}s")
    pause = db.use_focus_pause(fs.id, 60)
    print(f"Pause utilisée : {pause}")
    end = db.end_focus_session(fs.id, succes=True)
    print(f"Focus terminée avec succès, points: {end['points']}")

    # =========================================================================
    # Brain dump
    # =========================================================================
    items = db.add_brain_dump_items(["Apprendre le tricot", "Regarder une série", "Organiser mon armoire"])
    print(f"\nBrain dump : {len(items)} items créés")
    db.apply_sort_result(items[0].id, BrainDumpStatus.utile, explication_ia="Permet de diversifier tes compétences manuelles")
    db.apply_sort_result(items[1].id, BrainDumpStatus.futile)
    print(f"Items utiles : {[i.texte for i in db.get_useful_brain_dump_items()]}")

    print(f"\nCapital final : {db.get_config().capital_points} ({db.get_config().niveau_label})")
