import unittest
from unittest.mock import MagicMock

from src.parser import parse_application
from src.planfix import PlanfixClient
from tests.test_parser import QUIZ_SAMPLE


class PlanfixPayloadTests(unittest.TestCase):
    def _client(self) -> PlanfixClient:
        settings = MagicMock()
        settings.planfix_url = "https://medialive.planfix.ru/rest/"
        settings.planfix_token = "test-token"
        settings.planfix_contact_template_id = None
        settings.planfix_task_template_id = None
        settings.planfix_object_id = 24
        settings.planfix_assignee_user_id = None
        return PlanfixClient(settings)

    def test_base_url_normalized(self) -> None:
        settings = MagicMock()
        settings.planfix_url = "https://medialive.planfix.ru"
        settings.planfix_token = "t"
        settings.planfix_contact_template_id = None
        settings.planfix_task_template_id = None
        settings.planfix_object_id = None
        settings.planfix_assignee_user_id = None
        client = PlanfixClient(settings)
        self.assertEqual(client.base, "https://medialive.planfix.ru/rest")

    def test_contact_and_task_payload(self) -> None:
        client = self._client()
        lead = parse_application(QUIZ_SAMPLE)
        contact = client._contact_payload(lead)
        self.assertEqual(contact["name"], "Андрей")
        self.assertEqual(contact["phones"][0]["number"], "+79053967558")
        self.assertEqual(contact["phones"][0]["type"], 1)
        self.assertIn("Квиз: LED", contact["description"])

        task = client._task_payload(lead, contact_id=42)
        self.assertIn("LED", task["name"])
        self.assertEqual(task["counterparty"]["id"], "42")
        self.assertEqual(task["object"]["id"], 24)
        self.assertIn("P 4", task["description"])


if __name__ == "__main__":
    unittest.main()
