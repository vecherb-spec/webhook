import unittest
from unittest.mock import MagicMock

from src.espo import EspoClient
from src.parser import parse_application
from tests.test_parser import QUIZ_SAMPLE


class EspoPayloadTests(unittest.TestCase):
    def test_payload_from_quiz(self) -> None:
        settings = MagicMock()
        settings.espo_url = "https://crm.example.com"
        settings.espo_api_key = "test-key"
        settings.espo_entity = "Lead"
        settings.espo_lead_status = "New"
        settings.espo_source = "Web Site"
        settings.espo_assigned_user_id = None
        settings.espo_field_map = {
            "quiz_name": "cQuizName",
            "тип led": "cLedType",
            "ширина": "cWidth",
        }

        client = EspoClient(settings)
        lead = parse_application(QUIZ_SAMPLE)
        payload = client._payload_from_lead(lead)

        self.assertEqual(payload["firstName"], "Андрей")
        self.assertEqual(payload["phoneNumber"], "+79053967558")
        self.assertEqual(payload["addressCity"], "Россия, Волгоград")
        self.assertEqual(payload["status"], "New")
        self.assertEqual(payload["source"], "Web Site")
        self.assertEqual(payload["cQuizName"], "LED")
        self.assertEqual(payload["cLedType"], "Уличный")
        self.assertEqual(payload["cWidth"], "4000")
        self.assertIn("Квиз: LED", payload["description"])
        self.assertIn("P 4", payload["description"])

    def test_base_url_normalized(self) -> None:
        settings = MagicMock()
        settings.espo_url = "https://crm.example.com/"
        settings.espo_api_key = "k"
        settings.espo_entity = "Lead"
        client = EspoClient(settings)
        self.assertEqual(client.base, "https://crm.example.com/api/v1")


if __name__ == "__main__":
    unittest.main()
