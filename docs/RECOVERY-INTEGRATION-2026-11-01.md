# Локальная интеграция восстановления lavender — 2026-11-01

Рабочий репозиторий: `C:\Users\Admin\Desktop\ios-lavender`.
Восстановление: `C:\RN7-Recovered\Coding\RN7\ios-sweet`.
Архив: `C:\Linux\Coding.zip`, 10 706 189 543 байта.
Операции выполнены одним агентом. Телефон, GitHub Actions и полные сборки не запускались.

## 1. Что проверено и восстановлено

Оба ключевых бинарника существуют в восстановленной копии и совпадают с эталонами SHA256:

| Путь относительно `research\lavender\.artifacts` восстановленной копии | SHA256 |
|---|---|
| `xnu-recovered\kernel.development.lavender` | `40a9f79d3dbf63344d5dd3365dbcb2ced9298f06e86332840c93d45e48683cd5` |
| `xnu-pa-continuations-20261028-1745\lavender-xnu-pmsg-sequence.img` | `3269975b4637c4b9d4043fca3f7bce3ba2071ea51804ef973b8839c89b726683` |

Mach-O имеет magic `0xfeedfacf`, CPU type `0x0100000c` (ARM64). Это восстановленный Apple XNU, а не Linux с переименованным файлом. Проверены также SHA256 исторических `kernel.entry-pmsg`, `payload.bin`, `Image`, PMSG-выгрузки, более свежего boot image и двух последующих runtime-выгрузок: 9/9 совпадений. Полные пути и эталоны — `artifact-sha256.json`.

Хеши 24 файлов `*.img` записаны в `boot-image-sha256.json`. Наличие хеша в этом списке само по себе не означает совпадение с независимым эталоном. Большие артефакты оставлены в восстановленной копии; в рабочий Git они не переносились.

231 небольшой исходник, скрипт и документ проверен по CRC32 центрального каталога ZIP64, без повторной распаковки архива: все совпали. CRC проверяет соответствие архивной записи, но не является криптографическим доказательством происхождения. Источники, выбранные для интеграции, прошли эту проверку.

## 2. Инвентаризация до изменений

`recovery-inventory.csv` перечисляет каждый файл восстановленного проекта, кроме внутренностей `.git`, с размером, категорией и сравнением с рабочим каталогом. Сначала сравнивались байты; затем текстовые различия LF/CRLF выделены отдельно. Бинарные файлы не объявлялись одинаковыми по нормализованному тексту.

| Категория | Отсутствовали в рабочей копии | Содержательно отличались | Только LF/CRLF |
|---|---:|---:|---:|
| Исходники/патчи | 9 | 3 | 104 |
| Скрипты/конфигурация | 41 | 4 | 47 |
| Документация/логи | 13 | 3 | 5 |
| Артефакты в `.artifacts`, `out`, `backup`, либо >10 MiB | 470 | 0 | 0 |
| Прочее, включая кэш Python и небольшие бинарники | 59 | 0 | 12 |

Это классификация по пути/расширению, а не оценка необходимости переноса: например, DTS и небольшие DTB попали в «прочее», `differences.patch` — в исходники. Два исходника уже совпадали: восстановленные пользователем loader и PMSG. Большинство прочих исходников отличается только переводами строк.

В проверенном состоянии единственный файл рабочего каталога, отсутствовавший в восстановленной копии, — `shim\lavender_loader.c.before-recovery`. Утверждение о 21 дополнительном файле `shim` для этих конкретных каталогов не воспроизвелось. Ничего не удалялось для приведения копий к совпадению; все ранее отслеживаемые файлы сохранены. `.git` обеих копий не объединялись.

Содержательные отличия до интеграции: `AGENTS.md`, `NOTES.md`, `research\lavender\PORTING.md`; три файла shim (`lavender_loader.h`, `lavender_shim.c`, `lavender_start.S`); четыре tools (`check-lavender-diag-stocklike.py`, `make-lavender-diag-stocklike.py`, `preserve-lavender-bootv1-fields.py`, `test-lavender-xnu-shim.py`). Сравнение loader с HEAD учитывалось отдельно: он уже был изменён до начала работы.

## 3. Изменения загрузчика относительно HEAD

