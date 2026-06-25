#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Manager — Groq API avec rotation de clés ET fallback de modèles.
Si toutes les clés sont épuisées sur le modèle principal → modèle de secours.
Si même ça échoue → lève IAUnavailableError.
"""

import os, json, time, itertools
from typing import Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Config
# =============================================================================

# Cascade de modèles : du plus puissant au plus léger
MODEL_CASCADE = [
    os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

MAX_RETRIES_PER_MODEL = 3
RETRY_DELAY = 1.0


class IAUnavailableError(Exception):
    """Levée quand toutes les clés ET tous les modèles ont échoué."""
    pass


def _load_keys() -> list:
    keys = []
    i = 1
    while True:
        k = os.getenv(f"GROQ_API_KEY_{i}")
        if not k:
            break
        keys.append(k.strip())
        i += 1
    if not keys:
        raise ValueError("Aucune clé Groq trouvée dans .env (GROQ_API_KEY_1, GROQ_API_KEY_2...)")
    return keys


# =============================================================================
# LLMManager
# =============================================================================

class LLMManager:
    def __init__(self):
        self._keys  = _load_keys()
        self._cycle = itertools.cycle(self._keys)
        self._client = self._make_client()
        print(f"✅ LLMManager — {len(self._keys)} clé(s), cascade: {MODEL_CASCADE[0]} → fallbacks")

    def _make_client(self) -> Groq:
        return Groq(api_key=next(self._cycle))

    def _rotate(self):
        self._client = self._make_client()

    def generate(self, system_prompt: str, prompt: str, max_tokens: int = 1024) -> str:
        """
        Génère une réponse avec cascade automatique clés → modèles.
        Lève IAUnavailableError si tout échoue.
        """
        for model in MODEL_CASCADE:
            # Reset cycle de clés pour chaque modèle
            self._cycle = itertools.cycle(self._keys)
            self._client = self._make_client()

            for attempt in range(MAX_RETRIES_PER_MODEL * len(self._keys)):
                try:
                    response = self._client.chat.completions.create(
                        model=model,
                        max_tokens=max_tokens,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user",   "content": prompt},
                        ],
                        temperature=0.4,
                    )
                    return response.choices[0].message.content.strip()

                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ["rate", "limit", "429", "quota", "capacity"]):
                        print(f"⚠️  Rate limit [{model}] clé {(attempt % len(self._keys)) + 1} — rotation...")
                        self._rotate()
                        time.sleep(RETRY_DELAY)
                    elif "model" in err and ("not found" in err or "deprecated" in err):
                        print(f"⚠️  Modèle {model} indisponible, passage au suivant...")
                        break
                    else:
                        print(f"❌ Erreur Groq [{model}]: {e}")
                        raise

        raise IAUnavailableError("Toutes les clés et modèles Groq ont échoué. IA temporairement indisponible.")

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if "```" in cleaned:
                cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned.strip())

    # =========================================================================
    # Feature 1 — Génération des étapes d'un objectif
    # =========================================================================
    def generate_goal_steps(self, description: str, date_limite: str, titre: str = None) -> list:
        system_prompt = """Tu es un coach de vie bienveillant et organisé.
INSTRUCTIONS STRICTES :
- Réponds UNIQUEMENT en JSON valide, sans texte avant ni après, sans backticks markdown.
- Format exact : {"steps": [{"titre": "...", "description": "..."}, ...]}
- Entre 3 et 7 étapes, logiquement ordonnées, progressives.
- Titres courts (5-8 mots), descriptions actionnables (1-2 phrases).
- Adapte la difficulté et la durée à la date limite.
- Langue : français uniquement."""

        titre_part = f"Titre : {titre}\n" if titre else ""
        prompt = f"""{titre_part}Motivation : {description}
