# 📈 Bourse Casa — Actualisation automatique des cours

Ce repo met à jour automatiquement les cours de la Bourse de Casablanca depuis **CDG Capital Bourse**, deux fois par jour (matin et clôture), et publie le résultat dans `data/cours.json`.

## 🚀 Installation (10 minutes)

### Étape 1 — Créer le repo GitHub

1. Connecte-toi à [github.com](https://github.com)
2. Cliquer **"New repository"**
3. Nom : `bourse-casa-cours` (ou ce que tu veux)
4. Cocher **"Public"** (obligatoire pour que Netlify puisse lire le JSON)
5. Cliquer **"Create repository"**

### Étape 2 — Uploader les fichiers

Glisser-déposer tous ces fichiers dans le repo :
```
scraper.py
data/cours.json
.github/workflows/update-cours.yml
README.md
```

Ou via Git :
```bash
git clone https://github.com/TON_USERNAME/bourse-casa-cours
# Copier les fichiers dans le dossier
git add .
git commit -m "Setup scraper cours bourse"
git push
```

### Étape 3 — Activer GitHub Actions

1. Aller dans l'onglet **Actions** de ton repo
2. Cliquer **"I understand my workflows, go ahead and enable them"**
3. ✅ C'est tout — le script tournera automatiquement !

### Étape 4 — Récupérer l'URL du JSON

L'URL de ton `cours.json` sera :
```
https://raw.githubusercontent.com/TON_USERNAME/bourse-casa-cours/main/data/cours.json
```

**Remplace `TON_USERNAME` par ton nom d'utilisateur GitHub.**

Donne cette URL à Claude pour qu'il l'intègre dans ton tableau de bord Netlify.

### Étape 5 — Tester manuellement

1. Aller dans **Actions** → **"Actualisation cours Bourse de Casablanca"**
2. Cliquer **"Run workflow"** → **"Run workflow"**
3. Attendre ~2 minutes
4. Vérifier que `data/cours.json` est mis à jour

## 📅 Planning automatique

| Heure (Maroc) | Action |
|---|---|
| 10h00 | Cours d'ouverture |
| 16h30 | Cours de clôture |
| Weekend | Aucune action |

## 📋 Format du cours.json

```json
{
  "date": "2026-04-06",
  "time": "16:30",
  "source": "CDG Capital Bourse",
  "count": 78,
  "cours": {
    "ATW": 690.0,
    "BCP": 248.2,
    "IAM": 95.2
  }
}
```

## ❓ Dépannage

- **Actions ne se lancent pas** : Vérifier que le repo est Public et que Actions est activé
- **0 cours récupérés** : Le site CDG peut bloquer les robots. Essayer le lancement manuel.
- **Erreur playwright** : Normal si le site change de structure, contacter Claude pour mettre à jour le scraper