| Группа | Восстановленное поведение |
|---|---|
| PMSG | Условные `LAVENDER_PMSG_SHIM`, `PMSG_MARK`, `LAVENDER_TAG`; маркеры DTB/payload/контракта, 10 сегментов, копирования, boot_args, последнего loader checkpoint |
| Загрузка XNU | Явное `PA = phys_base + (VA - virt_base)` с проверками переполнения вместо wraparound-арифметики; локальные копии метаданных/командной строки/сегментов; контроль `_head.._end`; массив source ranges |
| Порядок копирования | ADT копируется первым, сегменты — с последнего к первому; `copy_overlap_safe` допускает перекрытие собственного источника; проверяется сохранность источников ещё не скопированных сегментов и неперекрытие назначений |
| boot_args | RAM `0x80000000..0x85600000`, 16 KiB страницы, размер структуры 736; `deviceTreeP` изменён с VA на PA; framebuffer остаётся нулевым |
| MMU/cache | Новый код настройки MMU/TTBR не добавлен. Перед вызовом XNU сохранён барьер `dsb sy; ic iallu; dsb sy; isb`. Комментарий о выключенных MMU/cache — предпосылка handoff, а не проверка SCTLR на устройстве |
| PSCI | Weak checkpoint допускает диагностическую реализацию; stage1 reset после DTB, stage2 после сегментных проверок, финальный reset вместо вызова XNU при соответствующих макросах. Реализация использует `PSCI_SYSTEM_RESET=0x84000009`, `smc #0` |
| Диагностика | `LAVENDER_LOADER_NO_UART` позволяет линковать без UART; отдельный handoff probe останавливается до loader/XNU |

`deviceTreeP=kernel_pa` сохранён как восстановленное поведение. Его корректность после включения MMU не доказана runtime-данными; VA/PA наугад не менялись. Обработчики исключений и доказанный MMU fault channel этим восстановлением не добавлены.

## 4. Что интегрировано и почему

Восстановлены 48 отсутствовавших файлов непосредственно в `shim` и `tools`, плюс 7 содержательно отличавшихся зависимостей. `integration-files.json` перечисляет эти 55 путей. Уже присутствовавшие `lavender_loader.c` и `lavender_pmsg.c` сохранены без изменения логики.

Добавлены `lavender_diag.h`, reset/preloader/timer исходники, 12 сборочных обёрток, патчеры XNU, упаковщик ramdisk и статические проверки. Обновлены:

- `lavender_loader.h`: объявления checkpoint/reset и условные макросы для восстановленного loader.
- `lavender_shim.c`: вызов PMSG writer, `CALL_LOADER`, handoff probe и вариант без UART.
- `lavender_start.S`: ARM64 Image `text_offset` исправлен с `0` на stock-подобный `0x80000`. Маскирование DAIF уже было в HEAD; оно не является новым изменением.
- `make-lavender-diag-stocklike.py`: сохранение stock gzip OS byte.
- `preserve-lavender-bootv1-fields.py`: сохранение остальных stock v1 scalar fields, ID и расширения при сохранении новых размеров kernel/ramdisk; это контракт восстановленных checker-ов.
- `check-lavender-diag-stocklike.py` и `test-lavender-xnu-shim.py`: согласованные проверки этих полей и восстановленных режимов loader.

Добавлен Windows PowerShell collector `tools\collect-lavender-pmsg-recovery.ps1`: только чтение через выбранный ADB serial, бинарное копирование stdout, отдельные exit codes/stderr и SHA256. Он подготовлен и синтаксически проверен, но не запускался на телефоне.

`build-lavender-xnu.sh` оставлен обычным непишущим PMSG вариантом. Специализированные PMSG wrappers компилируют **и линкуют** `lavender_pmsg.c` и передают `LAVENDER_PMSG_SHIM`/`LAVENDER_LOADER_NO_UART`. Reset wrappers подключают свою реализацию и соответствующие stage-макросы. Все буквальные ссылки на исходники, локальные заголовки, linker script и Python tools разрешаются.

Default build ID восстановленных исходников и XNU patcher — `B20261028_2355`. Это исторический ID: перед новым будущим билдом нужны согласованное изменение ID в header/patcher/checks либо поддержка общего параметра. Одно переопределение C-макроса не меняет ID, зашитые в Python patcher. Handoff probe использует собственный `B20261029_HANDOFF` и не доказывает выполнение XNU.

