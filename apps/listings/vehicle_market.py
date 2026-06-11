from __future__ import annotations

from .market_taxonomy import FALLBACK_BRAND_NAME, FALLBACK_MODEL_NAME

# Curaduría Ecuador/Guayaquil: líderes AEADE, modelos frecuentes en portales
# locales y marcas con oferta real. Mantener acotado evita convertir el select en
# un catálogo infinito.
VEHICLE_MARKET_TAXONOMY: dict[str, list[str]] = {
    "Kia": [
        "Soluto",
        "Rio",
        "Picanto",
        "Sportage",
        "Seltos",
        "Sonet",
        "Sorento",
        "Stonic",
        "Cerato",
    ],
    "Chevrolet": [
        "Aveo",
        "Spark",
        "Sail",
        "D-Max",
        "Tracker",
        "Groove",
        "Captiva",
        "Trailblazer",
        "Colorado",
        "N300",
        "Cruze",
    ],
    "Hyundai": [
        "Grand i10",
        "Accent",
        "Elantra",
        "Tucson",
        "Santa Fe",
        "Sonata",
        "Creta",
        "H-1",
    ],
    "Toyota": [
        "Corolla",
        "Corolla Cross",
        "Yaris",
        "RAV4",
        "Hilux",
        "Fortuner",
        "Land Cruiser",
        "Prado",
        "4Runner",
        "Prius",
        "Highlander",
    ],
    "Nissan": ["Versa", "Sentra", "Kicks", "X-Trail", "Frontier", "Pathfinder", "Qashqai"],
    "Ford": ["F-150", "Ranger", "Escape", "Explorer", "Territory", "EcoSport", "Edge"],
    "Mazda": ["Mazda 2", "Mazda 3", "Mazda 6", "CX-3", "CX-5", "CX-9", "CX-30", "BT-50"],
    "Suzuki": ["Swift", "Grand Vitara", "Vitara", "S-Cross", "Jimny", "Celerio"],
    "Great Wall": ["Poer", "Wingle", "Wingle 5", "Wingle 7", "Haval H5", "Haval H6", "C30", "Haval M4"],
    "Chery": ["Tiggo 2", "Tiggo 4", "Tiggo 7", "Tiggo 8", "Arrizo 5", "Arrizo 6"],
    "JAC": ["T6", "T8", "T9", "S2", "S3", "S4", "Serie HFC 1037"],
    "Volkswagen": ["Gol", "Jetta", "Polo", "Tiguan", "T-Cross", "Amarok", "Virtus"],
    "Renault": ["Duster", "Logan", "Sandero", "Stepway", "Koleos", "Kwid"],
    "Mitsubishi": ["L200", "Montero", "Outlander", "ASX", "Eclipse Cross", "Pajero", "Mirage"],
    "Honda": ["Civic", "CR-V", "HR-V", "Pilot", "Fit", "Accord"],
    "Jeep": ["Compass", "Grand Cherokee", "Wrangler", "Renegade", "Cherokee"],
    "BMW": ["X1", "X3", "X5", "320i", "118i", "520i"],
    "Mercedes Benz": ["GLA", "GLC", "C 180", "C 200", "E 200", "A 200"],
    "Audi": ["A3", "A4", "A6", "Q3", "Q5", "Q7"],
    "Jetour": ["X70", "X70 Plus", "X90", "Dashing"],
    "Changan": ["CS35 Plus", "CS55 Plus", "Hunter", "UNI-T"],
    "Peugeot": ["208", "2008", "3008", "Partner", "Rifter"],
    "Citroen": ["C3", "C4", "Berlingo", "C-Elysee"],
    "Fiat": ["Strada", "Fiorino", "500", "Uno", "Mobi", "Cronos"],
    "Dodge": ["Journey", "Durango", "Charger", "Caliber"],
    "Ram": ["1500", "2500", "700", "Promaster"],
    "Land Rover": ["Range Rover", "Discovery", "Evoque", "Defender"],
    "Porsche": ["Cayenne", "Macan", "Panamera", "911"],
    "DongFeng": ["Rich", "AX4", "AX7", "M5", "S50"],
    "DFSK": ["Glory", "Glory 580", "K01", "K07", "C31", "C32"],
    "BYD": ["Dolphin", "Song Plus", "Yuan Plus", "Tang", "Seagull"],
    "MG": ["ZS", "HS", "MG3", "MG5", "RX5"],
    "Geely": ["Coolray", "Azkarra", "Emgrand", "Okavango"],
    "Isuzu": ["D-Max", "MU-X", "NPR", "NKR"],
    "Subaru": ["Forester", "XV", "Outback", "Impreza", "WRX"],
    "Lexus": ["RX", "NX", "IS", "ES", "GX"],
    "Volvo": ["XC40", "XC60", "XC90", "S60"],
    "Mini": ["Cooper", "Countryman", "Clubman"],
    "Opel": ["Corsa", "Crossland", "Mokka", "Grandland"],
    "Karry": ["Q22", "Q22L", "K60"],
    "Foton": ["Tunland", "View", "Aumark", "Gratour"],
    FALLBACK_BRAND_NAME: [FALLBACK_MODEL_NAME],
}


def vehicle_market_taxonomy_with_fallback() -> dict[str, list[str]]:
    taxonomy: dict[str, list[str]] = {}
    for brand, models in VEHICLE_MARKET_TAXONOMY.items():
        unique_models = list(dict.fromkeys([*models, FALLBACK_MODEL_NAME]))
        taxonomy[brand] = unique_models
    return taxonomy
