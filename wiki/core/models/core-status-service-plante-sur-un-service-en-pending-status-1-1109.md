---
id: 1109
title: "CORE / status service plante sur un service en PENDING (status 1)"
status: review
who: "Claude"
due_date: 
classified_at: 2026-09-18T10:19:43
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: core/models
section_title: "Core / models"
---

# #1109 — CORE / status service plante sur un service en PENDING (status 1)

**TL;DR** — `nagioscli status service` (et `status host`) lève `ValueError` sur un service/hôte
en **PENDING** (`status = 1`) : l'enum `ServiceStatus` / `HostStatus` ne connaît pas la valeur 1,
et la conversion `ServiceStatus(self.status)` lève **avant** que le repli `UNKNOWN(n)` prévu
juste à côté puisse s'appliquer.

## Symptôme

```
$ nagioscli status service <host> <service>
Error: 1 is not a valid ServiceStatus
```

Exit code 1, aucune sortie — même profil que ken #1104 : la commande est aveugle précisément
sur un service qui n'a pas encore de résultat de check.

Reproduction minimale :

```python
from nagioscli.core.models import Service, Host
Service(host_name="h", description="FW", status=1, plugin_output="").status_text
# ValueError: 1 is not a valid ServiceStatus
Host(name="h", address="", status=1, plugin_output="").status_text
# ValueError: 1 is not a valid HostStatus
```

## Cause

`nagioscli/core/models.py`. Nagios Core code les états sur des bits : pour un service
`PENDING=1, OK=2, WARNING=4, UNKNOWN=8, CRITICAL=16` ; pour un hôte `PENDING=1, UP=2, DOWN=4,
UNREACHABLE=8`. Les deux enums démarrent à 2 — **PENDING (1) manque**.

```python
return status_map.get(ServiceStatus(self.status), f"UNKNOWN({self.status})")
#                     ^^^^^^^^^^^^^^^^^^^^^^^^^^ lève ValueError ici
```

Le repli `f"UNKNOWN({self.status})"` est du **code mort** : `.get()` n'est jamais atteint pour
une valeur inconnue, puisque c'est la construction de l'enum (l'argument) qui lève. Tout code
d'état non prévu — PENDING aujourd'hui, un futur code demain — plante au lieu de dégrader.

## Portée

- Plantent (passent par `Service.status_text` / `Host.status_text`) :
  `status service`, `status service --json`, `status service --quiet`, et les équivalents
  `status host`.
- Ne plantent pas : `problems`, `services`, `hosts`, `check-problems` — ils passent par
  `OutputFormatter.format_service_status()` / `format_host_status()` (`cli/handlers.py`), un
  dict `dict[int, str]` sans enum. Mais ces tables **ignorent PENDING** elles aussi et
  affichent `UNKNOWN(1)`, ce qui est faux et trompeur : un service en attente de premier check
  n'est pas en UNKNOWN.

## Correctif proposé

1. `core/models.py` — ajouter `PENDING = 1` à `ServiceStatus` et à `HostStatus`, et l'ajouter
   aux deux tables `status_map`.
2. `core/models.py` — rendre `status_text` réellement tolérant : indexer la table par `int`
   (`status_map.get(self.status, f"UNKNOWN({self.status})")`) au lieu de construire l'enum.
   Le repli redevient vivant et un code d'état inconnu s'affiche au lieu de planter.
3. `cli/handlers.py` — ajouter `1: "PENDING"` aux deux tables de `OutputFormatter` pour que
   `problems` / `services` / `hosts` cessent d'afficher `UNKNOWN(1)`.
4. **Décision à prendre** : `Service.is_problem` / `Host.is_problem` valent aujourd'hui
   `status != OK` / `status != UP`, donc **PENDING compte comme un problème**. À confirmer :
   un check jamais exécuté n'est pas un état d'erreur, et `get_problems()` filtre déjà côté
   serveur sur `warning critical unknown` — PENDING ne remonte donc jamais dans `problems`.
   L'incohérence est aujourd'hui invisible mais réelle.

## Tests de non-régression

- `Service(status=1).status_text == "PENDING"` et idem `Host`.
- Un code d'état inconnu (ex. `status=99`) rend `"UNKNOWN(99)"` **sans lever** — c'est le repli
  qui était mort.
- Bout en bout CLI : `status service` / `status host` sur une réponse `statusjson.cgi` avec
  `"status": 1`, en texte, `--json` et `--quiet`, exit 0.
- `OutputFormatter.format_service_status(1) == "PENDING"`.

## Contexte

Signalé par l'utilisateur en production. Même famille que ken #1104 (une valeur inattendue dans
la réponse Nagios fait planter toute la commande au lieu de dégrader proprement).


