# Market Intelligence Engine (MIE)

Личный анализатор рынка: свечные паттерны, технические индикаторы, структура рынка (BOS/CHoCH, FVG, Order Blocks),
мультитаймфреймовый фильтр, календарь с blackout вокруг новостей, COT, калиброванная вероятность (XGBoost).
Всё работает на бесплатных платформах и разворачивается **только через браузер**.

> Информационный инструмент, не инвестиционная рекомендация. Вероятности и E[R] оценочные и не учитывают спред,
> комиссии и проскальзывание. Пока ML-модель не обучена и не прошла проверку, вероятность помечена как эвристика
> (`*`) и почти не даёт преимущества над монетой.

## Архитектура

```
Браузер ──► Vercel (Next.js) ──► Supabase (Postgres, Realtime, Storage)
   │                                  ▲
   │ REST                             │ запись сигналов, чтение моделей
   └──────────► Hugging Face Space (FastAPI + APScheduler) ◄── cron-job.org (пульс /tick каждые 5 мин)
                    │                  ◄── GitHub Actions (обучение, разметка исходов)
                    └──► Binance* / Kraken / Coinbase, Twelve Data, Finnhub, CFTC
```

Крипта в реальном времени: браузер подключается к WebSocket Binance напрямую.

## Платформы и что на них

| Платформа | Что делает | Регистрация |
|---|---|---|
| GitHub | код, Actions | https://github.com/signup |
| Supabase | БД, Realtime, хранилище моделей | https://supabase.com |
| Hugging Face Spaces | Python-бэкенд (Docker) | https://huggingface.co/join |
| Vercel | фронтенд | https://vercel.com/signup |
| cron-job.org | будильник бэкенда | https://console.cron-job.org/signup |
| Twelve Data | котировки FX, металлов, ETF, акций | https://twelvedata.com/register |
| Finnhub (необязательно) | экономический календарь | https://finnhub.io/register |

Список лимитов бесплатных тарифов меняется. Перед регистрацией сверьтесь со страницами Pricing.

## Структура репозитория

```
backend/           корень Hugging Face Space (Dockerfile, FastAPI, анализ, ML)
frontend/          Next.js 14 (Vercel, Root Directory = frontend)
scripts/           supabase_schema.sql
.github/workflows/ train-models, mark-outcomes, deploy-hf (необязательный)
```

## Порядок развёртывания (кратко)

Подробная пошаговая инструкция с кнопками есть в руководстве «только через браузер».

1. **GitHub.** Создайте репозиторий `mie` и загрузите файлы с сохранением путей. Репозиторий можно сделать публичным:
   тогда минуты Actions безлимитны, а секреты остаются закрытыми.
2. **Supabase.** New project. SQL Editor -> вставьте `scripts/supabase_schema.sql` -> Run.
   Скопируйте Project URL, `anon` key и `service_role` key (Settings -> API).
3. **Hugging Face.** New Space -> SDK: Docker. Загрузите содержимое `backend/` в корень Space. В Settings добавьте
   переменные и секреты (таблица ниже). Дождитесь сборки.
4. **Проверка бэкенда.** Откройте `https://ЛОГИН-ИМЯ.hf.space/diagnostics`: все пробы должны быть `ok: true`.
5. **Vercel.** Add New Project -> выберите репозиторий -> **Root Directory = `frontend`** -> добавьте переменные
   -> Deploy. После получения адреса добавьте его в `ALLOWED_ORIGINS` бэкенда.
6. **cron-job.org.** Создайте задание: URL `https://ЛОГИН-ИМЯ.hf.space/tick`, каждые 5 минут.
7. **GitHub Actions.** Settings -> Secrets and variables -> Actions: добавьте секреты. Затем Actions -> Train models ->
   Run workflow для первого обучения.

## Переменные окружения

| Где | Переменная | Значение |
|---|---|---|
| HF Space (secret) | `SUPABASE_URL` | Project URL |
| HF Space (secret) | `SUPABASE_SERVICE_KEY` | service_role key |
| HF Space (secret) | `TWELVE_KEY` | ключ Twelve Data |
| HF Space (secret) | `FINNHUB_KEY` | необязательно |
| HF Space (variable) | `ALLOWED_ORIGINS` | адрес Vercel без слеша на конце |
| Vercel | `NEXT_PUBLIC_API_URL` | адрес Space (`https://….hf.space`) |
| Vercel | `NEXT_PUBLIC_SUPABASE_URL` | Project URL |
| Vercel | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon key (не service_role!) |
| GitHub Actions (secrets) | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `TWELVE_KEY` | те же значения |
| GitHub Actions (необязательно) | `HF_TOKEN`, `HF_USERNAME`, `HF_SPACE` | автодеплой в Space |

Полный список настроек бэкенда: `backend/.env.example`.

## Эндпоинты бэкенда

`/health`, `/tick`, `/diagnostics`, `/signals/{symbol}?tf=M15`, `/scan?tf=M15&asset_class=fx&min_prob=0.5`,
`/best/{symbol}`, `/calendar`, `/candles/{symbol}`, `/instruments`, `/docs` (Swagger).

## Ограничения бесплатного плана

- **Twelve Data:** около 800 кредитов в день. Планировщик ограничивает расход 700, по умолчанию M15 только у 4
  «быстрых» символов (EURUSD, XAUUSD, GBPUSD, USDJPY), остальное на H1. Скальпинг на M1 по FX и акциям на бесплатных
  API нереалистичен. Крипта берётся с бирж без ключа, поэтому M5 и M15 работают.
- **Hugging Face:** Space засыпает без трафика, поэтому нужен пульс от cron-job.org. Диск временный: модели лежат в
  Supabase Storage.
- **Supabase:** 500 MB. Сигналы хранятся 45 дней и чистятся автоматически. Проект ставится на паузу после
  примерно 7 дней без активности, бэкенд пишет пульс сам.
- **GitHub Actions:** в публичном репозитории запланированные workflow отключаются после 60 дней без коммитов
  (включите заново кнопкой Enable). В приватном репозитории действует лимит 2000 минут в месяц. Если запас мал,
  замените в `train-models.yml` расписание на `'0 3 * * 0'` (раз в неделю).
- **Binance:** с американских IP основной домен блокируется. Бэкенд использует `data-api.binance.vision` с запасными
  Kraken и Coinbase.
- **Vercel Hobby** разрешён только для некоммерческого использования.

## Если что-то не работает

| Симптом | Что проверить |
|---|---|
| Сайт пишет «Нет связи с бэкендом» | Space спит или собирается (подождите 1–2 минуты); `ALLOWED_ORIGINS` совпадает с адресом Vercel |
| `/diagnostics`: `supabase_db` не ok | `SUPABASE_URL` и `SUPABASE_SERVICE_KEY`; выполнен ли SQL |
| Лента сигналов пустая, Realtime «ошибка» | выполнен ли блок 4 (Realtime) в SQL; ключ `anon` во Vercel |
| Нет сигналов по FX | `TWELVE_KEY`; блок `budget` в `/diagnostics`; рынок может быть закрыт |
| Календарь пуст | у Finnhub календарь может быть платным: добавьте события в `manual_events` |
| Вероятность помечена `*` | модель не обучена или не прошла проверку: запустите Train models и смотрите логи |

## Лицензия и ответственность

Проект личный, без гарантий. Торговля связана с риском потери капитала.
