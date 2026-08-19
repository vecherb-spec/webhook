import unittest
from unittest.mock import MagicMock

from src.parser import parse_application
from src.planfix import (
    FIELD_CURRENCY,
    FIELD_EXEC_TYPE,
    FIELD_HEIGHT,
    FIELD_INSTALL_PLACE,
    FIELD_LEAD_SOURCE,
    FIELD_MANAGER,
    FIELD_MAX,
    FIELD_MOUNT,
    FIELD_PAGE_URL,
    FIELD_PAYMENT_STATUS,
    FIELD_PIXEL_PITCH,
    FIELD_QUIZ,
    FIELD_SCREEN_SIZE,
    FIELD_SCREEN_TYPE,
    FIELD_WIDTH,
    PlanfixClient,
)
from tests.test_parser import QUIZ_SAMPLE


class PlanfixPayloadTests(unittest.TestCase):
    def _client(self, object_id: int | None = 24) -> PlanfixClient:
        settings = MagicMock()
        settings.planfix_url = "https://medialive.planfix.ru/rest/"
        settings.planfix_token = "test-token"
        settings.planfix_contact_template_id = None
        settings.planfix_task_template_id = None
        settings.planfix_object_id = object_id
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
        self.assertIn("Тип экрана: Уличный", contact["description"])
        self.assertIn("Шаг пикселя: P 4", contact["description"])

        task = client._task_payload(lead, contact_id=42)
        self.assertIn("LED", task["name"])
        self.assertEqual(task["counterparty"]["id"], "42")
        self.assertEqual(task["object"]["id"], 24)
        self.assertIn("P 4", task["description"])

        by_id = {item["field"]["id"]: item["value"] for item in task["customFieldData"]}
        self.assertEqual(by_id[FIELD_CURRENCY], "RUB")
        self.assertEqual(by_id[FIELD_PAYMENT_STATUS], "Не выставлен счет")
        self.assertEqual(by_id[FIELD_LEAD_SOURCE], "Сайт")
        self.assertEqual(by_id[FIELD_SCREEN_TYPE], "Уличный")
        self.assertIn("4000 x 3000 мм", by_id[FIELD_SCREEN_SIZE])
        self.assertIn("P 4", by_id[FIELD_SCREEN_SIZE])
        self.assertIn("Отдельностоящий", by_id[FIELD_SCREEN_SIZE])
        self.assertEqual(by_id[FIELD_INSTALL_PLACE], "Россия, Волгоград")
        self.assertEqual(by_id[FIELD_MANAGER], {"id": "user:1"})
        self.assertEqual(task["name"], "LED / Уличный / 4000 x 3000 / Андрей")

    def test_no_custom_fields_without_object(self) -> None:
        client = self._client(object_id=None)
        lead = parse_application(QUIZ_SAMPLE)
        task = client._task_payload(lead, contact_id=1)
        self.assertNotIn("customFieldData", task)
        self.assertNotIn("object", task)


if __name__ == "__main__":
    unittest.main()
