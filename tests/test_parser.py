import unittest

from src.parser import parse_application


class ParserTests(unittest.TestCase):
    def test_labeled_fields(self) -> None:
        text = """
Имя: Иван Петров
Телефон: +7 (900) 111-22-33
Email: ivan@example.com
Комментарий: Нужен сайт
""".strip()
        lead = parse_application(text)
        self.assertEqual(lead.name, "Иван Петров")
        self.assertTrue(lead.phone.startswith("+7"))
        self.assertEqual(lead.email, "ivan@example.com")
        self.assertIn("Нужен сайт", lead.comments)
        self.assertIn("Telegram", lead.title)

    def test_freeform_phone(self) -> None:
        lead = parse_application("Хочу консультацию, мой номер 89001234567", sender_name="Анна")
        self.assertEqual(lead.name, "Анна")
        self.assertIsNotNone(lead.phone)
        self.assertIn("89001234567", lead.raw_text)

    def test_email_only(self) -> None:
        lead = parse_application("Свяжитесь: test@mail.ru")
        self.assertEqual(lead.email, "test@mail.ru")


if __name__ == "__main__":
    unittest.main()
