# Contributing

## How to help

- 🐛 **Bugs** — [Issues](https://github.com/starnowsky/mechanical-counter/issues/new?template=bug_report.md)
- 💡 **Ideas** — [Issues](https://github.com/starnowsky/mechanical-counter/issues/new?template=feature_request.md)
- 📝 **Code** — Pull Request
- 🖨 **Assembly photos** — send them via Issues or Discussions

## Development

```bash
git clone https://github.com/starnowsky/mechanical-counter.git
cd mechanical-counter
pip install -e ".[all,dev]"

make test      # tests
make lint      # flake8 + mypy
make format    # black + isort
```

## PR process

1. Fork the repository
2. Branch: `feature/my-feature` or `fix/my-bug`
3. Commits using [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: add 5-digit support`
   - `fix: correct drum rotation`
   - `docs: update assembly guide`
4. `make ci` — must pass
5. Pull Request → description + screenshots/video

## Code style

- **black** (88 characters)
- **isort** (profile=black)
- **mypy** (no strict errors)
- Docstrings in English
- Type hints required for public functions

## Tests

Every new function needs a test. Coverage must not decrease.
