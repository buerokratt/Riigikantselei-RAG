DEFAULT_PROMPT_VALUE = """Kontekst:Kommionupaneb

* Palun vasta järgmisele küsimusele sellega samas keeles.
* Palun kasuta küsimusele vastamiseks ainult ülaltoodud konteksti.
* Kui kontekstis pole küsimusele vastamisek svajalikku infot, vasta:"Teadmusbaasis info puudub!"
* NB! Kui küsimusele pole ülaltoodud info põhjal võimalik üksüheselt vastata, kuid seda puudutav info on kontekstis siiski olemas, siis vasta küsimusele ja too 
välja erinevad võimalikud kitsendused.
* Kasuta lauset "Teadmusbaasis info puudub!" ainult siis,kui kontekstis pole üldse mingit relevantset informatsiooni.
* Ära kasuta vastuses fraase nagu "Kontekstipõhjal...".

Küsimus: Kuidas saab moos kommi sisse?
"""

CHANGED_PROMPT_VALUE = """Kontekst:

Kommionu paneb


* Palun vasta järgmisele küsimusele sellega samas keeles.
* Palun kasuta küsimusele vastamiseks ainult ülaltoodud konteksti.
* Kui kontekstis pole küsimusele vastamiseks vajalikku infot, vasta: "Ma olen kõrgtehnoloogiline toode, ära küsi lollusi!"
* NB! Kui küsimusele pole ülaltoodud info põhjal võimalik üksüheselt vastata, kuid seda puudutav info on kontekstis siiski olemas, siis vasta küsimusele ja too välja erinevad võimalikud kitsendused.
* Kasuta lauset "Ma olen kõrgtehnoloogiline toode, ära küsi lollusi!" ainult siis, kui kontekstis pole üldse mingit relevantset informatsiooni.
* Ära kasuta vastuses fraase nagu "Konteksti põhjal...".Küsimus: Kuidas saab moos kommi sisse?

"""

BOTH_QUESTION_AND_MISSING_MESSAGE_CHANGED = """
Kontext: Kommionu paneb,
Puuduv sõnum: Ma olen kõrgtehnoloogiline toode, ära küsi lollusi!,
Küsimus: Kuidas saab moos kommi sisse?
"""