Резервные копии исходного рабочего состояния, loader из HEAD, diff и файл `.before-recovery` сохранены вне рабочего репозитория:
`C:\Users\Admin\Documents\Codex\2026-11-01\apple-xnu-ios-xiaomi-redmi-note\work\backup-before-integration`.
Старые NOTES/PORTING/AGENTS не заменялись восстановленными целиком; в NOTES добавлен новый handoff.

## 5. Повреждения и отсутствующие данные

`C:\Linux\zip-test.txt` сообщает 14 ошибок: 13 внутри этого проекта и одну в стороннем ZIP HyperOS. Все 13 проектных файлов существуют, но повторная CRC32-проверка извлечённых файлов подтвердила несовпадение **13/13**. Некоторые имеют правильный размер и всё равно повреждены. Их не удаляли и не использовали как надёжные inputs:

Пути ниже относительно восстановленного `research\lavender\.artifacts`:

1. `xnu-recovered/kernel.development.lavender.link/kernel.development.lavender.a`
2. `seg0-kernel-20261028-0951/kernel.entry-pmsg`
3. `orangefox-backup-audit-20261029-133600/diag-unpacked/kernel`
4. `orangefox-backup-audit-20261029-133600/diag-unpacked/ramdisk`
5. `xnu-c-startup-20261028-2055/xnu-c-startup-disassembly.txt`
6. `orangefox-repro-20261028-2230/stock-ramdisk.gz`
7. `recovery-kernel-check-20261028-2146/kernel-gzip-member.gz`
8. `known-path-audit-20261029-132648/pa/ramdisk`
9. `known-path-audit-20261029-132648/fresh/ramdisk`
10. `xnu-code-reached-20261028-1530/payload.bin`
11. `xnu-code-reached-20261028-1530/kernel.entry-pmsg`
12. `xnu-code-reached-20261028-1530/stock-ramdisk`
13. `xnu-code-reached-20261028-1530/ramdisk`

Подробные размеры/CRC — `damaged-files.json`. Здоровые одноимённые файлы в другом каталоге не объявлялись заменой соответствующей исторической сборки.

Историческая диагностическая recovery с SHA256 `7b423c9a8c24a2994df297149e7b438c6622f7e80a67b477a7eda79b913ccb35` отсутствует среди найденных image-файлов. Отсутствуют точный patch временного pre-zap hook `fs/pstore/ram.c`, полные исторические build inputs и доказательство идентичности reader ABI. Перечень исходников сам по себе не делает полную сборку воспроизводимой.

## 6. Доказательства выполнения XNU и границы вывода

База исторических доказательств — восстановленный каталог `xnu-pa-continuations-20261028-1745`:

- SHA256 boot image, patched Mach-O, payload, shim Image и PMSG совпали с REPORT.md.
- Выгрузка `pmsg-ramoops-0.raw`: 1476 байт, SHA256 `9fb5daead2ceb9b12935e2c09677c6a0cdc22083a7d7418344a1732285cc2605`.
- Содержит последовательность `XNU_ENTRY → XNU_BEFORE_FIRST → XNU_CODE_REACHED` с ID `B20261028_1700`.
- Статические сведения: entry VA `0xfffffe0007487488`, PA `0x81487488`; entry cave PA `0x81482780`; первый original instruction site PA `0x814890ec`; code cave исполняет `0xd510109f` (`msr OSLAR_EL1,xzr`) перед записью `XNU_CODE_REACHED`. Indirect продолжения исторического исправления переведены из high-half VA в PA.

По сохранённым данным подтверждается историческое исполнение инструментированного Mach-O entry и первой оригинальной инструкции XNU. Это не новое аппаратное наблюдение текущей сессии. Сам маркер после инструкции ещё не доказывает, что следующий переход или `DAIFSet` завершился. Полное MMU/C startup, запуск userspace и загрузка iOS не доказаны.

Не смешивать это с `B20261028_2030`: более поздний сохранённый текст с этим ID мог переживать последующие перезагрузки. Совпадение старых записей до/после не подтверждает повторное исполнение.

