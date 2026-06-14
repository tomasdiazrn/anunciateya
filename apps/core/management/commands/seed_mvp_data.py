"""
Genera datos de demostración en español para probar confianza y anuncios marcados.

Uso:
  python manage.py seed_mvp_data
  python manage.py seed_mvp_data --clear   # elimina usuarios @mvp-seed.local y datos ligados
"""

from __future__ import annotations

import random
from datetime import timedelta
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.categories.display import apply_root_category_display
from apps.categories.models import Category
from apps.listings.models import (
    ElectronicsItemType,
    ElectronicsListing,
    HomeGoodsListing,
    HomeItemType,
    ItemCondition,
    Listing,
    MarketBrand,
    MarketModel,
    MarketZone,
    MotorcycleListing,
    PropertyListing,
    VehicleListing,
)
from apps.trust.models import ListingReport
from apps.trust.services import bulk_seller_verification, sync_listing_flag
from apps.users.models import User, UserVerification

# Dominio reservado para poder borrar todo con --clear sin tocar cuentas reales.
SEED_EMAIL_DOMAIN = "mvp-seed.local"
ZONE_SLUGS = [
    "urdesa",
    "puerto-santa-ana",
    "samborondon",
    "garzota",
    "entrada-de-la-8",
    "kennedy",
    "via-a-la-costa",
    "duran",
]
LOCATION_REFERENCES = [
    "",
    "punto de encuentro acordado",
    "cerca de centro comercial",
    "retiro coordinado con el vendedor",
]

# (título base, descripción, marca, modelo, año) — coherentes con VehicleListing
VEHICLES = [
    ("Toyota Corolla 2018, automático", "Full equipo, revisión al día. Se vende por viaje.", "Toyota", "Corolla", 2018),
    ("Chevrolet Spark 2016", "Económico, ideal ciudad. Segundo dueño.", "Chevrolet", "Spark", 2016),
    ("Hyundai Tucson 2019", "SUV familiar, mantenimiento en agencia.", "Hyundai", "Tucson", 2019),
    ("Mitsubishi L200 2017", "4x4, trabajo y ciudad.", "Mitsubishi", "L200", 2017),
    ("Nissan Versa 2020", "Bajo kilometraje, único dueño.", "Nissan", "Versa", 2020),
]

INMUEBLES = [
    ("Suite amoblada — alquiler Puerto Santa Ana", "Vista al río, seguridad 24h. Contrato mínimo 6 meses."),
    ("Departamento 3 dormitorios — Urdesa", "Iluminación natural, parqueo cubierto."),
    ("Terreno 500 m² — vía Samborondón", "Plano, servicios cerca. Escritura al día."),
    ("Oficina pequeña — centro norte", "Ideal emprendimiento, baño y recepción."),
    ("Bodega 120 m² — norte de Guayaquil", "Acceso camión, techo zinc nuevo."),
]

MOTOS = [
    ("Yamaha NMAX 155", "Scooter urbano, revisiones al día."),
    ("Honda CB500F", "Naked, ideal ciudad y ruta corta."),
    ("Suzuki GSX-R 150", "Deportiva liviana, segundo dueño."),
    ("KTM Duke 200", "Uso mixto, escape homologado."),
    ("Italika FT150", "Trabajo y ciudad, económica."),
]

ELECTRONICA = [
    ("Samsung Galaxy A54 128 GB", "Pantalla impecable, funda y cargador."),
    ("Laptop Dell Inspiron 15", "SSD 256 GB, Windows actualizado."),
    ("iPad 9ª gen Wi‑Fi", "Ideal estudio, batería sana."),
    ("Smart TV 50\" 4K", "Caja y control, sin rayones en panel."),
    ("Auriculares Sony WH-CH720N", "Cancelación de ruido, poco uso."),
]

HOGAR = [
    ("Sofá 3 cuerpos gris", "Tela fácil de limpiar, desarmable para mudanza."),
    ("Mesa comedor 6 puestos", "Madera maciza, patas reforzadas."),
    ("Cama queen con colchón", "Colchón ortopédico, menos de 2 años de uso."),
    ("Estantería modular blanca", "4 módulos, fijación a pared incluida."),
    ("Juego de ollas antiadherentes", "7 piezas, aptas inducción."),
]