---

## Résolution

### Modifications

- **`nagioscli/core/models.py`** — `PENDING = 1` ajouté à `ServiceStatus` **et** `HostStatus`,
  avec l'entrée correspondante dans les deux `status_map`. Docstrings des enums référencent
  désormais les macros `SERVICE_*` / `HOST_*` de `cgiutils.h` (Nagios Core), source des valeurs.
- **`nagioscli/core/models.py`** — le repli redevient vivant : `status_map` est typée
  `dict[int, str]` et la recherche se fait sur l'`int` brut
  (`status_map.get(self.status, f"UNKNOWN({self.status})")`) au lieu de
  `status_map.get(ServiceStatus(self.status), ...)`. C'était la vraie cause : la conversion
  d'enum levait sur l'**argument**, donc le `.get()` et son défaut n'étaient jamais atteints.
  N'importe quel code d'état futur dégrade maintenant en `UNKNOWN(n)` au lieu de planter.
- **`nagioscli/core/models.py`** — `is_problem` : PENDING n'est plus un problème
  (`status not in (PENDING, OK)` / `(PENDING, UP)`). Un check jamais exécuté n'est pas un état
  d'erreur. Aucun chemin de production n'en dépendait (`get_problems()` filtre déjà côté serveur
  sur `warning critical unknown`, `is_problem` n'était lu que par les tests).
- **`nagioscli/cli/handlers.py`** — `1: "PENDING"` ajouté aux deux tables de `OutputFormatter`,
  qui affichaient `UNKNOWN(1)` dans `problems` / `services` / `hosts` / `check-problems`.
- **Tests (+14, 169 → 183)** — `test_models.py` : PENDING service + hôte (texte et
  `is_problem is False`), code non mappé `99` → `"UNKNOWN(99)"` sans lever, `PENDING == 1` dans
  les deux enums ; `test_handlers.py` : `(1, "PENDING")` ajouté aux deux paramétrages ;
  `test_cli_commands.py` : `status service` en texte, `--json` et `--quiet`, et `status host`,
  sur un état PENDING.

### Autres valeurs manquantes — vérification demandée

Revue des bitmasks Nagios Core (`include/cgiutils.h`), qui sont ce que renvoie le champ
`status` de `statusjson.cgi` :

- service : `PENDING 1`, `OK 2`, `WARNING 4`, `UNKNOWN 8`, `CRITICAL 16` — **complet** après ce
  correctif.
- hôte : `PENDING 1`, `UP 2`, `DOWN 4`, `UNREACHABLE 8` — **complet** après ce correctif.

PENDING était donc le seul trou dans les deux enums. Les autres champs énumérés de la réponse
(`state_type` 0/1, `acknowledgement_type` 0/1/2) sont manipulés comme des entiers et ne passent
par aucune conversion d'enum : ils ne peuvent pas lever. Le repli vivant couvre de toute façon
tout code ajouté en amont par une version future de Nagios.

### Comportements obtenus

- Exécution réelle du binaire contre un faux `statusjson.cgi` servant `"status": 1` :
  `status service` → exit 0, `Status: PENDING` ; `--quiet` → `PENDING` ; `status host` →
  exit 0, `Status: PENDING`. Avant : `Error: 1 is not a valid ServiceStatus`, exit 1, sans sortie.
- `problems` / `services` / `hosts` affichent `PENDING` au lieu de `UNKNOWN(1)`.
- Sans le correctif, 9 des tests ajoutés échouent — chaque comportement est couvert.

### Garde-fous

- `pdm run check` vert : ruff, black, mypy strict, import-linter, vulture, refurb,
  **183 tests**, couverture 94 %, `core/models.py` et `cli/handlers.py` à **100 %**,
  metrics gate palier 1 PASS.
- `dict[int, str]` explicite sur les deux `status_map` : mypy strict refuserait sinon une
  recherche par `int` dans une table indexée par membres d'enum.
---

[← retour à core/models](index.md) · [voir log](../../log.md)
