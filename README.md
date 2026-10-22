# Amanah · أمانة

Application d’aide à la préparation juridique des offres aux marchés publics mauritaniens. **Flask + React/TypeScript + PostgreSQL/pgvector**, interface français/arabe avec lecture RTL.

## Lancer en local

Prérequis : Docker Engine et Docker Compose.

```bash
cp .env.example .env
# Remplacer les trois valeurs CHANGE_ME par des secrets aléatoires.
docker compose up --build -d
docker compose exec api flask --app app create-admin
```

L’interface est accessible à **http://localhost:8080**. Si le port est déjà utilisé, changer `WEB_PORT` et `FRONTEND_URL` dans `.env`. Dans cet espace de travail, le port **8088** est utilisé. La boîte de réception locale est accessible à **http://localhost:8025** : les liens de confirmation et de récupération y arrivent pendant le développement. Aucun compte ni mot de passe administrateur n’est fourni par défaut. La commande `create-admin` demande le nom, l’adresse et un mot de passe de 12 caractères minimum.

Dans cet espace de travail, un `.env` local non versionné a été généré avec des secrets aléatoires. Ne le remplacez pas si les volumes de base de données ont déjà été initialisés avec ces valeurs.

## Activer l’IA

Renseigner `AI_API_KEY` et `AI_MODEL` dans `.env`, puis recréer **les deux** services :

```bash
docker compose up -d --force-recreate api worker
```

Le fournisseur par défaut expose l’API Responses d’OpenAI et les sorties structurées strictes. `AI_BASE_URL` permet un fournisseur compatible avec cette interface. Il n’y a pas de mode simulant un avis en production. Choisir un modèle prenant en charge JSON Schema strict et vérifier ses conditions de confidentialité avant d’utiliser des offres réelles.

L’implémentation suit la [documentation officielle OpenAI des sorties structurées](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) et désactive la conservation applicative des réponses avec `store: false`. Cela ne remplace pas la vérification des politiques de conservation du fournisseur.

## Parcours

1. Créer un compte, confirmer l’e-mail puis se connecter : l’utilisateur arrive directement dans le chat.
2. Écrire une question ou utiliser le trombone pour joindre l’offre et l’appel d’offres. Aucun dossier ni formulaire de titre n’est demandé.
3. Les documents sont lus en arrière-plan ; leur état apparaît au-dessus de la zone de saisie.
4. Demander l’analyse dans le chat. L’avis, ses citations et son export PDF apparaissent dans la conversation.
5. Poser des questions de suivi. L’historique des conversations permet de retrouver les échanges ; le bouton « Nouvelle conversation » ouvre un chat vide sans étape de création.

Les anciens dossiers restent accessibles comme conversations, avec leurs documents et avis. L’administration conserve ses écrans de gestion. Les conteneurs appliquent automatiquement la migration des messages au prochain lancement. Les questions de suivi sont limitées à 30 réponses IA par utilisateur et par jour, réglables avec `DAILY_CHAT_MESSAGES` ; les avis complets conservent leur quota de 5 par jour.

L’administrateur ajoute les sources juridiques, vérifie et corrige le texte extrait, renseigne leur applicabilité et confirme la relecture avant publication. Une nouvelle version peut remplacer une référence publiée ; les anciens rapports conservent leur propre copie. L’administrateur voit les comptes, la consommation et les métadonnées des tâches, sans accès aux offres des autres utilisateurs.

## Architecture

- `frontend/` : React, Vite, TypeScript, traductions complètes FR/AR, affichage mobile et RTL.
- `backend/app/` : application Flask, API JSON, SQLAlchemy, commandes CLI et authentification.
- `backend/migrations/` : schéma initial Alembic et support des évolutions.
- PostgreSQL 17 avec extension pgvector ; Redis pour Celery et les limites de requêtes.
- Stockage S3 privé avec SeaweedFS, exposé uniquement au réseau Docker. L’accès des navigateurs passe par des liens applicatifs signés de deux minutes.
- Tesseract français/arabe pour les scans ; PyMuPDF et python-docx pour les documents ; WeasyPrint pour les PDF avec composition arabe.

### Analyse et traçabilité

Tous les fragments du dossier d’appel d’offres sont examinés pour extraire les exigences, avec citation exacte. Pour chaque exigence, le serveur recherche les passages de l’offre et des références publiées, puis demande un constat structuré. Les citations sont validées côté serveur : un identifiant inconnu ou un extrait non exact entraîne l’échec de l’analyse. Le résumé s’appuie sur les constats validés.

