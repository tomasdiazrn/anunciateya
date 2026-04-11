import json

from django.test import Client, TestCase

from .models import Event


class TrackEventViewTests(TestCase):
    def test_requires_event_type(self):
        c = Client()
        r = c.post(
            "/events/track/",
            data=json.dumps({"event_detail": "x"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Event.objects.count(), 0)

    def test_creates_event(self):
        c = Client()
        r = c.post(
            "/events/track/",
            data=json.dumps(
                {
                    "event_type": "category_click",
                    "event_detail": "autos",
                    "path": "/autos/",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Event.objects.count(), 1)
        ev = Event.objects.get()
        self.assertEqual(ev.event_type, "category_click")
        self.assertEqual(ev.event_detail, "autos")
        self.assertEqual(ev.path, "/autos/")
        self.assertIsNone(ev.user)
