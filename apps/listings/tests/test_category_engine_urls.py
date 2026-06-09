"""Smoke HTTP: listados vía `build_category_page` (sin romper verticales)."""

from django.test import TestCase

from apps.categories.models import Category


class CategoryEngineURLTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        specs = [
            ("autos", "Autos"),
            ("motos", "Motos"),
            ("inmuebles", "Inmuebles"),
            ("electronica", "Electrónica"),
            ("hogar", "Hogar"),
        ]
        for order, (slug, name) in enumerate(specs):
            Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "order": order},
            )

    def _assert_200(self, path: str) -> None:
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200, f"{path} -> {r.status_code}")

    def test_browse_and_category_hubs(self) -> None:
        self._assert_200("/anuncios/")
        for slug in ("autos", "motos", "inmuebles", "electronica", "hogar"):
            self._assert_200(f"/{slug}/")

    def test_browse_with_vehicle_filter_param(self) -> None:
        self._assert_200("/autos/?marca=1")

    def test_browse_shows_category_sidebar_filter(self) -> None:
        response = self.client.get("/anuncios/")

        self.assertContains(response, 'aria-label="Filtrar anuncios por categoría"')
        self.assertContains(response, 'data-href="/autos/"')

    def test_browse_category_query_redirects_to_hub(self) -> None:
        response = self.client.get("/anuncios/?category=autos", follow=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/autos/")

    def test_browse_category_query_preserves_search(self) -> None:
        response = self.client.get("/anuncios/?category=autos&q=toyota", follow=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/autos/?q=toyota")

    def test_browse_category_query_with_location_redirects(self) -> None:
        response = self.client.get(
            "/anuncios/?category=autos&location=guayaquil",
            follow=False,
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/guayaquil/autos/")

    def test_location_category_landings(self) -> None:
        self._assert_200("/guayaquil/autos/")
        self._assert_200("/guayaquil/motos/")
        self._assert_200("/samborondon/inmuebles/")
