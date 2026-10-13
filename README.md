# Agent Automations — универсальный скилл

Этот репозиторий содержит переиспользуемый скилл `effective-agent-automations` для проектирования, создания, запуска и проверки автономных ИИ-агентов.

- **Codex:** `.agents/skills/effective-agent-automations/SKILL.md`
- **Claude Code:** `.claude/skills/effective-agent-automations/SKILL.md`

Скилл основан на [Building effective agent automations](https://claude.dev/blog/building-effective-agent-automations/) (Anthropic, 08.10.2026), но принципы подходят и для других платформ. Команды для Claude Managed Agents выделены отдельно: они требуют рабочей Claude API-среды, авторизации и явной настройки.

## Как использовать

Откройте репозиторий в Codex или Claude Code и попросите: «Примени скилл effective-agent-automations. Спроектируй агента, который проверяет GitHub и отправляет ежедневную сводку. Подготовь конфигурацию, сначала тестирование без отправки и без деплоя».

**Важно:** само добавление скилла не создаёт фоновые задания, не подключает API, не запускает деплой и не тратит токены. Всё это требует отдельной настройки.

## Надёжность и безопасность

- Продолжение от последней подтверждённой точки, а не «последние 24 часа».
- Явное обозначение недоступных источников.
- Перепроверка актуальности перед сообщением.
- Обновление памяти только после подтверждения доставки.
- Настройки пользователя доступны агенту только для чтения.
- Минимальные права доступа, ограниченный бюджет, контроль успешности запусков.
- По умолчанию **не запускать GitHub Actions**; использовать API/локальные команды/SSH только при необходимости и с разрешёнными правами.

## Источники

- [Исходная статья Anthropic](https://claude.dev/blog/building-effective-agent-automations/)
- [Официальный пример Daily Brief](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/daily-brief)
- [Спецификация Agent Skills](https://agentskills.io/specification)
