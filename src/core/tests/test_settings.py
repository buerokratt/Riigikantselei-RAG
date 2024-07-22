DEFAULT_PROMPT_VALUE = """Kontekst: Kommionu paneb
Palun vasta järgnevale küsimusele sellega samas keeles.
Kasuta küsimusele vastamiseks AINULT ülaltoodud konteksti.
Kui kontekstis pole vastamiseks piisavalt ja/või
sobivat infot, vasta: "Teadmusbaasis info puudub!".

Küsimus: Kuidas saab moos kommi sisse?
"""

CHANGED_PROMPT_VALUE = """Kontekst: Kommionu paneb
Palun vasta järgnevale küsimusele sellega samas keeles.
Kasuta küsimusele vastamiseks AINULT ülaltoodud konteksti.
Kui kontekstis pole vastamiseks piisavalt ja/või sobivat infot,
vasta: "Ma olen kõrgtehnoloogiline toode, ära küsi lollusi!".

Küsimus: Kuidas saab moos kommi sisse?
"""

BOTH_QUESTION_AND_MISSING_MESSAGE_CHANGED = """
Kontext: Kommionu paneb,
Puuduv sõnum: Ma olen kõrgtehnoloogiline toode, ära küsi lollusi!,
Küsimus: Kuidas saab moos kommi sisse?
"""
