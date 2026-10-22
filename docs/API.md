# API JSON

Préfixe `/api`. Les appels authentifiés utilisent `Authorization: Bearer <token>`. Erreurs : `{ "error": "code_stable" }`, traduites dans le navigateur. Les listes sont limitées à l’utilisateur connecté ; les routes administrateur nécessitent son rôle.

| Méthode | Route | Fonction |
|---|---|---|
| POST | `/auth/register` | `{name,email,password}` ; envoi de confirmation |
| POST | `/auth/verify` | `{token}` ; consommation du lien |
| POST | `/auth/resend` | `{email}` ; nouveau lien |
| POST | `/auth/login` | `{email,password}` → `{token,user}` |
| GET | `/auth/me` | Session courante |
| POST | `/auth/logout` | Révocation de la session |
| POST | `/auth/forgot` | `{email}` ; demande de récupération |
| POST | `/auth/reset` | `{token,password}` ; changement et révocation des sessions |
| GET / POST | `/cases` | Liste ou création administrateur `{title,description,language:fr\|ar}` |
| GET / DELETE | `/cases/:id` | Détail ou suppression d’un dossier |
| POST | `/cases/:id/documents` | Multipart `file`, `kind:offer\|tender` |
| GET / DELETE | `/documents/:id` | Texte extrait ou suppression d’une pièce |
| POST | `/documents/:id/download` | Lien signé de 120 secondes |
| POST | `/documents/:id/retry` | Relance de lecture après échec |
| POST | `/cases/:id/analyses` | Nouvelle version, traitement asynchrone |
| GET | `/analyses/:id` | État, progression et rapport |
| GET | `/analyses/:id/passages/:passage_id` | Passage du snapshot, sans dépendance au fichier courant |
| POST | `/analyses/:id/retry` | Relance de la même version après échec |
| GET | `/analyses/:id/pdf` | Rapport PDF privé |
| GET / POST | `/admin/references` | Corpus / dépôt multipart avec métadonnées |
| PATCH | `/admin/references/:id` | `{publication,reviewed?,chunks?,replaces?}` |
| GET | `/admin/users` | Comptes et nombre de versions d’analyse |
| PATCH | `/admin/users/:id` | `{suspended:boolean}` ; hors administrateurs |
| GET | `/admin/jobs` | 100 dernières tâches actives/échouées de chaque type, sans contenu |
| POST | `/admin/jobs/:kind/:id/retry` | Relance opérationnelle |
| GET | `/health` | Connectivité base et disponibilité de la configuration IA |

Référence multipart : `file,title,authority,date` (ISO YYYY-MM-DD), `version,language,applicability`.

Rapport : `summary,findings[],limitations[],references[],language`. Un constat contient `requirement_id,title,status,severity,explanation,missing[],correction,citations[],tender_citation`. Statuts : `conforme,non_conforme,a_verifier,non_applicable`. Une citation conserve `passage_id,quote,document_id,document_name,location,kind`.

## Chat utilisateur

- `GET /chats` : historique privé et disponibilité de l’IA.
- `POST /chats` : initialisation automatique `{language}` au premier envoi ou dépôt de pièce ; aucun titre demandé.
- `GET /chats/:id` : messages, pièces jointes et avis antérieurs.
- `POST /chats/:id/messages` : `{content,language,intent?:message|analysis}`. Un avis complet est rattaché au fil ; les questions de suivi sont traitées par Celery et citent leurs sources.
- `POST /chats/:id/messages/:messageId/retry` : relance de réponse en échec.
- `GET /chats/:id/messages/:messageId/passages/:passageId` : passage conservé avec la réponse.

Les messages et leurs sources sont supprimés avec la conversation. Les documents et exports utilisent les routes privées existantes ; ils ne nécessitent aucune gestion de dossier dans l’interface utilisateur.