Поздний тест 2026-10-29 использовал image SHA256 `a1853c50dbb27331ac371706fbd31511aade064d166fe4a035cbbf86daf171c2`, ID `B20261028_2355`. Сохранённая fresh PMSG (SHA256 проверен) не содержит этого ID и XNU-маркеров. Отсутствие даже SHIM ограничивает наблюдение всей цепочки; конкретный XNU checkpoint как место остановки не установлен.

## 7. PMSG: что известно и что проверять дальше

Writer: base `0xA0200000`, signature `0x43474244`, header 12 байт, capacity `0x1FFFF4`, data с `0xA020000C`. Он **не инициализирует** пустой/неверный header, а молча возвращает; поэтому даже выполненный shim может не оставить маркер. Data публикуются перед индексами, используются `dc cvac` и `dsb sy`, предполагается cache line 64 байта. Нет runtime-проверки EL/cache attributes либо подтверждения сохранности RAM через ABL.

Исходный writer и восстановленный raw decoder трактуют `start` как начало логических данных и дописывают по `(start+size)%capacity`. Синтетический тест проверяет согласованность именно этой модели. Он **не проверяет** её совместимость с точной реализацией `persistent_ram_write/save_old` реально запущенного recovery. Без exact source/raw header нельзя считать ABI доказанным только по совпадению адресов, размеров и signature. Логи исторического reader hook не заменяют его отсутствующий patch. Логика writer/decoder намеренно сохранена для сравнения с известным историческим образом.

В поздней recovery логи показывают reservation `0xA0000000..0xA0400000`, console 2 MiB и PMSG 2 MiB, `record_size=ftrace_size=ecc=0`, `mem_type=0`. База PMSG действительно вторая половина, `0xA0200000`; оснований менять её на `0xA0000000` нет. Однако параметры надо заново снять с текущего устройства.

`manual-reset-pmsg-20261029-132214/after-pmsg.raw` совпал с эталоном SHA256 и содержит `RN7_MANUAL_RESET_20261029`: Linux→manual reset→Linux retention работал. Это не проверяет bare-metal writer и сохранение RAM при входе в другой boot image.

Исторический reader имел описанный raw-buffer hook до zap; более новая recovery `f07d6971...` — standard PMSG frontend. Отдельные более ранние captures показывали `CONFIG_PSTORE_PMSG=n` при существовавшем старом файле. Нельзя смешивать конфигурацию ядра, хеш recovery-раздела и происхождение запущенного ядра: последнее могло быть загружено иным способом. Наличие файла в pstore не доказывает наличие `/dev/pmsg0` writer.

## 8. Быстрые проверки

- 63 Python-файла: AST syntax без исполнения сборок.
- 26 shell-файлов: `bash -n` через Git Bash, stdin с нормализованным LF. Это проверка синтаксиса; запуск CRLF shell-файлов напрямую на Linux требует LF checkout.
- 15 существовавших статических checks для loader, PMSG, ID, entry, C startup, reset и classifier: прошли.
- Буквальные repo dependencies build wrappers и quoted includes shim: все найдены.
- `git diff --check`: прошёл; финальный staged check записывается отдельно.
- PowerShell collector: Parser syntax прошёл; на устройстве не выполнялся.
- На восстановленном историческом наборе прошли `check-lavender-pmsg-sequence.py` и `check-lavender-loader-psci-reset.py`: 10 сегментов, entry PA `0x81487488`, Android v1, gzip + stock DTBs, payload + stock ramdisk. Также прошёл восстановленный ADT-first static regression.

ARM64 clang/LLVM toolchain не найден в PATH/стандартном LLVM-каталоге; target C/assembly syntax и линковка не проверялись. XNU/Linux/OrangeFox сборки не выполнялись по ограничению пользователя. Runtime-результаты, корректность MMU и совместимость bootloader не проверялись статическими тестами. Старые проверки не являются полной формальной проверкой произвольного повреждённого payload.

Локальный commit, предписанный AGENTS.md, остановлен Git с `Author identity unknown`: `user.name`/`user.email` не настроены. Авторство не выдумывалось и Git config не менялся. Изменения оставлены staged. Итоговый status: 9 modified + 51 added, без удалений; staged diff: 60 files changed, 2895 insertions(+), 51 deletions(-). Обычный `git diff --stat` пуст, поскольку все изменения находятся в index. Полные фактические status и обе формы diff stat записаны в `git-state.txt`.

