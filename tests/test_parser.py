import unittest

from src.parser import parse_application


QUIZ_SAMPLE = """
🎯 Заявка на квиз "LED"

Имя: Андрей
Телефон: +79053967558

max: +79053967558

 (Шаг 1 · Тип LED-экрана)
Уличный

Шаг 2 · Тип исполнения (уличный)
Отдельностоящий

Шаг 3 · Шаг пикселя (уличный)
P 4

Ширина (мм) (Шаг 4 · Размер экрана)
4000

Высота (мм) (Шаг 4 · Размер экрана)
3000

Шаг 5 · Монтаж
Монтаж "Под ключ"


Местоположение: Россия, Волгоград
Страница: https://media-live.ru/?yclid=1

Согласия:
Я согласен на обработку персональных данных: Да
""".strip()


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
        self.assertIn("Нужен сайт", lead.raw_text)
        self.assertIn("Telegram", lead.title)

    def test_freeform_phone(self) -> None:
        lead = parse_application("Хочу консультацию, мой номер 89001234567", sender_name="Анна")
        self.assertEqual(lead.name, "Анна")
        self.assertIsNotNone(lead.phone)
        self.assertIn("89001234567", lead.raw_text)

    def test_email_only(self) -> None:
        lead = parse_application("Свяжитесь: test@mail.ru")
        self.assertEqual(lead.email, "test@mail.ru")

    def test_quiz_led(self) -> None:
        lead = parse_application(QUIZ_SAMPLE)
        self.assertEqual(lead.quiz_name, "LED")
        self.assertEqual(lead.name, "Андрей")
        self.assertEqual(lead.phone, "+79053967558")
        self.assertEqual(lead.city, "Россия, Волгоград")
        self.assertTrue(lead.page_url and lead.page_url.startswith("https://media-live.ru"))
        self.assertEqual(lead.messengers.get("max"), "+79053967558")
        self.assertGreaterEqual(len(lead.answers), 5)
        answers = dict(lead.answers)
        self.assertIn("Уличный", answers.values())
        self.assertIn("Отдельностоящий", answers.values())
        self.assertIn("P 4", answers.values())
        self.assertIn("4000", answers.values())
        self.assertIn("3000", answers.values())
        self.assertIn("Квиз LED: Андрей", lead.title)
        self.assertEqual(lead.comments, "")


if __name__ == "__main__":
    unittest.main()
