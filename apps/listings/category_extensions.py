"""
Extensión de anuncios por categoría (OneToOne). Slugs = Category.slug en BD.

EXTENSION_SPECS documenta el mapeo slug → modelo + formulario (nombres de clase).
La lógica de vistas usa publish_flow_kind().

Listados / filtros / búsqueda / SEO por categoría: ver `category_engine.py` (`CategoryContractSpec`).
"""

# Slugs raíz con formulario extendido (deben existir como Category.slug).
VEHICLE_SLUG = "autos"
PROPERTY_SLUG = "inmuebles"
MOTORCYCLE_SLUG = "motos"
ELECTRONICS_SLUG = "electronica"
HOMEGOODS_SLUG = "hogar"

# Slugs que tienen fila en EXTENSION_SPECS (incl. autos / inmuebles).
EXTENDED_CATEGORY_SLUGS = frozenset(
    {
        VEHICLE_SLUG,
        PROPERTY_SLUG,
        MOTORCYCLE_SLUG,
        ELECTRONICS_SLUG,
        HOMEGOODS_SLUG,
    }
)

EXTENSION_SPECS = {
    VEHICLE_SLUG: {
        "label": "Autos",
        "extension_model": "VehicleListing",
        "form_class": "VehicleListingForm",
    },
    PROPERTY_SLUG: {
        "label": "Inmuebles",
        "extension_model": "PropertyListing",
        "form_class": "PropertyListingForm",
    },
    MOTORCYCLE_SLUG: {
        "label": "Motos",
        "extension_model": "MotorcycleListing",
        "form_class": "MotorcycleListingForm",
    },
    ELECTRONICS_SLUG: {
        "label": "Electrónica",
        "extension_model": "ElectronicsListing",
        "form_class": "ElectronicsListingForm",
    },
    HOMEGOODS_SLUG: {
        "label": "Hogar",
        "extension_model": "HomeGoodsListing",
        "form_class": "HomeGoodsListingForm",
    },
}

EXTENSION_PUBLISH_META = {
    VEHICLE_SLUG: (
        "Completa marca, modelo, año y datos del vehículo. "
        "Fotos claras generan más contactos."
    ),
    PROPERTY_SLUG: (
        "Indica tipo de propiedad, habitaciones, baños y metros cuadrados."
    ),
    MOTORCYCLE_SLUG: (
        "Marca, modelo, año y condición de la moto. La cilindrada es opcional."
    ),
    ELECTRONICS_SLUG: (
        "Marca, modelo y estado del equipo. Indicá si aplica garantía."
    ),
    HOMEGOODS_SLUG: (
        "Condición del artículo; material y medidas ayudan a evitar dudas."
    ),
}


def publish_flow_kind(slug: str) -> str:
    if slug == VEHICLE_SLUG:
        return "vehicle"
    if slug == PROPERTY_SLUG:
        return "property"
    if slug == MOTORCYCLE_SLUG:
        return "motorcycle"
    if slug == ELECTRONICS_SLUG:
        return "electronics"
    if slug == HOMEGOODS_SLUG:
        return "homegoods"
    return "simple"
