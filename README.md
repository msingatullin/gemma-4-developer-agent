# Gemma 4 Developer Agent & Paper Track (Kaggle 2026)

## 📌 Обзор соревнований (Google DeepMind)

- **Основной трек:** [Gemma 4 Developer Agent](https://www.kaggle.com/competitions/gemma-4-developer-agent) — **$65,000**
  - Дедлайн подачи: **25 ноября 2026**
  - Цель: Автономный программный агент для отладки и починки кода (SWE-agent) на базе квантованной открытой модели `gemma-4-31b-it-qat-w4a16-ct`.
  - Формат: `submission.zip` с `agent.yaml`, системными промптами, subagents, skills и LoRA-адаптерами.

- **Исследовательский трек:** [Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper) — **$35,000**
  - Дедлайн: **12 ноября 2026**
  - Номинации:
    - **Overall Best Paper:** $15,000
    - **Best New Resource (Dataset, Library, Tool):** $10,000
    - **Best New Application:** $10,000
  - Формат: Kaggle Writeup / исследовательская статья по 5 критериям оценки (Innovation, Technical Depth, Generalizability, Empirical Validation, Clarity).

---

## 🏗 Архитектура проекта

```text
/home/mikhail/gemma-4-developer-agent/
├── README.md                          # Документация и план проекта
├── submission/                        # Каталог для сборки submission.zip
│   ├── agent.yaml                     # Корневая конфигурация агента
│   ├── configs/
│   │   └── sampling.yaml              # Параметры семплирования модели
│   ├── prompts/
│   │   ├── system.md                  # Главный системный промпт SWE-агента
│   │   └── bug_localization.md        # Специализированный промпт поиска причины бага
│   ├── sub_agents/                    # Вспомогательные субагенты (agent_tool)
│   │   ├── code_explorer.yaml         # Субагент навигации и поиска по кодовой базе
│   │   └── test_verifier.yaml         # Субагент воспроизведения тестов и верификации
│   └── skills/                        # Скиллы по формату SKILL.md
│       ├── test_runner/               # Скилл изолированного запуска pytest и сбора трейсов
│       │   └── SKILL.md
│       └── ast_indexer/               # Скилл семантического обхода графа кода
│           └── SKILL.md
├── paper/                             # Материалы для Paper Track ($35k)
│   ├── outline.md                     # Структура и тезисы статьи
│   └── writeup.md                     # Текст статьи для Kaggle Writeup
└── tools/                             # Скрипты автоматизации и валидации
    ├── pack_submission.sh             # Сборка валидного submission.zip
    └── validate_submission.py         # Статическая проверка структуры и синтаксиса
```

---

## 🎯 Стратегия победы

1. **В основном треке (SWE Agent):**
   - **Fault Localization First:** Агент не делает слепых правок. Сначала воспроизведение падающего теста через `pytest` или минимальный воспроизводящий скрипт.
   - **Code Graph Navigation:** Использование встроенных инструментов `search_similar_code`, `get_code_neighbors`, `get_code_subgraph` для быстрого сжатия контекста.
   - **Surgical Edits:** Минимальные точечные патчи, не ломающие соседние интерфейсы и форматирование.
   - **Regression Check Loop:** Обязательный прогон полного тестового набора до вызова `submit_patch`.

2. **В исследовательском треке (Paper Track):**
   - Фокус на номинацию **Best New Resource / Application**.
   - Презентация модульного фреймворка верификации и структурированного поиска по кодовому графу на базе открытой Gemma 4.
   - Строгая эмпирическая оценка (A/B тест базовой Gemma 4 vs Gemma 4 с нашими навыками и субагентами на выборке задач `tasks.jsonl`).
