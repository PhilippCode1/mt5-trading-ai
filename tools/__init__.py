"""Werkzeuge des Repos als Paket.

Diese Datei existiert, damit ein Werkzeug ein anderes einbinden kann, ohne dass eine
Rechnung zweimal im Baum steht. ``tools/aufloesung.py`` holt sich K aus
``tools/kostentor.py`` statt die Kostenformel nachzubauen -- der Nachbau hatte die
Waehrungsumrechnung der Kommission verloren. Ohne Paketdatei sieht ``mypy`` dieselbe
Datei unter zwei Modulnamen und bricht ab.
"""
