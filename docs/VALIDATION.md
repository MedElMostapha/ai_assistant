# Vérifications réalisées — 22 octobre 2026

- **31 tests serveur réussis**, avec SQLite puis avec PostgreSQL 17 et l’extension pgvector dans une base jetable distincte.
- **3 tests frontend réussis** ; compilation TypeScript et build Vite réussis.
- Audit npm après installation : **0 vulnérabilité signalée**.
- Migrations appliquées à la stack réelle ; `flask db check` ne détecte aucune différence de schéma.
- Parcours réel dans Chromium : inscription, livraison SMTP via Mailpit, confirmation d’e-mail, connexion, création du dossier, dépôt de deux fichiers DOCX dans S3 et extraction par Celery.
- Administration dans Chromium : dépôt d’une référence fictive, aperçu du texte, refus de publication sans relecture, publication, archivage, listes des utilisateurs et des traitements.
- Rendu français/arabe, direction RTL, affichage mobile 390 px et absence de débordement horizontal contrôlés sur le parcours utilisateur.
- OCR réel Tesseract vérifié sur des pages françaises et arabes transformées en images sans texte sélectionnable.
- Rapports PDF de test français et arabe générés, rendus et inspectés visuellement sur toutes leurs pages.
- Vérification effective du refus des requêtes S3 anonymes de liste et de lecture lors de l’initialisation.

Les documents fictifs, le dossier et le compte de contrôle ont été supprimés après les tests. Aucun compte administrateur avec mot de passe par défaut n’est laissé dans l’application.

## À valider avec les accès métier

L’analyse par le fournisseur externe n’a pas été exécutée avec une clé réelle. Les tests du pipeline utilisent des réponses structurées contrôlées pour vérifier les citations, erreurs et reprises. Configurer la clé et le modèle, charger des sources validées, puis évaluer les rapports sur un corpus relu par un juriste. Évaluer en particulier la couverture de la recherche lexicale et les correspondances entre documents de langues différentes.

Le SMTP de production, le domaine HTTPS, les sauvegardes et la politique de conservation restent à configurer pour l’hébergement public. La stack actuelle écoute localement sur le port 8088.

## Parcours chat utilisateur

L’utilisateur normal arrive directement dans le chat. Le navigateur a vérifié l’absence de création de dossier, l’envoi et la persistance des messages après rechargement, l’ajout de l’offre et de l’appel d’offres via le trombone, leur lecture asynchrone, l’historique, la suppression de la conversation et la déconnexion. Le rendu RTL et mobile (390 px) a été contrôlé avec une zone de messages défilante et une saisie séparée. Les tests serveur couvrent aussi la confidentialité du chat, les citations conservées, le lancement de l’avis depuis un message, la relance sans doublon et le refus de modification pendant une réponse.
