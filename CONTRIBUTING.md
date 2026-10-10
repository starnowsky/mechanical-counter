# Contributing

## Как помочь

- 🐛 **Баги** — [Issues](https://github.com/USERNAME/mechanical-counter/issues/new?template=bug_report.md)
- 💡 **Идеи** — [Issues](https://github.com/USERNAME/mechanical-counter/issues/new?template=feature_request.md)
- 📝 **Код** — Pull Request
- 🖨 **Фото сборок** — присылайте в Issues или Discussions

## Development

```bash
git clone https://github.com/USERNAME/mechanical-counter.git
cd mechanical-counter
pip install -e ".[all,dev]"

make test      # тесты
make lint      # flake8 + mypy
make format    # black + isort
```

## Процесс PR

1. Форкнуть репозиторий
2. Ветка: `feature/my-feature` или `fix/my-bug`
3. Коммиты по [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: add 5-digit support`
   - `fix: correct drum rotation`
   - `docs: update assembly guide`
4. `make ci` — должно пройти
5. Pull Request → описание + скриншоты/видео

## Стиль кода

- **black** (88 символов)
- **isort** (profile=black)
- **mypy** (без строгих ошибок)
- Docstrings на русском или английском
- Type hints обязательны для публичных функций

## Тесты

Каждая новая функция — тест. Покрытие не должно падать.