**Limite actuelle :** la recherche utilise des vecteurs de hachage lexical multilingue locaux (256 dimensions), conservés dans pgvector ; ce ne sont pas des embeddings sémantiques. Elle peut manquer des paraphrases et des correspondances entre deux langues différentes. Les résultats indiquent la recherche partielle et les éléments non trouvés restent à vérifier. Valider la qualité sur un corpus métier et remplacer ce moteur par un modèle d’embeddings multilingue évalué avant ouverture publique.

Les documents, leurs empreintes, les passages et les métadonnées de sources sont figés dans chaque analyse. Les contenus publiés ne sont plus éditables. Les instructions présentes dans les documents sont traitées comme des données non fiables ; les prompts en interdisent l’exécution. Cette protection et les vérifications de citations réduisent les erreurs sans garantir l’exactitude juridique.

Limites initiales configurables : 25 Mo/fichier, 20 fichiers et 500 pages/dossier, 5 nouvelles analyses/utilisateur/jour UTC. Les pages DOCX sont estimées à 2 500 caractères, car ce format ne fournit pas de pagination physique fiable. Au-delà de 120 exigences, le traitement demande de séparer les lots au lieu d’omettre silencieusement des exigences. Une version échouée peut être relancée jusqu’à trois exécutions, sans créer de rapport supplémentaire ni consommer un nouveau quota de version. Un nouvel avis crée une nouvelle version.

### Confidentialité

Les mots de passe utilisent scrypt (Werkzeug). Les jetons de session, vérification et récupération sont aléatoires ; seule leur empreinte est conservée. Les liens de vérification/récupération expirent et ne sont utilisables qu’une fois. Le changement de mot de passe et la suspension révoquent les sessions. Le navigateur conserve le jeton de session dans `sessionStorage` ; les appels utilisent l’en-tête Authorization, sans cookie d’authentification.

Les journaux applicatifs ne contiennent pas le texte des offres ni les clés d’API. Les téléchargements passent par un lien signé court et revérifient le compte et la propriété du dossier. Supprimer un dossier supprime les rapports et les données extraites, puis programme la suppression des objets. En cas de panne de stockage, la file `storage_garbage` conserve les suppressions à retenter.

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
cd backend
../.venv/bin/pytest -q
cd ../frontend
npm ci
npm test
npm run build
```

Les tests unitaires utilisent SQLite pour leur isolation. La variable `TEST_DATABASE_URL` permet les mêmes tests contre une **base PostgreSQL de test dédiée avec l’extension vector déjà activée**. Cette base doit être jetable : les tables sont créées et supprimées par les fixtures. Ne jamais utiliser la base de production.

Les tests vérifient les droits, confirmations, récupération, suspension, fichiers invalides, extraction DOCX, OCR indisponible, publication/relecture/remplacement, snapshots historiques, quota, citations inventées et reprise après panne du fournisseur. Les appels IA sont remplacés dans les tests ; une clé réelle est nécessaire pour une évaluation du fournisseur.

## Exploitation

```bash
# Appliquer des migrations après mise à jour
docker compose run --rm api flask --app app db upgrade
# Réessayer les suppressions d’objets en échec
docker compose exec api flask --app app collect-garbage
# Débloquer les tâches interrompues depuis plus de deux heures
docker compose exec api flask --app app recover-jobs
# Vérifier les services
docker compose ps
```

Planifier les deux commandes de maintenance avec l’ordonnanceur de l’hébergement. Les tâches devenues « échec » peuvent ensuite être relancées dans l’interface. Une relance garde le même modèle et les mêmes sources. Les résultats Celery ne sont pas stockés dans Redis ; les rapports restent dans PostgreSQL.

Avant mise en production : remplacer Mailpit par un SMTP réel avec TLS, fixer `FRONTEND_URL` au domaine HTTPS, placer le service web derrière un proxy TLS, sauvegarder et chiffrer PostgreSQL et les objets, définir la politique de rétention des sauvegardes et surveiller les erreurs/quotas. Seuls les ports locaux web et Mailpit sont exposés dans Compose. Ne pas exposer Mailpit publiquement. Les secrets locaux n’ont pas vocation à être utilisés en production. Le compte PostgreSQL de déploiement initial peut créer l’extension ; utiliser ensuite un rôle applicatif restreint.

Faire relire un corpus de rapports par un juriste des marchés publics mauritaniens avant ouverture aux entreprises. Aucun texte juridique mauritanien n’est inventé ou préchargé dans la base.
