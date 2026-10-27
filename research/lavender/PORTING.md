# lavender porting status

Дата аудита: 2026-10-27. Ветка `lavender-port` добавляет только
изолированный диагностический shim; существующий sweet-путь не меняется.

## XNU artifact preflight (run 40487392402)

Артефакт `xnu-kernel` распакован во временный каталог и не добавлен в git.
`SHA256SUMS` совпадает с фактическим файлом:

```
40a9f79d3dbf63344d5dd3365dbcb2ced9298f06e86332840c93d45e48683cd5  kernel.development.lavender
```

Файл — Mach-O 64-bit ARM64 PIE, entry point
`0xfffffe0007487488` находится в `__TEXT_EXEC`; верхняя граница сегментов —
`0xfffffe00080ac000`. Chained fixups отсутствуют. Статическая проверка
реализована в `tools/preflight-lavender-xnu.py`.

Текущая арифметика `mkpayload.py` физически кладёт сегменты в
`0x81004000..0x820ac000` при lavender `dram-base=0x80000000`; сам диапазон
ядра не пересекает фиксированные carve-out’ы DTS. Но `boot_args` передают XNU
`memSize=0x80000000`, то есть XNU может считать управляемой всю нижнюю RAM и
выделить страницы поверх wlan/modem/ADSP/splash/pstore. Preflight намеренно
завершается `BLOCKED` на этом условии. Это блокер boot.img, а не проблема
Mach-O или entry point.

Следующий кодовый шаг — отдельный подтверждённый memory-map path для XNU:
полноценно исключить fixed и dynamic reserved-memory из allocator либо
использовать консервативное проверенное окно RAM. Для первого варианта уже
проверено, что `xnu-8796.141.3` не поддерживает это через DT: arm64
`arm_vm_init()` читает только `boot_args.physBase/memSize`, рассчитывает
`gPhysBase/gPhysSize`, а `pmap` выдаёт страницы из одного интервала
`first_avail..avail_end`; `/reserved-memory` и `/chosen/memory-map` allocator
не читает. `memoryMap` в arm64 `boot_args` отсутствует (он есть в i386 ABI).

Реализован безопасный ограниченный профиль: `dram-base=0x80000000`,
`dram-size=0x05600000`, то есть `[0x80000000,0x85600000)`. Все фиксированные
reserved-memory области начинаются не раньше `0x85600000`, а kernel/ADT/boot
args помещаются в это окно. Полная физическая двухбанковая карта остаётся в
`/memory.reg` и `dram-high-*` только как справочная; она не передаётся XNU как
управляемая память. Dynamic `shared-dma-pool` узлы имеют широкие
`alloc-ranges`, но не фиксированный `reg`; этот профиль предполагает запуск
непосредственно после ABL, до Linux allocator. Это остаётся отдельным риском,
который нельзя снять только статическим DTS-анализом.

`tools/preflight-lavender-xnu.py` теперь требует путь к исходникам XNU и
проверяет фактическую цепочку `dram-*` → `boot_args` → `arm_vm_init` → `pmap`,
фиксированные reservations и запас под ADT/boot_args. Старый BLOCKED снят
только для этого проверенного ограниченного окна; boot image по-прежнему не
создаётся до отдельной проверки ABL ramdisk placement.

## Полный layout-аудит первого XNU payload

Для артефакта run `40487392402` и lavender ADT рассчитаны следующие адреса:

```
kernel:    0x81004000..0x820ac000
ADT:       0x820ac000..0x820ade00
boot_args: 0x820b0000..0x820b4000
avail_end: 0x85600000
entry:     VA 0xfffffe0007487488 -> PA 0x81487488
```

Символы XNU stack из Mach-O также попадают в окно: interrupt stack
`0x81c94000..0x81c9c000`, exception stack `0x81ca0000..0x81ca4000`.
Это проверяет relocation math и отсутствие пересечений, но не доказывает, что
ABL действительно разместил shim по ожидаемой физической базе.

Критический конфликт: при распространённой гипотезе `ABL base=0x80000000`
stock `ramdisk_addr=0x01000000` указывает примерно на `0x81000000`, внутри
XNU-managed window и рядом с kernel destination. `shim/loader.c` корректно
откажется от такого пересечения; считать payload запускаемым без фактического
ABL ramdisk placement нельзя. `shim/build.sh` также остаётся sweet-only:
Android v2, embedded sweet DTB, framebuffer и UFS.