## 9. Один следующий аппаратный эксперимент — контроль исторического образа с текущим reader

Не выполнен. Цель: оставить XNU image неизменным (SHA256 `3269975b...`) и проверить воспроизводимость старого результата с **текущим** recovery. Полную пересборку и изменение ramoops пока исключить. Все ADB-команды collector только читают; единственный будущий запуск — temporary `fastboot boot`, без записи разделов.

Использовать PowerShell 7 (`pwsh`), ADB/fastboot в PATH. Вручную войти в текущую recovery, взять serial из `adb devices -l`, затем:

```powershell
$repo = 'C:\Users\Admin\Desktop\ios-lavender'
$old = 'C:\RN7-Recovered\Coding\RN7\ios-sweet\research\lavender\.artifacts\xnu-pa-continuations-20261028-1745\lavender-xnu-pmsg-sequence.img'
$capture = Join-Path $repo ('research\lavender\.artifacts\historical-control-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$serial = 'ВСТАВИТЬ_ФАКТИЧЕСКИЙ_SERIAL'
if ((Get-FileHash -LiteralPath $old -Algorithm SHA256).Hash -ne '3269975b4637c4b9d4043fca3f7bce3ba2071ea51804ef973b8839c89b726683') { throw 'Image hash mismatch' }
& "$repo\tools\collect-lavender-pmsg-recovery.ps1" -Serial $serial -OutDir "$capture\before"
$beforeText = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes("$capture\before\pmsg.bin"))
if ($beforeText.Contains('@B20261028_1700')) { throw 'Historical ID already present: this experiment cannot establish freshness. Preserve capture and stop.' }
```

Перед переходом дальше проверить `.exit.txt`/stderr, `identity.txt`, `ramoops.txt`, `recovery-node.txt`: это recovery lavender, PMSG действительно прочитан, reservation соответствует 4 MiB/2 MiB split. Хеш `recovery-partition.img` сравнить с локальным image-каталогом; несовпадение размера/ошибка чтения означает отсутствие доказательства provenance. Записать способ входа в recovery. Если этих данных нет — остановиться на read-only capture.

После ручного перехода в fastboot, только при выполненных условиях baseline:

```powershell
fastboot -s $serial getvar product
fastboot -s $serial getvar unlocked
# Продолжать только для product=lavender, unlocked=yes.
fastboot -s $serial boot $old
# После зависания вручную вернуться тем же способом в ту же recovery.
& "$repo\tools\collect-lavender-pmsg-recovery.ps1" -Serial $serial -OutDir "$capture\after"
$afterText = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes("$capture\after\pmsg.bin"))
$afterText | Select-String 'LAVENDER:(SHIM|LOADER|XNU_ENTRY|XNU_BEFORE_FIRST|XNU_CODE_REACHED)@B20261028_1700' -AllMatches
```

`Booting OKAY` не считать подтверждением entry. Если temporary boot не принят, остановиться; не заменять его flash. Temporary boot отличается от исторически записанного flash boot, поэтому неуспех также оставляет boot-method/selection как переменную.

Ожидаемая интерпретация:

| Наблюдение | Вывод |
|---|---|
| Новый `SHIM@B20261028_1700`, затем все 3 XNU-маркера | Историческая цепочка воспроизводится с текущим reader; дальше сравнивать поздний image, сохранив recovery и reset path |
| SHIM/LOADER есть, XNU-маркеров нет | Канал работает до loader; локализовать последнюю свежую стадию, а не менять recovery вслепую |
| Ни одного свежего SHIM | Не различены отсутствие исполнения, отказ writer по header, потеря RAM и различие reader; отсутствие XNU не доказано |
| Старый ID уже в baseline либо capture неуспешен | Свежесть/канал не установлены; запуск не проводить |

Для последнего случая следующий диагностический input — read-only снимок **до zap** обоих reserved regions (включая 12-byte header) через уже существующий доказанный reader либо восстановленный точный hook/kernel. Не пытаться читать физическую память через выдуманный `/dev/mem`, не очищать pstore и не строить новую recovery в этом задании. Сравнить raw signature/start/size, расположение ASCII-маркеров и экспорт `/sys/fs/pstore`; это разделит writer ABI и reader/export. Одно исчезновение записей после перезагрузки не даёт такого разделения.