class Command(BaseCommand):
    help = "Crea usuarios, categorías, anuncios y reportes de prueba (español, confianza variada)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help=f'Elimina usuarios con correo @{SEED_EMAIL_DOMAIN} y datos asociados.',
        )
        parser.add_argument(
            "--listings",
            type=int,
            default=75,
            help="Número aproximado de anuncios (50–100 recomendado).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Vuelve a insertar aunque ya existan anuncios semilla (sin --clear duplica datos).",
        )
    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_seed_data()
            self.stdout.write(self.style.WARNING("Datos semilla eliminados."))
            return

        n_listings = max(50, min(100, options["listings"]))
        random.seed(42)

        seed_domain = f"@{SEED_EMAIL_DOMAIN}"
        if (
            Listing.objects.filter(seller__email__endswith=seed_domain).exists()
            and not options["force"]
        ):
            self.stderr.write(
                self.style.ERROR(
                    "Ya existen anuncios semilla. Ejecute con --clear o añada --force (duplicará datos)."
                )
            )
            return

        with transaction.atomic():
            call_command("sync_market_taxonomy")
            categories = self._seed_categories()
            users = self._seed_users()
            self._apply_user_profiles(users)
            listings = self._seed_listings(users, categories, n_listings)
            self._seed_flagged_listings(users, listings)

        # Refresca banderas por si el conteo de reportes lo requiere
        for lid in Listing.objects.filter(seller__email__endswith=f"@{SEED_EMAIL_DOMAIN}").values_list(
            "id", flat=True
        ):
            sync_listing_flag(lid)

        user_ids = list(
            User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}").values_list("pk", flat=True)
        )
        bulk_seller_verification(user_ids)

        self._print_summary(users, listings, categories)

    def _clear_seed_data(self):
        """Borra en orden seguro respetando PROTECT y FKs."""
        qs = User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}")
        user_ids = list(qs.values_list("pk", flat=True))
        if not user_ids:
            self.stdout.write("No hay usuarios semilla que borrar.")
            return

        ListingReport.objects.filter(reporter_id__in=user_ids).delete()
        ListingReport.objects.filter(listing__seller_id__in=user_ids).delete()
        Listing.objects.filter(seller_id__in=user_ids).delete()
        UserVerification.objects.filter(user_id__in=user_ids).delete()
        qs.delete()

    def _seed_categories(self) -> dict[str, Category]:
        """Categorías raíz en español (alineadas con iconos en migración 0003)."""
        specs = [
            ("Autos", "autos", "Autos, motos y camionetas en Guayaquil y Samborondón."),
            ("Inmuebles", "inmuebles", "Alquiler y venta de propiedades."),
            ("Electrónica", "electronica", "Celulares, laptops y gadgets. Ofertas locales."),
            ("Motos", "motos", "Motos urbanas y de trabajo. Publicaciones claras."),
            ("Hogar", "hogar", "Muebles y artículos para tu casa."),
        ]
        out = {}
        for name, slug, desc in specs:
            cat, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": desc},
            )
            changed = False
            if cat.name != name:
                cat.name = name
                changed = True
            if cat.description != desc:
                cat.description = desc
                changed = True
            if changed:
                cat.save(update_fields=["name", "description"])
            apply_root_category_display(cat)
            out[slug] = cat
        return out

    def _seed_users(self) -> list[User]:
        """18 usuarios vendedor/comprador con nombres en español."""
        names = [
            "María José Villamar",
            "Carlos Mendoza",
            "Ana Lucía Correa",
            "Roberto Sánchez",
            "Daniela Pincay",
            "Luis Fernando Aguilar",
            "Patricia Ruiz",
            "Miguel Ángel Vera",
            "Sofía Torres",
            "Javier Macías",
            "Carmen Noboa",
            "Diego Ordóñez",
            "Valentina Castro",
            "Andrés Cevallos",
            "Lucía Espinoza",
            "Fernando Baquerizo",
            "Gabriela Reyes",
            "Esteban Salinas",
        ]
        users = []
        for i, full_name in enumerate(names):
            email = f"vendedor{i+1:02d}@{SEED_EMAIL_DOMAIN}"
            parts = (full_name or "").strip().split()
            first_name = parts[0] if parts else ""
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"first_name": first_name, "last_name": last_name},
            )
            if created or user.has_usable_password():
                user.set_unusable_password()
                user.save(update_fields=["password"])
            changed = False
            if user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if user.last_name != last_name:
                user.last_name = last_name
                changed = True
            if changed:
                user.save(update_fields=["first_name", "last_name"])
            users.append(user)
        return users

    def _apply_user_profiles(self, users: list[User]) -> None:
        """Perfiles semilla con una mezcla de teléfonos verificados y no verificados."""
        now = timezone.now()

        verified_phones = [
            "+593 98 100 0001",
            "+593 98 100 0002",
            "+593 98 100 0003",
            "+593 98 100 0004",
            "+593 98 100 0007",
            "+593 98 100 0008",
        ]

        UserVerification.objects.filter(user__in=users).delete()

        for idx, user in enumerate(users):
            want_verified = idx <= 8 and idx not in (4, 5, 6)
            if want_verified:
                phone = verified_phones[idx % len(verified_phones)]
                UserVerification.objects.create(
                    user=user,
                    phone_number=phone,
                    phone_verified=True,
                    verification_date=now - timedelta(days=1),
                )

    def _seed_listings(
        self,
        users: list[User],
        categories: dict[str, Category],
        n_listings: int,
    ) -> list[Listing]:
        """Anuncios repartidos entre vendedores; títulos y ubicaciones realistas."""
        cat_cycle = [
            categories["autos"],
            categories["inmuebles"],
            categories["electronica"],
            categories["motos"],
            categories["hogar"],
        ]
        templates = [
            VEHICLES,
            INMUEBLES,
            ELECTRONICA,
            MOTOS,
            HOGAR,
        ]
        listings: list[Listing] = []
        # Solo los primeros 15 usuarios publican más anuncios; el resto completa la muestra.
        seller_pool = users[:15]
        seq = 0
        n_cats = len(cat_cycle)
        while len(listings) < n_listings:
            seller = random.choice(seller_pool)
            cat_idx = seq % n_cats
            cat = cat_cycle[cat_idx]
            row = random.choice(templates[cat_idx])
            if cat.slug == "autos":
                title, desc_base, seed_v_brand, seed_v_model, seed_v_year = row
            else:
                title, desc_base = row
                seed_v_brand = seed_v_model = ""
                seed_v_year = 0
            seq += 1
            title = f"{title} #{seq}"
            desc = f"{desc_base}\n\nUbicación para retiro o visita acordada. Precio negociable leve."
            price = random.randint(80, 45000)
            if cat.slug == "autos":
                price = random.randint(5000, 28000)
            elif cat.slug == "inmuebles":
                price = random.randint(250, 2500) if random.random() < 0.4 else random.randint(35000, 180000)
            elif cat.slug == "motos":
                price = random.randint(1200, 14000)
            elif cat.slug == "electronica":
                price = random.randint(80, 2200)
            elif cat.slug == "hogar":
                price = random.randint(45, 2800)

            zone = MarketZone.objects.filter(
                slug=random.choice(ZONE_SLUGS),
                is_active=True,
            ).first()
            if zone is None:
                zone = MarketZone.objects.filter(is_active=True).order_by("sort_order").first()

            listing = Listing.objects.create(
                title=title[:200],
                description=desc,
                price_amount=price,
                currency="USD",
                zone=zone,
                location_reference=random.choice(LOCATION_REFERENCES),
                seller=seller,
                category=cat,
                status=Listing.Status.PUBLISHED,
                is_flagged=False,
            )
            if cat.slug == "autos":
                brand_name = seed_v_brand
                model_name = seed_v_model
                brand_obj, model_obj = self._resolve_market_model(
                    "autos",
                    "",
                    brand_name,
                    model_name,
                )
                VehicleListing.objects.create(
                    listing=listing,
                    brand_fk=brand_obj,
                    model_fk=model_obj,
                    year=int(seed_v_year),
                    mileage=random.choice([None, 0, 35000, 68000, 85000, 120000]),
                    doors=random.choice([3, 4, 5]),
                    transmission=random.choice(
                        [
                            VehicleListing.Transmission.MANUAL,
                            VehicleListing.Transmission.AUTOMATICO,
                            VehicleListing.Transmission.CVT,
                        ]
                    ),
                    fuel_type=random.choice(
                        [
                            "",
                            VehicleListing.FuelType.GASOLINA,
                            VehicleListing.FuelType.DIESEL,
                            VehicleListing.FuelType.HIBRIDO,
                            VehicleListing.FuelType.ELECTRICO,
                        ]
                    ),
                )
            elif cat.slug == "inmuebles":
                PropertyListing.objects.create(
                    listing=listing,
                    property_type=random.choice(
                        [
                            PropertyListing.PropertyType.CASA,
                            PropertyListing.PropertyType.DEPARTAMENTO,
                            PropertyListing.PropertyType.SUITE,
                            PropertyListing.PropertyType.TERRENO_LOTE,
                            PropertyListing.PropertyType.OFICINA_COMERCIAL,
                            PropertyListing.PropertyType.LOCAL_COMERCIAL,
                            PropertyListing.PropertyType.BODEGA_GALPON,
                        ]
                    ),
                    operation_type=random.choice(
                        [
                            None,
                            PropertyListing.OperationType.VENTA,
                            PropertyListing.OperationType.ALQUILER,
                            PropertyListing.OperationType.ALQUILER_TEMPORAL,
                        ]
                    ),
                    rooms=random.randint(1, 5),
                    bathrooms=random.randint(1, 4),
                    area_m2=random.randint(40, 450),
                    parking_spaces=random.choice([None, 0, 1, 2]),
                    furnished=random.choice([True, False]),
                    property_condition=random.choice(
                        [
                            None,
                            PropertyListing.PropertyConditionChoice.NUEVO,
                            PropertyListing.PropertyConditionChoice.USADO,
                        ]
                    ),
                )
            elif cat.slug == "motos":
                model_obj = self._pick_random_market_model("motos")
                MotorcycleListing.objects.create(
                    listing=listing,
                    brand_fk=model_obj.brand,
                    model_fk=model_obj,
                    year=random.randint(2016, 2023),
                    mileage=random.choice([None, 0, 3500, 12000, 28000]),
                    engine_cc=random.choice([None, 125, 155, 200, 390, 650]),
                    transmission=random.choice(
                        [
                            MotorcycleListing.Transmission.MANUAL,
                            MotorcycleListing.Transmission.AUTOMATICO,
                            MotorcycleListing.Transmission.OTRO,
                        ]
                    ),
                    fuel_type=random.choice(
                        [
                            MotorcycleListing.FuelType.GASOLINA,
                            MotorcycleListing.FuelType.NAFTA,
                            MotorcycleListing.FuelType.ELECTRICA,
                            MotorcycleListing.FuelType.OTRO,
                        ]
                    ),
                    condition=random.choice(
                        [ItemCondition.NUEVO, ItemCondition.USADO]
                    ),
                )
            elif cat.slug == "electronica":
                model_obj = self._pick_random_market_model("electronica", item_type=None)
                ElectronicsListing.objects.create(
                    listing=listing,
                    item_type=model_obj.item_type or ElectronicsItemType.OTROS,
                    brand_fk=model_obj.brand,
                    model_fk=model_obj,
                    condition=random.choice(
                        [ItemCondition.NUEVO, ItemCondition.USADO]
                    ),
                    warranty=random.choice([True, False]),
                )
            elif cat.slug == "hogar":
                item_type = random.choice(
                    [
                        HomeItemType.FURNITURE,
                        HomeItemType.APPLIANCES,
                        HomeItemType.DECOR,
                    ]
                )
                model_obj = self._pick_random_market_model(
                    "hogar",
                    item_type=str(item_type),
                )
                HomeGoodsListing.objects.create(
                    listing=listing,
                    item_type=item_type,
                    brand_fk=model_obj.brand,
                    model_fk=model_obj,
                    condition=random.choice(
                        [
                            ItemCondition.NUEVO,
                            ItemCondition.USADO,
                            ItemCondition.REFURBISHED,
                        ]
                    ),
                    material=random.choice(["", "melamina", "madera", "metal", "tela"]),
                    dimensions=random.choice(["", "200×100 cm", "180×90 cm", "modular"]),
                )
            listings.append(listing)
        return listings

    def _resolve_market_model(
        self,
        category_slug: str,
        item_type: str,
        brand_name: str,
        model_name: str,
    ) -> tuple[MarketBrand, MarketModel]:
        brand = MarketBrand.objects.filter(
            name__iexact=brand_name.strip(),
            is_active=True,
        ).first()
        if brand is None:
            raise CommandError(
                f"Marca «{brand_name}» no está en taxonomía. "
                "Ejecute sync_market_taxonomy antes del seed."
            )
        model = MarketModel.objects.filter(
            brand=brand,
            category_slug=category_slug,
            item_type=item_type or "",
            name__iexact=model_name.strip(),
            is_active=True,
        ).first()
        if model is None:
            raise CommandError(
                f"Modelo «{model_name}» ({brand_name}) no está en taxonomía "
                f"para {category_slug!r}."
            )
        return brand, model

    def _pick_random_market_model(
        self,
        category_slug: str,
        *,
        item_type: str | None = "",
    ) -> MarketModel:
        qs = MarketModel.objects.filter(
            category_slug=category_slug,
            is_active=True,
            brand__is_active=True,
        )
        if item_type is not None:
            qs = qs.filter(item_type=item_type)
        model = qs.select_related("brand").order_by("?").first()
        if model is None:
            suffix = f" ({item_type})" if item_type else ""
            raise CommandError(
                f"No hay modelos en taxonomía para {category_slug!r}{suffix}."
            )
        return model

    def _seed_flagged_listings(self, users: list[User], listings: list[Listing]) -> None:
        """Varios anuncios con ≥3 reportes distintos → is_flagged vía sync_listing_flag."""
        candidates = [L for L in listings if L.seller_id != users[0].pk][:8]
        random.shuffle(candidates)
        flagged_targets = candidates[:6]

        for listing in flagged_targets:
            eligible = [u for u in users[:14] if u.pk != listing.seller_id]
            random.shuffle(eligible)
            reporters = eligible[:3]
            if len(reporters) < 3:
                continue
            for reason, reporter in zip(
                [
                    ListingReport.Reason.SCAM,
                    ListingReport.Reason.SPAM,
                    ListingReport.Reason.INCORRECT,
                ],
                reporters,
            ):
                ListingReport.objects.get_or_create(
                    reporter=reporter,
                    listing=listing,
                    defaults={"reason": reason},
                )
            sync_listing_flag(listing.pk)

    def _print_summary(
        self,
        users: list[User],
        listings: list[Listing],
        categories: dict,
    ) -> None:
        from apps.trust.services import seller_verification_bundle

        n_users = len(users)
        n_listings = len(listings)
        n_flagged = Listing.objects.filter(
            seller__email__endswith=f"@{SEED_EMAIL_DOMAIN}",
            is_flagged=True,
        ).count()
        n_reports = ListingReport.objects.filter(
            listing__seller__email__endswith=f"@{SEED_EMAIL_DOMAIN}"
        ).count()

        self.stdout.write(self.style.SUCCESS("\n=== Resumen datos MVP (semilla) ==="))
        self.stdout.write(f"  Usuarios:        {n_users}")
        self.stdout.write(f"  Categorías:      {len(categories)}")
        self.stdout.write(f"  Anuncios:        {n_listings}")
        self.stdout.write(f"  Reportes:        {n_reports}")
        self.stdout.write(f"  Anuncios marcados: {n_flagged}")
        self.stdout.write("  Acceso:          OTP por correo (sin contraseña)")
        self.stdout.write(f"  Correo patrón:   vendedorXX@{SEED_EMAIL_DOMAIN}")

        self.stdout.write("\n  Muestra verificación por vendedor:")
        for u in users[:6]:
            b = seller_verification_bundle(u)
            self.stdout.write(
                f"    - {u.get_full_name() or u.email}: "
                f"teléfono verificado={'sí' if b['verified'] else 'no'}"
            )
        self.stdout.write(self.style.SUCCESS("=== Fin ===\n"))
