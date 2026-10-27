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

## Внешняя source-level сверка

- AOSP `boot_img_hdr_v1` описывает `kernel_addr` как physical load address и
  для v1 требует page-aligned kernel/ramdisk/second/recovery-dtbo layout:
  [bootimg.h](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/android16-release/include/bootimg/bootimg.h).
- AOSP `mkbootimg.py` записывает в header `base + kernel_offset`; сам header
  не хранит отдельное поле `base`:
  [mkbootimg.py](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/main/mkbootimg.py).
- Qualcomm LK `aboot.c` в открытой реализации вызывает `boot_linux()` с
  `hdr->kernel_addr`, `hdr->ramdisk_addr` и `hdr->tags_addr`; это подтверждает
  прямую семантику header, но не доказывает поведение закрытого lavender ABL:
  [aboot.c](https://github.com/tsgan/qualcomm/blob/master/lk/app/aboot/aboot.c).
- ARM64 Linux boot protocol ожидает DTB в `x0`, `x1..x3 = 0`, EL1/EL2 и MMU
  off; diagnostic shim теперь печатает все исходные `x0..x2`, чтобы проверить
  фактический ABL handoff:
  [Linux arm64 booting](https://kernel.org/doc/html/v5.17/arm64/booting.html).

## ABL lavender: результат поиска и границы доказательства

В локальных файлах, подкаталогах рабочего дерева, `/tmp` и доступных локальных
носителях подходящего `abl.elf`, `abl.img` или fastboot-архива lavender не
найдено. Поэтому закрытый ABL Redmi Note 7 статически не анализировался и
выводы ниже не следует приписывать именно его реализации.

Безопасный исходный артефакт для следующего шага — официальный fastboot ROM
для `lavender`, региона и ветки, соответствующих `backup/lavender-boot.img`,
полученный через [Xiaomi ROM Download portal](https://c.mi.com/global/miuidownload/index)
(на странице модели выбрать Fastboot Update). Из распакованного архива нужен
только ABL из `images/` или `firmware-update/` — в Xiaomi-пакетах он обычно
называется `abl.img`; это может быть ELF без суффикса `.elf`. Перед анализом
нужно проверить `file`, `readelf -h`, SHA-256 и board/version strings. Нельзя
считать подходящим ABL от `sweet`, другого SoC, другого региона/ветки или
неизвестного boot chain.

Стоковый дамп имеет `os_version=0x14000158`, что декодируется как Android 10,
patch year 2021, month 8. Это полезный ориентир совместимости, но не доказано,
что он совпадает с версией ABL: в `boot.img` ABL не хранится.

Открытая Qualcomm LK-реализация показывает обычную схему `boot_linux()` с
`hdr->kernel_addr`, `hdr->ramdisk_addr` и `hdr->tags_addr`, но это source-level
аналог, а не lavender ABL. Поэтому подтверждено только следующее:

* в нашем v1 header физический offset/load field равен `0x8000`;
* при гипотезе ABL base `0x80000000` арифметический адрес образа был бы
  `0x80008000`, а entry — тем же адресом (`_head=0`);
* абсолютные base, DTB placement и сохранение `x0` закрытым lavender ABL не
  подтверждены; `0x80008000` нельзя объявлять фактом.

## Анализ полученного Xiaomi ROM и `abl.elf`

Локальный архив
`/mnt/LocalDisk/Downloads/Linux/miui_LAVENDEREEAGlobal_V12.5.1.0.QFGEUXM_39f6c7990f_10.0.zip`
имеет SHA-256
`2e4be961b13b7056dbaa9684e4052a94eb37946abbfcca86afd7f0082478cc0a`.
Это подписанный Android JAR/ZIP recovery ROM (`signed by SignApk`), но в нём
есть `firmware-update/abl.elf` размером 151552 байта. Извлечён только этот
файл в `research/lavender/firmware/abl.elf`; исходный архив не изменялся и в
git бинарный firmware-артефакт не добавлялся.

SHA-256 извлечённого ABL:
`d3c34e19619696d110da0f34242d9a3696397c553088715cb1f47c4e45d5d74a`.
ELF header и program headers:

```
class       ELF32, little-endian, ARM, ET_EXEC
entry       0x9fa00000
PT_LOAD     file 0x3000, vaddr/paddr 0x9fa00000
            filesz/memsz 0x22000, flags RWE, align 0x1000
```

Это подтверждает адрес размещения и entry самого ABL в Qualcomm boot chain,
но не `kernel_addr` Android boot header. `abl.elf` является 32-битным ABL;
это совместимо с тем, что он затем передаёт управление 64-битному ARM64
Linux/XNU shim.

В load segment обнаружен EFI Firmware Volume: `_FVH` на offset `0x3028`,
длина FV `0x22000`, header length `0x48`. Первый FFS имеет тип Firmware
Volume Image и содержит GUID-defined vendor section с data offset `0x18`.
ELF не имеет section headers или символов; внутри отсутствуют `ANDROID!` и
валидный DTB magic. Единственный `MZ` в payload находится в высокоэнтропийном
vendor data и не образует распознаваемый PE header. Поэтому из этого
артефакта надёжно видны только ELF/FV container и ABL load/entry, но не
внутренние функции Android boot path.

Сопоставление с shim:

- ABL load `0x9fa00000` не должен использоваться как адрес shim/kernel.
- `kernel_addr=0x8000` в boot.img остаётся отдельным Android v1 полем.
- Нельзя подтвердить по этому stripped/packed ABL, что lavender ABL делает
  `load = 0x80000000 + 0x8000`, передаёт DTB в `x0` или сохраняет любые
  другие регистры.
- Архивный `boot.img` имеет те же `kernel_addr=0x8000`, page size 4096,
  header v1 и `os_version=0x14000158`, но отличается от сохранённого boot:
  его `kernel_size=26043409` и `ramdisk_size=0`. Он не использовался как
  источник DTB или как образ для shim.

Для полного анализа handoff потребуется не другой случайный ROM, а
распакованный внутренний `LinuxLoader`/PE из этого ABL либо открытые symbols
для соответствующей версии ABL. Без этого утверждать физический адрес
ядра, расположение DTB или точный ARM64 jump нельзя.

## Изменения

`shim/build-lavender-diag.sh` собирает отдельный arm64 Linux Image и
упаковывает его как Android header v1 без DTB: ABL должен передать live FDT в
`x0`. `diag_start.S` устанавливает только стек, маскирует исключения, чистит
`.bss` и вызывает `diag_main`. `diag.c` не включает XNU, MMU, GIC, таймеры,
PSCI, UFS или framebuffer. Перед записью shim ограниченно читает UART status
`0x08` и пишет в TX FIFO `0x70` только при `TX_READY` (bit 2). База и диапазон
подтверждены DTS, offsets подтверждены upstream Linux Qualcomm UARTDM driver;
clock/pinctrl после ABL всё ещё требуют hardware-проверки.

Наблюдаемый вывод: `LAVENDER-DIAG:entry`, исходные `ARG0`, `ARG1`, `ARG2`,
MPIDR и `LAVENDER-DIAG:stack-bss`. Это позволяет проверить, в каком именно
аргументе ABL передал DTB, вместо принятия x0 за факт. Бесконечный `wfe` после
маркера не считается успешной загрузкой.

`tools/check-lavender-diag.py` проверяет header v1, адреса lavender, отсутствие
second stage/embedded DTB, размер kernel и arm64 Image header. Sweet
`shim/build.sh`, `tools/mkadt.py` и `tools/mkpayload.py` остаются отдельным
sweet/XNU pipeline; перенос synthetic ADT на lavender до подтверждения layout
был бы предположением.

`tools/preflight-lavender-diag.py` дополнительно сравнивает структурные поля
с `backup/lavender-boot.img` и проверяет ELF symbols. Без искусственно
заданной relocation base он получает:

```
header kernel_addr=0x8000; physical base/DTB placement unresolved by header
```

Если явно подставить гипотезу `--ram-base 0x80000000`, диапазон получается
`0x80008000..0x8000c7d0`, entry `0x80008000`, stack top `0x8000c7d0`, ниже
`0x85700000`. Это проверяет только арифметику гипотезы; ABL lavender и DTB
placement этим не подтверждаются.

## Проверка

2026-10-27 локальная сборка через `clang --target=aarch64-none-elf`, lld и
`llvm-objcopy` (системного `aarch64-linux-gnu-gcc` нет):

```
OK: Android v1, page=4096, kernel=18384, no embedded DTB
OK: v1 fields match stock; header kernel_addr=0x8000; physical base/DTB placement unresolved by header
```

Дополнительный отрицательный тест с явной гипотезой
`--ram-base 0x80000000` выводит `0x80008000..0x8000c7d0`, `_start=0x80008040`
и стек до `0x8000c7d0`; это проверка арифметики и границ образа, не проверка
ABL. `tools/validate-repo.py` прошёл: 81 patch, 17 Python tools, 8 shell
scripts. `git diff --check` прошёл.
Телефон не подключался; fastboot/adb/write операции не выполнялись.

## Риски и следующий этап

- Не найден локальный lavender ABL; не подтверждены его версия, физическая
  relocation base, DTB placement и передача DTB в `x0`.
- Не подтверждены clock/pinctrl и доступность UART после handoff; при
  выключенном UART маркер не будет виден.
- Не доказаны фактические load/entry адреса, stack range и непересечение
  буферов на ABL lavender, поэтому образ не объявляется безопасным для запуска.
- DTB-кандидаты — MTP-derived исследовательские входы, не доказанный runtime
  FDT lavender.

Следующий этап: source-level/read-only сопоставление DTB и UARTDM register map,
затем статический harness для entry/load/stack/memory ranges. Только после
этого проектировать lavender ADT и отдельный payload profile для XNU.

Надёжного обычного канала подтверждения выполнения без UART не найдено:
boot.img v1 не предоставляет completion/status reply, ABL не обязан сохранять
регистры после handoff, а RAM-маркер теряется или недоступен после reset.
JTAG/ICE мог бы наблюдать PC/GPR без записи на устройство, но такой интерфейс
не подтверждён и не является доступным runtime-механизмом. Добавлять для этого
PSCI reset, watchdog, IMEM/restart-reason или framebuffer было бы опасным
расширением scope.

Если UART clock выключен, чтение status может вернуть неготовность и shim
пропустит все TX-записи; если interconnect/peripheral не отвечает на gated
clock, даже MMIO read не имеет гарантии bounded completion. Если clock включён,
но pinctrl в sleep/GPIO-состоянии, записи могут проходить во FIFO, но на
физическом UART RX хоста байты не появятся. В обоих случаях fallback-канала
сейчас нет: `wfe` после попыток вывода не является доказательством загрузки.
