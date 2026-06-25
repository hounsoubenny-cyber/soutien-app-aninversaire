Parfait ! Voici un README complet en français et une licence MIT adaptée à ton projet.  

---

## 📄 README.md

```markdown
# Soutien App — Coach personnel pour objectifs, planning et focus

**Soutien App** est une application web tout-en-un qui t’accompagne au quotidien pour :

- Définir et suivre tes **objectifs** (avec étapes et progression)
- Planifier tes **tâches** dans un agenda journalier
- Utiliser un **mode focus** (Pomodoro amélioré)
- Bénéficier d’une **IA bienveillante** (via Groq) pour t’aider à structurer tes idées
- Garder une trace de tes **doutes** et de ta **confiance** grâce à un système de points

L’application est **mono-utilisateur** et protégée par un **PIN** (hashé avec bcrypt).  
Elle est construite avec **FastAPI** (backend) et **React** (frontend, non fourni ici).

---

## ✨ Fonctionnalités principales

- **Objectifs** : crée des objectifs avec date limite, ajoute des étapes (manuelles ou générées par IA), visualise ta progression.
- **Planning journalier** : crée, modifie, termine ou reporte des tâches. Détection automatique des conflits d’horaire.
- **Brain dump** : dépose toutes tes idées, l’IA les trie en « utiles » ou « futiles » avec explications.
- **Mode focus** : lance des sessions de concentration (durée au choix), avec pause (10 % du temps) et gain/perte de points.
- **Capital confiance** : système de points qui évolue selon tes actions (tâches terminées, étapes franchies, focus réussi). Niveaux symboliques pour te motiver.
- **Journal des doutes** : note tes moments de doute, l’application analyse les tendances.
- **Chatbot contextuel** : discute avec l’IA qui connaît tes objectifs et tâches du jour.
- **API REST complète** (documentation automatique Swagger disponible).

---

## 🛠 Stack technique

- **Backend** : Python 3.10+, FastAPI, SQLModel (ORM), SQLite, bcrypt, python-dotenv
- **IA** : Groq API (avec rotation automatique de clés et fallback de modèles)
- **Rate limiting** : slowapi
- **Frontend** : React (non inclus dans ce dépôt, mais build attendu dans `frontend/build`)

---

## 📦 Installation

### 1. Cloner le dépôt
```bash
git clone https://github.com/ton-utilisateur/soutien-app.git
cd soutien-app
```

### 2. Créer un environnement virtuel Python
```bash
python -m venv venv
source venv/bin/activate  # sur Windows : venv\Scripts\activate
```

### 3. Installer les dépendances
Crée un fichier `requirements.txt` avec le contenu suivant :

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlmodel==0.0.14
bcrypt==4.1.2
python-dotenv==1.0.0
groq==0.9.0
slowapi==0.1.9
pydantic==2.5.3
python-multipart==0.0.6
```

Puis :
```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d’environnement
Crée un fichier `.env` à la racine du projet (ou dans le dossier `backend/`) :

```env
# Clés API Groq (au moins une, tu peux en mettre plusieurs pour la rotation)
GROQ_API_KEY_1=votre_cle_groq_1
GROQ_API_KEY_2=votre_cle_groq_2   # optionnel

# Modèle par défaut (optionnel, défaut : llama-3.3-70b-versatile)
GROQ_MODEL=llama-3.3-70b-versatile
```

> **Note** : Si tu n’as pas de clé Groq, l’application fonctionnera sans IA (les endpoints IA retourneront une indisponibilité).
---

## 🚀 Lancer l’application

Depuis la racine du projet, avec l’environnement virtuel activé :

```bash
python backend/main.py
```

Ou avec uvicorn directement :
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 9000 --reload
```

L’API sera disponible sur `http://localhost:9000`  
La documentation Swagger : `http://localhost:9000/docs`

---

## 🔧 Utilisation de l’API

### PIN et sécurité
Tous les endpoints (sauf `/config/set_pin` et `/config/check_pin`) nécessitent un PIN valide.  
Le PIN est défini via `POST /config/set_pin` (hashé automatiquement) ou via `POST /config/check_pin` (si non configuré, il le définit).

### Exemple d’appel (création d’une tâche)
```bash
curl -X POST http://localhost:9000/tasks/create \
  -H "Content-Type: application/json" \
  -d '{
    "pin": "1234",
    "titre": "Réviser le chapitre 3",
    "date": "2026-06-26",
    "heure_debut": "14:00",
    "heure_fin": "15:30"
  }'
```

### Endpoints principaux
- **Config** : `/config/*`
- **Tâches** : `/tasks/*`
- **Objectifs** : `/goals/*`
- **IA** : `/ai/*`
- **Focus** : `/focus/*`
- **Brain dump** : `/braindump/*`
- **Doutes** : `/doubt/*`

Tous les schémas de données sont documentés dans Swagger.

---

## 🗂 Structure du projet

```
soutien-app/
├── backend/
│   ├── backend/
│   │   ├── api/                 # config (IP, PORT, chemins)
│   │   ├── core/                # logique métier
│   │   │   ├── db_manager.py    # modèles SQLModel + gestionnaire DB
│   │   │   ├── llm_manager.py   # client Groq + rotation clés/modèles
│   │   │   ├── router.py        # endpoints principaux
│   │   │   └── ai_router.py     # endpoints IA (avec gestion d’indisponibilité)
│   │   └── utils/               # rate limiter
│   └── main.py                  # point d’entrée FastAPI
├── frontend/                    # (optionnel) code React
├── .env                         # variables d’environnement
└── README.md
```

---

## 🤝 Contribution

Les contributions sont les bienvenues !  

---

## 📄 Licence

Ce projet est sous licence MIT (voir le fichier `LICENSE`).

---

## 🙏 Remerciements

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/)
- [Groq](https://groq.com/) pour l’IA
- [SlowAPI](https://github.com/laurentS/slowapi) pour le rate limiting
- [bcrypt](https://github.com/pyca/bcrypt/)
```