Дополнительные проверки находятся в `tools/preflight-lavender-layout.py` и
`tools/test-lavender-layout.py`. Без ABL-доказательства preflight сохраняет
`BLOCKED`.

86 MiB достаточно для размещения текущего Mach-O, ADT, boot_args и штатных
XNU stack symbols с большим запасом до `avail_end`. Но это не доказательство
полного XNU startup: pmap bootstrap allocates metadata proportional to
`memSize`, а итоговый запас и runtime allocations требуют собранного XNU и
наблюдаемого handoff. Отдельно остаётся риск dynamic `shared-dma-pool`, если
ABL передаст уже занятые Linux carve-out’ы.

Для снятия BLOCKED нужны конкретные read-only подтверждения: ABL static
analysis для lavender с фактическими kernel/ramdisk destination и DTB pointer,
либо временный shim UART/другой наблюдаемый канал, который распечатает
`x0`, initrd range и PC до перехода в XNU. Header v1 и `kernel_addr=0x8000`
этого не подтверждают.

## Lavender XNU shim

Добавлен отдельный путь `shim/build-lavender-xnu.sh` и файлы
`lavender_start.S`, `lavender_loader.c`, `lavender_console.c`, `lavender.ld`.
Он не включает sweet framebuffer, UFS, GIC, timer или PSCI. UART использует
только подтверждённые offsets UARTDM и gated TX polling; clock/pinctrl не
трогаются. Если UART clock/pins не подготовлены ABL, логов не будет.

Loader проверяет magic/version/границы payload, segment table, каждый source и
destination range, lavender memory contract, DTB totalsize, DTB↔ramdisk
пересечение, ramdisk↔XNU window пересечение и запас под ADT/boot_args. После
подготовки `boot_args` он сохраняет MMU/cache-off handoff и передаёт управление
XNU `entry_pa` с физическим `boot_args` в `x0`; bootstrap MMU настраивает
`start_first_cpu` XNU, а не shim.

Локально собраны компоненты: ARM64 Image (`36 KiB`, включая zero-filled
ранний stack), ELF shim и payload (`15.7 MiB`). Android wrapper v1 намеренно не создаётся: stock ramdisk
гипотеза `base+0x01000000` пересекает XNU-managed window, а фактический ABL
base/ramdisk/DTB placement не подтверждён.

USB как канал ранней диагностики не реализован. Найденные USB-патчи содержат
только sweet-подтверждённые DWC3/QUSB2/QSCRATCH адреса и не могут переноситься
на lavender. До отдельной проверки lavender USB controller/clock/pinctrl
единственный предусмотренный канал shim — UART; fallback без UART не заявлен.

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
- В актуальном AOSP пустой входной файл приводит к `ramdisk_size=0` и
  `ramdisk_addr=0`, но это только поведение генератора; описание v1 всё равно
  требует ненулевой ramdisk:
  [mkbootimg.py](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/main/mkbootimg.py),
  [bootimg.h](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/main/include/bootimg/bootimg.h).
