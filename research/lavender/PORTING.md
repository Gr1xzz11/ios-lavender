# lavender porting status

Дата аудита: 2026-10-27. Ветка `lavender-port` добавляет только
изолированный диагностический shim; существующий sweet-путь не меняется.

## Подтверждено локальными артефактами

- `backup/lavender-boot.img` имеет Android boot header v1, page size 4096,
  `kernel_addr=0x8000`, `ramdisk_addr=0x1000000`, `tags_addr=0x100` и не имеет
  встроенного DTB.
- Оба DTB-кандидата содержат GICD `0x17a00000`, GICR `0x17b00000`, UART
  `0x0c170000`, SDHCI `0x0c0c4000` и CMDQ `0x0c0c5000`, но различаются CPU
  compatibility и другими узлами; выбор DTB для XNU не сделан.
- DTS описывает UART как `qcom,msm-uartdm-v1.4` с диапазоном `0x1000`, а
  SDHCI — с двумя диапазонами.
- Splash reserve/framebuffer и `0xb0000000` не считаются безопасными для
  диагностического кода; shim в framebuffer не пишет.

## Изменения

`shim/build-lavender-diag.sh` собирает отдельный arm64 Linux Image и
упаковывает его как Android header v1 без DTB: ABL должен передать live FDT в
`x0`. `diag_start.S` устанавливает только стек, маскирует исключения, чистит
`.bss` и вызывает `diag_main`. `diag.c` не включает XNU, MMU, GIC, таймеры,
PSCI, UFS или framebuffer. Перед записью shim ограниченно читает UART status
`0x08` и пишет в TX FIFO `0x70` только при `TX_READY` (bit 2). База и диапазон
подтверждены DTS, offsets подтверждены upstream Linux Qualcomm UARTDM driver;
clock/pinctrl после ABL всё ещё требуют hardware-проверки.

Наблюдаемый вывод: `LAVENDER-DIAG:entry`, адрес FDT, MPIDR и
`LAVENDER-DIAG:stack-bss`. Бесконечный `wfe` после маркера не считается
успешной загрузкой.

`tools/check-lavender-diag.py` проверяет header v1, адреса lavender, отсутствие
second stage/embedded DTB, размер kernel и arm64 Image header. Sweet
`shim/build.sh`, `tools/mkadt.py` и `tools/mkpayload.py` остаются отдельным
sweet/XNU pipeline; перенос synthetic ADT на lavender до подтверждения layout
был бы предположением.

## Проверка

2026-10-27 локальная сборка через `clang --target=aarch64-none-elf`, lld и
`llvm-objcopy` (системного `aarch64-linux-gnu-gcc` нет):

```
OK: Android v1, page=4096, kernel=17232, no embedded DTB
```

`tools/validate-repo.py` прошёл: 81 patch, 16 Python tools, 8 shell scripts.
Телефон не подключался; fastboot/adb/write операции не выполнялись.

## Риски и следующий этап

- Не подтверждено, что ABL передаёт DTB в `x0` для такого образа.
- Не подтверждены clock/pinctrl и доступность UART после handoff; при
  выключенном UART маркер не будет виден.
- Не доказаны фактические load/entry адреса, stack range и непересечение
  буферов на ABL lavender, поэтому образ не объявляется безопасным для запуска.
- DTB-кандидаты — MTP-derived исследовательские входы, не доказанный runtime
  FDT lavender.

Следующий этап: source-level/read-only сопоставление DTB и UARTDM register map,
затем статический harness для entry/load/stack/memory ranges. Только после
этого проектировать lavender ADT и отдельный payload profile для XNU.
