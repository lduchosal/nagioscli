---
id: 1134
title: "VSCODE / Service groups et host groups dans l'arbre"
status: review
who: "Claude"
due_date: 
classified_at: 2026-10-02T20:58:36
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: vscode
section_title: "VS Code extension"
---

# #1134 — VSCODE / Service groups et host groups dans l'arbre

**TL;DR** — l'arbre de l'extension n'avait ni groupes de services ni groupes d'hôtes → ajout de « Service groups » et « Host groups » (objectjson.cgi), chaque groupe avec son nombre de membres et ses problèmes, dépliable vers ses services / hôtes (puis services) avec leur état.

dans la liste de l'extension, peux-tu ajouter:
> services groups
  - service group 1
  - service group 2
> host groups
  - host group 1
  etc ...

---

## Résolution

### Modifications
- `vscode/src/api.js` : `jsonCgi()` commun statusjson / objectjson ; `listServiceGroups()` / `listHostGroups()` (objectjson.cgi `*grouplist&details=true`, triés, liste de noms nue tolérée) ; `listGroupServices()` / `listGroupHosts()` (statusjson filtré `servicegroup=` / `hostgroup=`) ; `groupUrl()` (status.cgi `style=overview`).
- `vscode/src/status.js` : `serviceGroupProblems()` / `hostGroupProblems()`, `groupDescription()` (« 2 members · 1 problem »), `groupIcon()` (rouge non traité, atténué si tout est acquitté / en downtime, vert sinon).
- `vscode/src/extension.js` : racines « Service groups » et « Host groups » (repliées) après « All hosts » ; nœuds groupe dépliables ; services d'un service group affichés « hôte / service » ; hôtes d'un host group dépliables vers leurs services ; `path` dans les nœuds pour des ids uniques quand un même hôte / service apparaît sous plusieurs parents ; « Open in Nagios » sur un groupe.
- `vscode/package.json` : menu contextuel « Open in Nagios » sur `hostgroup` / `servicegroup`.
- Docs : `vscode/README.md`, README, ARCHITECTURE.md.

### Comportements obtenus
- Un groupe montre ses membres et ses problèmes sans requête supplémentaire (calculés depuis la liste des problèmes déjà chargée) ; ses membres sont chargés au dépliage.
- Erreur de chargement d'un groupe (ex. 403) : ligne message sous le groupe, le reste de l'arbre intact.

### Garde-fous
- `./publish.sh --quality` : 18/18 vert.
- Extension : 81/81 tests (+10), couverture 100 % lignes / 99,05 % branches / 99,38 % fonctions ; biome et tsc 0.
---

[← retour à vscode](index.md) · [voir log](../log.md)