- Qualcomm LK `aboot.c` в открытой реализации вызывает `boot_linux()` с
  `hdr->kernel_addr`, `hdr->ramdisk_addr` и `hdr->tags_addr`; это подтверждает
  прямую семантику header, но не доказывает поведение закрытого lavender ABL:
  [aboot.c](https://github.com/tsgan/qualcomm/blob/master/lk/app/aboot/aboot.c).
- ARM64 Linux boot protocol ожидает DTB в `x0`, `x1..x3 = 0`, EL1/EL2 и MMU
  off; diagnostic shim теперь печатает все исходные `x0..x2`, чтобы проверить
  фактический ABL handoff:
  [Linux arm64 booting](https://kernel.org/doc/html/v5.17/arm64/booting.html).

## ABL lavender: результат поиска и границы доказательства

### Целевой статический анализ локального `abl.elf`

Добавлен воспроизводимый bounded-анализатор
`tools/analyze-lavender-abl.py`. Для локального файла он подтверждает:

```
ELF32 ARM ET_EXEC, entry=0x9fa00000
PT_LOAD file 0x3000..0x25000, paddr 0x9fa00000..0x9fa22000, RWE
FV signature at 0x3028, FV start 0x3000, length 0x22000, header 0x48
FFS type 0x0b (FV_IMAGE)
```

У вложенного FFS первый section — стандартный GUID-defined type `0x02`, с
`data_offset=0x18` и vendor-defined payload. Внутри этого payload нет
доступного PE/TE/обычного ARM-кода: ELF не содержит section headers и
символов, а в load payload не найдены `ANDROID!`, FDT magic `d00dfeed` или
ARM64 Image magic. Единственное совпадение с little-endian `0x01000000`
находится внутри контейнерного заголовка и не является доказательством
использования `ramdisk_addr`.

Следовательно, этот конкретный файл не позволяет доказать ни один из
интересующих Android handoff-вопросов: обработку `ramdisk_size=0`, вычисление
физического адреса ARM64 kernel, использование `kernel_addr`/`ramdisk_addr`/
`tags_addr`, источник DTB, регистры передачи DTB или дополнительные проверки
shim. Установлен только адрес размещения и entry самого ABL (`0x9fa00000`),
что не связано с адресом kernel.

Это граница статического доказательства, а не утверждение, что ABL не
поддерживает нужный формат: payload, вероятно, содержит vendor-defined или
упакованный слой, но его алгоритм упаковки/ключи/внутренний loader отсутствуют
в recovery-артефакте. Для снятия блокера нужен matching fastboot ABL с
доступным LinuxLoader/PE или symbols, либо контролируемый read-only запуск с
наблюдением ABL-лога и ранних регистров; новый boot image для этого шага не
создавался.

### Сравнение stock v1 и диагностического образа после временного запуска

`backup/lavender-boot.img` содержит gzip-сжатый kernel, за которым внутри
`kernel_size` следуют два валидных concatenated FDT blob. Первый начинается с
file offset `0x95ab2e` и имеет `totalsize=0x759d9`, второй идёт сразу после
него и имеет `totalsize=0x7d819`. В v1 header при этом `recovery_dtbo_size=0`;
отдельного `dtb_addr` нет.

Диагностический образ из `578e595` содержит только ARM64 Image и не имеет ни
одного `d00dfeed` после kernel header. Поэтому сохранение fastboot совместимо
как минимум с двумя гипотезами: ABL отверг нулевой ramdisk или ABL/следующий
этап не смог найти требуемый appended DTB. `Booting OKAY` от fastboot означает
успешную передачу/принятие команды протоколом; это не подтверждение перехода
ABL к ARM64 Image. Возврат USB fastboot после команды усиливает гипотезу
отказа/раннего возврата, но сам по себе не различает причины.

Один следующий диагностический эксперимент без UART: собрать ровно один
кандидат, сохранив тот же shim и v1 header, но добавить в kernel payload
проверенный stock DTB-хвост с корректным appended FDT layout и оставить другие
поля неизменными. Наблюдаемый результат — USB fastboot должен исчезнуть на
время перехода shim; если он сразу остаётся доступным, это указывает на отказ
до перехода или несовместимость нулевого ramdisk. Эксперимент пока не
выполнялся и не доказывает успешность shim без дополнительного канала.

### Экспериментальный v1 без ramdisk

#### DTB-only candidate

Собран отдельный кандидат
`shim/out/lavender-diag-dtb-noramdisk/lavender-diag-dtb-boot-noramdisk.img`:
raw ARM64 Image shim плюс два stock FDT подряд, при `ramdisk_size=0`. Размеры
FDT: `481753` и `514073` байта; SHA-256 соответственно
`1ada82bafb433f6369cd50fca6763b908881f618c8216d1a0325e4120e11f41d` и
`aa106624b6d313dcb8b75a558d81b54814a7887fe2fe86921f2d455b11154019`. Полный
kernel payload: `1014210` байт; boot image: `1019904` байта; SHA-256 boot:
`f1b65bc2205019ec99c87d3b3d4e641feb77473f092fe1e761f3d8895416bccb`.

`tools/check-lavender-diag-dtb.py` проверяет точное совпадение appended bytes
со stock, порядок и totalsize обоих FDT, структуру `/struct`/`/strings`, v1
header, нулевой ramdisk, 64 MiB boot limit и гипотетическое размещение
`0x80008000..0x800ff9c2` внутри проверенного раннего окна. Последний адрес —
только арифметическая гипотеза; ABL base не подтверждён.

Статически raw ARM64 Image распознаётся как валидный Linux Image, но из
доступных данных нельзя установить, принимает ли закрытый ABL именно raw
payload с appended FDT или требует gzip-обёртку/собственный DTB handoff.
Кандидат подготовлен для одного будущего эксперимента, но не запускался.

#### Stock-like gzip + DTB + ramdisk candidate

Подготовлен отдельный
`shim/out/lavender-diag-stocklike/lavender-diag-stocklike-boot.img`. В нём
raw shim сжат gzip, после gzip сохранены оба оригинальных FDT, а ramdisk
скопирован побайтно из stock. Header v1, page size, `kernel_addr=0x8000`,
`ramdisk_addr=0x1000000`, `tags_addr=0x100`, `os_version` и cmdline совпадают
со stock.

Результаты:

```
boot size:       1683456
kernel_size:      996479
gzip stream:         653
ramdisk_size:      676352
SHA256 boot:      4e1911686c721abc18210e39a9a4ce0bb531c58fbd70317e9aad41e665a6cead
SHA256 kernel:    f0af67c5f9ca230db830f0423d161db1ced478ebd2936033f62a2cbf27a178c9
SHA256 ramdisk:   79dc913a3e05b519c1b231014b03aa1ddf5a16ebeef908f8604c37fcfd9e2c1f
```

Проверены gzip integrity/raw Image header, точное DTB-содержимое и порядок,
ramdisk equality, header/cmdline, boot-размер и fixed-reserved intersections.
При явной гипотезе ABL base `0x80000000` shim занимает
`0x80008000..0x800fb47f`, ramdisk — `0x81000000..0x810a5200`; они не
пересекаются. Эти диапазоны также не пересекаются с известным ABL load
диапазоном `0x9fa00000..0x9fa22000` или fixed reserved-memory. Поэтому для
shim-only диагностики memory preflight проходит. Отдельное ограничение:
ramdisk находится внутри будущего XNU-managed окна; это блокирует XNU-путь,
но не является блокером для этого shim-only образа. Абсолютный ABL base и
динамические ABL buffers всё ещё не доказаны.

Добавлен отдельный `shim/build-lavender-diag-noramdisk.sh`. Он создаёт
структурный кандидат через `mkbootimg --header_version 1 --ramdisk /dev/null`.
Локальный результат имеет размер 24576 байт, `ramdisk_size=0`,
`ramdisk_addr=0`, страницу 4096, `kernel_addr=0x8000` и укладывается в
подтверждённый 64 MiB boot-раздел. `tools/check-lavender-bootv1-noramdisk.py`
проверяет ARM64 Image header, `image_size`, page-aligned layout, отсутствие
второго этапа/recovery-DTBO, границы payload и совпадение подтверждённых полей
стокового v1.

Статус намеренно `BLOCKED`: AOSP прямо называет kernel и ramdisk обязательными
элементами v1 с ненулевым размером. Открытый Qualcomm LK пропускает чтение при
нулевом размере, но это не доказывает поведение закрытого ABL Redmi Note 7.
Кроме того, v1 не содержит полей `dtb_size`/`dtb_addr`; DTB должен быть
передан отдельным legacy/appended или ABL handoff-механизмом. Для lavender не
подтверждено, будет ли DTB в `x0`, `tags_addr` или сформирован ABL отдельно.
Нулевой ramdisk не устраняет этот блокер и не является разрешением на запуск.

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

### Первый XNU/ADT профиль lavender

Добавлен `mkadt.py --profile lavender`. Он не меняет профиль sweet и содержит
только подтверждённые по `candidate-2.dts` узлы: 8 CPU с MPIDR
`0..3,0x100..0x103`, GICD/GICR, UARTDM и eMMC SDHCI/CMDQ. RAM описана двумя
диапазонами `0x80000000..0xffffffff` и `0x100000000..0x17e4bffff`; это описание
карты памяти, а не разрешение размещать XNU в произвольном адресе. В lavender
ADT намеренно нет framebuffer, UFS, `/pram` и synthetic Apple `/product`.

Добавлен XNU patch `0082-lavender-board-profile.patch`: отдельный machine
config `LAVENDER`, отдельный рабочий symlink `MASTER.arm64.lavender` (сейчас он
совместно наследует базовую конфигурацию sweet), matcher
`xiaomi,lavender`/`arm,armv8` и допустимая MPIDR-топология Snapdragon 660.
Идентичность target/product берётся из ADT; методы, удалённые патчем 0059,
не дублируются.
Существующая реализация SWEET временно используется как compile-time каркас,
но framebuffer bootstrap/mapping/panic-console из патчей 0010/0012 явно
отключены для `LAVENDER`; таким образом подтверждённый адрес sweet
`0x9c000000` не исполняется на lavender. Это не означает, что остальные
sweet-драйверы уже являются lavender-драйверами: eMMC, UART clocks/pinctrl,
PSCI и timer требуют отдельного bring-up.

Добавлен `tools/test-lavender-adt.py` — проверяет аппаратные адреса,
топологию, RAM ranges, отсутствие sweet framebuffer/UFS nodes и наличие
lavender guard в раннем XNU-пути.

После ошибки CI `Unsupported CURRENT_MACHINE_CONFIG LAVENDER` исправлен
повреждённый hunk 0082: теперь `MakeInc.def` действительно получает
`LAVENDER` в `SUPPORTED_ARM64_MACHINE_CONFIGS` и `MACHINE_FLAGS`. В staging
проверках libpthread, BearSSL и HFS добавлен тот же профиль; SWEET остаётся
допустимым значением. Статический тест дополнительно проверяет счётчики всех
unified-diff hunks и корректность symlink patch.

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

Профиль ADT и guard-проверка прошли локально:

```
python3 tools/test-lavender-adt.py
lavender XNU hardware guard test: PASS
lavender ADT profile test: PASS
```

На чистом `xnu-8796.141.3` патч 0082 теперь применяется. В изолированной
проверке без staging-скриптов ожидаемо не применяются только 0031 и 0041,
поскольку они требуют предварительно созданный `bsd/sweet_hfs`; сам 0082
применяется, список MakeInc содержит LAVENDER, а symlink master разрешается в
`MASTER.arm64.sweet`.

Генерация sweet без `--profile` также сохранена и проверяется отдельно.
Полная сборка XNU на текущем Linux-хосте невозможна: в рабочем окружении нет
Xcode/macOS SDK, Kernel Development Kit и `iig`; workflow
`.github/workflows/xnu.yml` рассчитан на macOS GitHub runner. Поэтому патч
0082 прошёл только статические проверки и ещё не имеет результата clang/XNU
компиляции. Для CI надо запускать workflow с `machine_config=LAVENDER`, не
меняя default `SWEET`.

## Разбор падения CI 2026-10-27

Архив `logs_109729891426.zip` относится к commit `e57e910`. Preflight,
применение всех 82 numbered-патчей и компиляция прошли до финальной
линковки `kernel.development.lavender`.

Фатальная ошибка была:

```
Undefined symbols for architecture arm64:
  _sweet_log_append, referenced from serial_console.o
```

Реализация `sweet_log_append` находится в `bsd/dev/sweet_ufs.c`, который
защищён `ARM64_BOARD_CONFIG_SWEET`; включать этот UFS-код в lavender ради
символа нельзя, поскольку подтверждённое хранилище lavender — eMMC.
Патчи 0047 и 0067 исправлены: persistent UFS-log остаётся SWEET-only,
а общий lavender console mute сохраняется. Добавлены статические проверки
этих guard-условий.

Свежая последовательная replay-проверка на `xnu-8796.141.3` применяет все
не-staged проектные патчи до 0082; ожидаемо пропущены только 0031 и 0041,
которым нужен staging HFS. Локальные preflight, machine-config,
`validate-repo.py` и `git diff --check` проходят. Следующий CI должен
проверить линковку уже без ссылки на `sweet_log_append` в lavender.

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
