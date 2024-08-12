DEFAULT_PROMPT_VALUE = """
Kontekst:

Kommionu paneb


* Palun vasta järgmisele küsimusele sellega samas keeles.
* Palun anna küsimusele 2 vastust järgnevate reeglite alusel:

1. GPT teadmusele tuginev vastus:

* Kasuta vastamiseks üksnes oma teadmust, ära kasuta ülaltoodud konteksti.

2. Kaasatud andmestikele tuginev vastus:

* Palun kasuta küsimusele vastamiseks ainult ülaltoodud konteksti.
* Kui kontekstis pole küsimusele vastamiseks vajalikku infot, vasta: Teadmusbaasis info puudub!. Ära kasuta seda fraasi osalise vastuse korral.
* NB! Kui küsimusele pole ülaltoodud info põhjal võimalik üksüheselt vastata, kuid seda puudutav info on kontekstis siiski olemas, siis vasta küsimusele ja too välja erinevad võimalikud kitsendused.
* Palun tagastada relevantsuse järjekorras komaga eraldatuna nimekiri kontekstis olevatest allikatest, mida vastamisel kasutasid, nt: "Allikad: 10, 5, 7". Kui mõnda konteksti kaasatud allikat ei kasutatud, siis ära seda nimekirja lisa.\n* Palun lisa allikad ainult kõige lõppu. Ära lisa allikaid lõikude järele.
* Palun eralda allikad ülejäänud vastusest kahekordse reavahetusega, nt: "<vastused>\n\nAllikad: [10, 5, 9]".\n\nKüsimus: Kuidas saab moos kommi sisse?
"""

CHANGED_PROMPT_VALUE = """Kontekst:

Kommionu paneb


* Palun vasta järgmisele küsimusele sellega samas keeles.* Palun anna küsimusele 2 vastust järgnevate reeglite alusel:
1. GPT teadmusele tuginev vastus:

* Kasuta vastamiseks üksnes oma teadmust, ära kasuta ülaltoodud konteksti.

2. Kaasatud andmestikele tuginev vastus:

* Palun kasuta küsimusele vastamiseks ainult ülaltoodud konteksti.
* Kui kontekstis pole küsimusele vastamiseks vajalikku infot, vasta: Ma olen kõrgtehnoloogiline toode, ära küsi lollusi!. Ära kasuta seda fraasi osalise vastuse korral.
* NB! Kui küsimusele pole ülaltoodud info põhjal võimalik üksüheselt vastata, kuid seda puudutav info on kontekstis siiski olemas, siis vasta küsimusele ja too välja erinevad võimalikud kitsendused.
* Palun tagastada relevantsuse järjekorras komaga eraldatuna nimekiri kontekstis olevatest allikatest, mida vastamisel kasutasid, nt: "Allikad: 10, 5, 7". Kui mõnda konteksti kaasatud allikat ei kasutatud, siis ära seda nimekirja lisa.
* Palun lisa allikad ainult kõige lõppu. Ära lisa allikaid lõikude järele.
* Palun eralda allikad ülejäänud vastusest kahekordse reavahetusega, nt: "<vastused>\n\nAllikad: [10, 5, 9]".

Küsimus: Kuidas saab moos kommi sisse?

"""

BOTH_QUESTION_AND_MISSING_MESSAGE_CHANGED = """
Kontext: Kommionu paneb,
Puuduv sõnum: Ma olen kõrgtehnoloogiline toode, ära küsi lollusi!,
Küsimus: Kuidas saab moos kommi sisse?
"""
