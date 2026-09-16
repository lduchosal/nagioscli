---
id: 1104
title: "NAGIOSCLI / Decodage UTF-8 strict - une sortie de plugin en cp1252 fait planter la commande entiere"
status: review
who: "luc.duchosal"
due_date: 
classified_at: 2026-09-16T17:57:35
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: core/client
section_title: "Core / client"
---

# #1104 — NAGIOSCLI / Decodage UTF-8 strict - une sortie de plugin en cp1252 fait planter la commande entiere

**TL;DR** — `nagioscli` decode la reponse HTTP de Nagios en UTF-8 strict : un seul octet cp1252
dans la sortie d'un plugin fait planter la commande entiere, sans aucun affichage. Vecu en
production sur un hote Windows a locale francaise (ken #1585).

## Symptome

```
$ nagioscli status service petit-tonnerre.arcantel.dev FW -c nagioscli.ini
Error: 'utf-8' codec can't decode byte 0xae in position 523: invalid start byte
```

Exit code 1, **aucune sortie utile**. Idem avec `--json`. Le meme hote repond normalement a
`nagioscli services <host>` (qui n'affiche que les statuts, pas `plugin_output`) — d'ou un
diagnostic trompeur : on croit le service injoignable alors que le check tourne tres bien et que
c'est le client qui ne sait pas lire la reponse.

Version constatee : **nagioscli 0.1.26** (PyPI `nachos`), Python 3.14 sous Windows.

## Cause

`nagioscli/core/client.py`, methode `_request()` :

```python
response = opener.open(request, timeout=self.config.timeout)
content = response.read().decode("utf-8")      # <-- strict
```

`statusjson.cgi` renvoie la sortie du plugin **telle quelle**, sans normalisation d'encodage.
Ici le plugin est un `check_by_ssh` vers un Windows a **locale francaise** : PowerShell produit son
message d'erreur en **cp1252**, avec des guillemets francais et des accents. Les octets `0xab`
`0xbb` (« ») et `0xe8` (e accent grave) ne sont pas de l'UTF-8 valide, et le `.decode()` leve.

Comme le decodage precede `json.loads`, l'exception remonte avant meme l'analyse de la reponse :
la commande ne peut rien afficher, pas meme les champs sains.

Sortie reelle de l'hote (lue en contournement) :

```
UNKNOWN - check_by_ssh: Remote command execution failed: L'argument
«c:/programdata/nagioscmd/scripts/check_win_firewall.ps1» du parametre -File n'existe pas.
```

## Incoherence interne

Le meme fichier decode **deja** en mode tolerant ailleurs — `_csrf_preflight()` :

```python
body = response.read().decode("utf-8", errors="replace")
```

Le correctif consiste donc a aligner `_request()` sur ce qui est deja fait a deux lignes de la.

## Correctif propose

1. `core/client.py::_request()` — `decode("utf-8", errors="replace")`. Un caractere de
   remplacement dans un message d'erreur de plugin est infiniment preferable a une commande qui
   ne rend rien. Verifier s'il reste d'autres `decode("utf-8")` stricts dans le module.
2. Option plus fine si le caractere de remplacement gene : tenter `utf-8`, puis `cp1252` en
   repli, puis `errors="replace"`. Nagios Core ne declare pas d'encodage, la sortie d'un plugin
   est un flux d'octets arbitraire — aucune hypothese n'est sure, seul le repli l'est.
3. Cote affichage Windows, le meme probleme existe en sortie : imprimer un caractere hors cp1252
   sur la console leve `UnicodeEncodeError: 'charmap' codec can't encode`. Reconfigurer
   `sys.stdout` avec `errors="replace"` au demarrage de la CLI evite de deplacer le plantage
   d'un cran.

## Test de non-regression

Un test qui stube la reponse HTTP avec un corps JSON dont un champ `plugin_output` contient des
octets cp1252 bruts (`0xab`, `0xae`, `0xbb`, `0xe9`) et qui verifie que `status service` rend un
resultat au lieu de lever. C'est exactement le cas de production, et il n'est couvert par aucun
test aujourd'hui.

## Contournement actuel

Interrogation directe de `statusjson.cgi` avec la meme auth (`X-API-Key`) et un decodage
tolerant :

```python
body = urllib.request.urlopen(req, context=ctx).read().decode("utf-8", errors="replace")
d = json.loads(body)["data"]["service"]
print(d["plugin_output"], d["long_plugin_output"])
```

Sous Windows, lancer avec `PYTHONIOENCODING=utf-8:replace`.

## Impact

Tout hote Windows du parc a locale non anglaise peut rendre `nagioscli` aveugle sur ses services
des qu'un plugin echoue — c'est-a-dire **precisement au moment ou on en a besoin**. Le parc
compte plusieurs postes dans ce cas.

---

## Résolution

### Modifications

- **`nagioscli/core/encoding.py`** (nouveau) — `decode_body(raw)` : décode en UTF-8 avec un
  gestionnaire d'erreurs codec enregistré (`nagioscli.cp1252_fallback`). Option 2 du ticket,
  mais **par segment** et non sur le corps entier : l'UTF-8 valide est conservé tel quel, seul
  chaque segment d'octets indécodable est relu en cp1252, et les octets que cp1252 ne définit
  pas (`0x81`, `0x8d`, `0x8f`, `0x90`, `0x9d`) deviennent U+FFFD. Un repli « tout le corps en
  cp1252 » aurait abîmé les accents UTF-8 légitimes du reste de la réponse (alias d'hôtes, etc.).
  Linéaire : un seul passage du décodeur, pas de boucle de ré-essais. Module séparé car
  `client.py` passait à 620 lignes, au-dessus du plafond absolu de 600 du gate.
- **`nagioscli/core/client.py`** — les **trois** points de lecture passent par `decode_body` :
  `_request()` (statusjson.cgi, le cas du ticket), `_post()` (cmd.cgi, **aussi strict** : un
  `ack`/`check` pouvait planter après avoir réussi côté Nagios) et `_csrf_preflight()` (déjà en
  `errors="replace"`, aligné). Il ne reste aucun `decode("utf-8")` strict dans le client ;
  `self_update.py` garde le sien (JSON PyPI, UTF-8 garanti).
- **`nagioscli/cli/__init__.py`** — `_tolerate_unencodable_stdout()`, appelé dans le callback
  du groupe `main` : si `sys.stdout` est un `TextIOWrapper` en `errors="strict"`, il est
  reconfiguré en `errors="replace"` (point 3). Une politique non stricte choisie par
  l'utilisateur (`PYTHONIOENCODING=utf-8:backslashreplace`) est conservée. Click renvoie
  `sys.stdout` tel quel quand il est compatible, donc `click.echo` en bénéficie.
- **`tests/unit/test_encoding.py`** (nouveau, 14 tests) — décodeur (UTF-8 intact, cp1252 relu,
  mélange UTF-8 + cp1252, octet de tête UTF-8 tronqué qui n'avale pas l'ASCII suivant, octet
  indéfini → U+FFFD) ; client (`get_service_status` avec `0xab 0xae 0xbb 0xe8 0xe9` bruts,
  `acknowledge_service` avec HTML cp1252 au preflight et au POST) ; **non-régression CLI de
  bout en bout** : vrai `NagiosClient`, seul l'opener est stubé, `status service` texte et
  `--json` ; stdout cp1252 (`CliRunner(charset="cp1252")`) face à un U+FFFD.
- **Docs** — `encoding.py` ajouté aux arborescences de `ARCHITECTURE.md`, `README.md`,
  `doc/SPEC.md` (pas de nouvelle section wiki : le module vit dans `core`).

### Comportements obtenus

- Le corps de production produit exactement la sortie réelle de l'hôte, lisible :
  `Output: UNKNOWN - check_by_ssh: ... L'argument «c:/programdata/nagioscmd/scripts/check_win_firewall.ps1» du paramètre -File n'existe pas.`
  — guillemets et accents restitués, pas de `�`.
- Exécution réelle du binaire contre un faux `statusjson.cgi` local servant les octets cp1252
  bruts + un `0x81` : avec `PYTHONIOENCODING=cp1252` (stdout Windows redirigé), exit 0, texte
  correct, le caractère non représentable s'affiche `?` ; `--json` exit 0, JSON valide.
- Avant correctif, le même scénario reproduit à l'identique le symptôme de production :
  `Error: 'utf-8' codec can't decode byte 0xab ... invalid start byte`, exit 1. Le test stdout
  cp1252 échoue lui aussi sans `_tolerate_unencodable_stdout()` — chaque garde-fou est
  couvert indépendamment.
- Une réponse entièrement UTF-8 (cas normal) est décodée à l'identique d'avant.

### Garde-fous

- `pdm run check` vert : ruff, black, mypy strict, import-linter (2 contrats KEPT), vulture,
  refurb, 174 tests, couverture 93.61 %, `encoding.py` et `cli/__init__.py` à 100 %, metrics
  gate palier 1 PASS (`max_file_lines` 597).
- Limite assumée : des octets cp1252 qui forment *par hasard* une séquence UTF-8 valide
  (ex. `Ã©`) sont lus en UTF-8 — indécidable sans encodage déclaré, et rare en pratique.
- Pas de dépendance ajoutée (stdlib `codecs` uniquement) ; le nom du gestionnaire est
  préfixé `nagioscli.` pour ne pas entrer en collision dans le registre global des codecs.
---

[← retour à core/client](index.md) · [voir log](../../log.md)