Date limite : {date_limite}
Génère un plan d'étapes progressives et réalistes."""

        raw = self.generate(system_prompt, prompt, max_tokens=800)
        return self._parse_json(raw).get("steps", [])

    # =========================================================================
    # Feature 2 — Génération du titre d'un objectif
    # =========================================================================
    def generate_goal_title(self, description: str) -> str:
        system_prompt = """Tu es un coach de vie.
INSTRUCTIONS STRICTES :
- Réponds UNIQUEMENT en JSON valide, sans texte avant ni après, sans backticks.
- Format exact : {"titre": "..."}
- 3 à 7 mots, commence par un verbe à l'infinitif (Maîtriser, Apprendre, Créer...).
- Langue : français uniquement."""

        raw = self.generate(system_prompt, f"Description : {description}\nGénère un titre court et motivant.", max_tokens=80)
        return self._parse_json(raw).get("titre", description[:50])

    # =========================================================================
    # Feature 3 — Tri du Brain Dump
    # =========================================================================
    def sort_brain_dump(self, items: list) -> list:
        system_prompt = """Tu es un assistant d'organisation bienveillant.
INSTRUCTIONS STRICTES :
- Réponds UNIQUEMENT en JSON valide, sans texte avant ni après, sans backticks.
- Format exact :
{"sorted": [{"id": <int>, "statut": "utile"|"futile", "explication": "<1-2 phrases>", "dependances": "<liens entre idées utiles ou null>"}]}
- "utile" = contribue à la croissance/bien-être. "futile" = distraction ou procrastination.
- Sois bienveillant(e), jamais condescendant(e).
- Langue : français uniquement."""

        items_text = "\n".join([f"- id={i['id']}: {i['texte']}" for i in items])
        raw = self.generate(system_prompt, f"Idées à trier :\n{items_text}", max_tokens=1200)
        return self._parse_json(raw).get("sorted", [])

    # =========================================================================
    # Feature 4 — Aide pourquoi/avantages (Me ressourcer)
    # =========================================================================
    def generate_why_and_advantages(self, objectif_titre: str, objectif_description: str) -> dict:
        system_prompt = """Tu es un coach de vie bienveillant.
INSTRUCTIONS STRICTES :
- Réponds UNIQUEMENT en JSON valide, sans texte avant ni après, sans backticks.
- Format exact : {"pourquoi": "...", "avantages": "..."}
- "pourquoi" : 2-3 phrases à la 1ère personne (Je...), motivation profonde et personnelle.
- "avantages" : 2-3 bénéfices concrets et émotionnels.
- Sois inspirant(e) et personnel(le), pas générique.
- Langue : français uniquement."""

        prompt = f"""Objectif : {objectif_titre}
Ce que la personne a écrit : {objectif_description}
Aide-la à formuler un pourquoi profond et des avantages concrets."""

        raw = self.generate(system_prompt, prompt, max_tokens=400)
        data = self._parse_json(raw)
        return {"pourquoi": data.get("pourquoi", ""), "avantages": data.get("avantages", "")}

    # =========================================================================
    # Feature 5 — Chatbot contextuel
    # =========================================================================
    def chat(self, messages: list, context: dict) -> str:
        """
        Chatbot contextuel avec accès aux données de l'utilisatrice.

        Parameters
        ----------
        messages : list
            Historique de la conversation [{"role": "user"|"assistant", "content": "..."}]
        context : dict
            Données de l'app : objectifs actifs, tâches du jour, capital, niveau.
        """
        goals_text = ""
        if context.get("goals"):
            goals_text = "\n".join([
                f"- {g.get('titre') or g.get('description','')[:50]} (échéance: {g.get('date_limite','?')})"
                for g in context["goals"][:5]
            ])

        tasks_text = ""
        if context.get("tasks"):
            tasks_text = "\n".join([
                f"- {t.get('titre','')} [{t.get('heure_debut','?')}-{t.get('heure_fin','?')}] ({t.get('statut','')})"
                for t in context["tasks"][:8]
            ])

        system_prompt = f"""Tu es une assistante personnelle bienveillante, motivante et organisée. Tu aides une utilisatrice à gérer ses objectifs, son planning, sa concentration et sa motivation.

CONTEXTE ACTUEL DE L'UTILISATRICE :
- Capital confiance : {context.get('capital_points', '?')} pts (niveau : {context.get('niveau_label', '?')})
- Objectifs actifs :
{goals_text or "  Aucun objectif actif pour l'instant."}
- Tâches d'aujourd'hui :
{tasks_text or "  Aucune tâche planifiée aujourd'hui."}

INSTRUCTIONS :
- Utilise le contexte ci-dessus pour donner des réponses personnalisées et pertinentes.
- Tu peux faire référence à ses objectifs et tâches spécifiques.
- Sois chaleureuse, motivante, jamais condescendante.
- Réponds de façon concise (3-5 phrases max sauf si elle demande plus de détails).
- Si elle doute d'elle-même, rappelle-lui son capital confiance et ses progrès.
- Langue : français uniquement."""

        # Construction des messages pour l'API (sans le system prompt qui est séparé)
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages += [{"role": m["role"], "content": m["content"]} for m in messages[-10:]]  # 10 derniers messages max

        # Appel direct avec messages complets (pas generate() qui reconstruit les messages)
        for model in MODEL_CASCADE:
            self._cycle = itertools.cycle(self._keys)
            self._client = self._make_client()
            for attempt in range(MAX_RETRIES_PER_MODEL * len(self._keys)):
                try:
                    response = self._client.chat.completions.create(
                        model=model,
                        max_tokens=512,
                        messages=api_messages,
                        temperature=0.7,
                    )
                    return response.choices[0].message.content.strip()
                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ["rate", "limit", "429", "quota", "capacity"]):
                        self._rotate()
                        time.sleep(RETRY_DELAY)
                    elif "model" in err and ("not found" in err or "deprecated" in err):
                        break
                    else:
                        raise
        raise IAUnavailableError("IA temporairement indisponible.")


# =============================================================================
# Singleton
# =============================================================================
_instance: Optional[LLMManager] = None

def get_llm_manager() -> LLMManager:
    global _instance
    if _instance is None:
        _instance = LLMManager()
    return _instance
