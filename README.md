# shift-report-bot

![ci](https://github.com/quueli/shift-report-bot/actions/workflows/ci.yml/badge.svg)

people post shift reports into a telegram chat as free text. this turns them into numbers.

a report looks roughly like "Отчёт от 14.02 / Закрытие смены / name / начало 14:00 / конец 22:00 / финотчёт 12000 / итого ...", except every person writes it differently: fields in random order, labels spelled three ways, the value on the next line, a shift that ends at 00:30, a total that doesnt add up. the parser is a small state machine that doesnt care about order, matches labels exact -> prefix -> fuzzy, and puts anything it cant place into `extras` and every inconsistency into `issues` instead of giving up.

money is Decimal everywhere. hours handle the wrap past midnight. reports are grouped by the shift's start date so a 02:40 post counts for the day before.

only the parsing + analytics core is here, the bot / scheduler / db wiring stayed private.

    python -m examples.parse_report   # parses examples/sample_reports.txt, stdlib only
    pip install pytest && pytest
