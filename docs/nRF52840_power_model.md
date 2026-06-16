# System Hardware Design

This section describes the hardware platform of the battery-free neighbor-discovery
node, the rationale behind its supply-voltage operating thresholds, and the
power-mode selection that governs its behavior under intermittent, ambient-energy
operation. The design centers on a single microcontroller unit (MCU) that performs
radio-based advertisement, augmented by a dedicated, ultra-low-power external circuit
for the energy-dominant scanning phase. The section concludes with a consolidated
table specifying the power consumption of each operating mode.

## 1. Platform Overview

The node is built around the Nordic Semiconductor nRF52840, a 32-bit Arm Cortex-M4F
system-on-chip clocked at 64 MHz with an integrated 2.4 GHz multiprotocol radio
supporting Bluetooth Low Energy (BLE), IEEE 802.15.4, and proprietary modes. The
nRF52840 is selected because it is a widely adopted, well-characterized platform for
battery-free wireless networking and exposes the fine-grained power-management states
required for intermittent operation. Its salient characteristics are summarized in
Table 1.

**Table 1. nRF52840 characteristics relevant to a battery-free node.**

| Feature | Value | Relevance to the node design |
|---|---|---|
| CPU | Cortex-M4F @ 64 MHz | High throughput per active interval; comparatively high active current (Γëê 52 ┬╡A/MHz), so active time must be minimized. |
| Memory | 1 MB flash + 256 KB SRAM | Firmware resides in flash; working state resides in volatile SRAM, retained only while the device remains powered (System ON) or in a retention state. |
| Radio | 2.4 GHz; Γëê 4.6 mA RX, Γëê 4.8 mA TX @ 0 dBm (DC/DC, 3 V) | Determines the energy of an advertisement / active-discovery burst. |
| Supply range | 1.7ΓÇô3.6 V (normal); up to 5.5 V (high-voltage mode) | Defines the hard lower and upper bounds of the operating window. |
| Regulators | Selectable DC/DC (buck) or LDO | DC/DC mode roughly halves active and radio current; assumed enabled throughout. |
| System ON idle (RTC + full RAM retention) | Γëê 1.5 ┬╡A @ 3 V (DC/DC) | Establishes the sleep-mode current floor with a running real-time clock. |
| System OFF (no retention) | Γëê 0.4 ┬╡A | Deep sleep; loses SRAM and stops the RTC, and is therefore unusable for a periodic wake-up. |
| Real-time clock (RTC) | 32.768 kHz low-frequency clock | Source of the 1 kHz wake-up tick that paces the protocol state machine. |

A defining property of this platform is that working state is held in **volatile
SRAM**. State persists only while the device remains in System ON (CPU idle is
permissible) or in System OFF with explicit RAM retention; a genuine power loss, in
which the supply rail collapses below the brown-out reset voltage, erases SRAM. A
brown-out is therefore a true loss of progress, and the node must rebuild its protocol
state from flash defaults upon the next charge cycle. This property directly motivates
the conservative hysteresis band described in Section 2: because every brown-out is
costly, each activation must be guaranteed to perform useful work.

## 2. Supply-Voltage Operating Thresholds

The node is powered from a storage capacitor rather than a regulated rail, so its
behavior is governed by three voltage thresholds applied to the capacitor: a turn-on
threshold $V_\text{on}$, a turn-off (brown-out) threshold $V_\text{off}$, and an upper
clamp $V_\text{max}$. The energy stored on a capacitor $C$ at voltage $V$ follows the
standard relation

$$E = \tfrac{1}{2} C V^2 \quad\Longleftrightarrow\quad V = \sqrt{\dfrac{2E}{C}},$$

which the node uses to translate between its stored energy and its instantaneous rail
voltage. The chosen operating point uses a storage capacitor with an effective
(voltage-derated) capacitance of 17 ┬╡F and $V_\text{off} = 2.4$ V,
$V_\text{on} = 3.0$ V, and $V_\text{max} = 3.3$ V. The 17 ┬╡F figure reflects the
substantial DC-bias derating of the ceramic storage capacitor at the operating rail
voltage relative to its nominal rating; all energy calculations use this effective
value.

**Turn-off threshold $V_\text{off} = 2.4$ V.** The nRF52840 operates down to 1.7 V, so
a 2.4 V floor provides comfortable margin above the brown-out reset voltage and keeps
the radio power amplifier and DC/DC converter within their reliable operating regions.
Because the scan circuit is powered directly from the GPIO at the rail voltage
(Section 4) rather than from a regulated 2.0 V supply, it imposes no additional
lower-bound constraint; the turn-off threshold is therefore set by the MCU and radio
margins alone. The 2.4 V floor also limits the transient rail droop during a radio
burst that could otherwise trigger a premature brown-out.

**Turn-on threshold $V_\text{on} = 3.0$ V.** A hysteresis band between $V_\text{off}$
and $V_\text{on}$ guarantees a minimum stored-energy budget before any work begins, so
the node does not immediately brown out under the first active-mode load. The usable
energy within this band,

$$E_\text{usable} = \tfrac{1}{2}C\left(V_\text{on}^2 - V_\text{off}^2\right)
= \tfrac{1}{2}(17\ \mu\text{F})(3.0^2 - 2.4^2) \approx 27.5\ \mu\text{J},$$

is sized so that at least one full advertisement and associated housekeeping fit within
a single activation. Because state on this platform is volatile, this guarantee is
essential: an activation that browned out before completing useful work would forfeit
all in-SRAM progress.

**Upper clamp $V_\text{max} = 3.3$ V.** The clamp sits safely below the 3.6 V
normal-mode maximum, modeling a practical harvester or shunt limit. Energy harvested
beyond this point is discarded. Clamping at 3.3 V keeps the rail within the DC/DC
converter's most efficient band.

A deep-discharge configuration (e.g. $V_\text{off} = 1.8$ V) is rejected because, with
the voltage-derated 17 ┬╡F storage capacitor, the energy available in the band scales
with $V^2$, and the usable budget at a lower operating point becomes too small to
reliably complete a full advertisement. The comparatively expensive active mode of the
Cortex-M4F (Section 3) benefits from the additional margin that the 2.4 V floor
preserves.

## 3. Power-Mode Selection

The nRF52840 provides two top-level power modes, System ON and System OFF, with
sub-states inside System ON. The node maps its activities onto these modes as follows.

**Active mode (System ON, CPU and radio running).** This mode is used whenever the CPU
or radio performs work: transmitting an advertisement, configuring or reading the scan
circuit, or actively discharging the capacitor. Executing from flash at 64 MHz with the
DC/DC converter enabled draws approximately 3.3 mA at 3 V, giving an active power of

$$P_\text{active} = 3.3\ \text{mA} \times 3\ \text{V} = 9.9\ \text{mW},$$

with the radio adding Γëê 4.6 mA (RX) or Γëê 4.8 mA (TX) at 0 dBm during a discovery burst.
This active power is roughly an order of magnitude above that of comparable
low-current MCUs, and it is the dominant theme of the design: active time must be kept
short, which is precisely why the listening phase is offloaded to the dedicated
external scan circuit of Section 4.

**Sleep mode (System ON idle).** Between protocol ticks the node enters System ON idle,
in which the CPU is clock-gated via a wait-for-interrupt instruction while the RTC
continues to run and the full SRAM is retained. This is the central power-mode decision
and is dictated by two requirements: the protocol state machine must advance on a
periodic 1 kHz tick (a wake-up every 1 ms), and it must preserve its volatile,
RAM-resident state between ticks. These requirements rule out the deeper modes, as
summarized in Table 2.

**Table 2. Suitability of nRF52840 low-power modes for a periodic-tick, stateful node.**

| Mode | RTC running | SRAM retained | Wake behavior | Suitable |
|---|---|---|---|---|
| System OFF (no retention) | No | No | Reset / cold boot | No ΓÇö cannot maintain a 1 kHz tick; loses all state each wake. |
| System OFF + RAM retention | No | Yes | Wake on GPIO/NFC/reset only | No ΓÇö RTC unavailable, so no periodic tick. |
| System ON idle (CPU wait-for-interrupt) | Yes | Yes | Γëê ┬╡s wake on RTC interrupt | Yes ΓÇö CPU clock-gated, RTC alive, full SRAM retained. |

System ON idle is therefore the correct sleep mode. System OFF would suit only nodes
that sleep for long, event-driven intervals and tolerate a cold boot, which is the
opposite of the periodic, stateful operation required here.

## 4. Dedicated Scan Circuit

In a conventional design, the listening (scan) phase would energize the main 2.4 GHz
radio in receive mode, drawing Γëê 4.6 mA and consuming Γëê 13.8 ┬╡J for a 1 ms listen
window ΓÇö comparable to an entire advertisement. Because a battery-free node spends a
large fraction of its active budget listening, this design instead delegates scanning
to a dedicated external circuit specified at

$$P_\text{scan} = 7.51\ \mu\text{W at } V_\text{scan} = 2.0\ \text{V}
\;\Longrightarrow\; I_\text{scan} = \frac{7.51\ \mu\text{W}}{2.0\ \text{V}} = 3.755\ \mu\text{A}.$$

The MCU power-gates this circuit: a single GPIO pin both enables it and provides its
supply directly at the node's rail voltage. The 3.755 ┬╡A demand is far below the
nRF52840 GPIO source capability (Γëê 0.5 mA at standard drive, several mA at high drive),
so one pin can power the circuit directly.

**Powering the circuit at the rail voltage.** Rather than introducing a dedicated 2.0 V
regulator and the attendant dropout and conversion-loss complications, the scan circuit
is powered directly from the GPIO at the node's nominal 3 V rail. Treating the circuit's
draw as current-defined (3.755 ┬╡A, from its 7.51 ┬╡W / 2.0 V rating), the power consumed
at 3 V is

$$P_\text{scan} = I_\text{scan} \times 3\ \text{V} = 3.755\ \mu\text{A} \times 3\ \text{V}
= 11.27\ \mu\text{W},$$

and energy accounting uses this 3 V figure. Driving the circuit directly from the rail
also removes any regulator-dropout constraint on $V_\text{off}$, so the turn-off
threshold is governed solely by the MCU and radio margins of Section 2.

**Power mode during a scan.** A scan occupies a single 1 ms protocol slot, during which
the MCU's involvement is minimal: it wakes from System ON idle and drives the GPIO high
to enable the scan circuit (a few microseconds of active time), returns to System ON
idle for the listening window while the scan circuit operates autonomously and signals
a detection by interrupt, and finally reads the result and de-asserts the GPIO. The MCU
thus remains in the same low-power System ON idle state as during an ordinary sleep
tick, plus a brief active setup, plus the energy delivered to the scan circuit. The
resulting per-scan energy is

$$E_\text{scan} = P_\text{scan}\,t_\text{slot} + P_\text{idle}\,t_\text{slot}
+ P_\text{active}\,t_\text{setup},$$

with $t_\text{slot} = 1$ ms, $P_\text{scan} = 11.27\ \mu\text{W}$,
$P_\text{idle} = 4.5\ \mu\text{W}$, $P_\text{active} = 9.9\ \text{mW}$, and
$t_\text{setup} \approx 3\ \mu\text{s}$, giving

$$E_\text{scan} \approx 11.27\ \text{nJ} + 4.5\ \text{nJ} + 29.7\ \text{nJ}
\approx 45\ \text{nJ}.$$

A scan performed through the dedicated circuit is thus roughly 300 times cheaper than a
listen performed with the main radio in receive mode (Γëê 13.8 ┬╡J). Notably, the residual
cost is dominated not by the scan circuit but by the brief CPU setup, so further savings
accrue from minimizing CPU wake time rather than from the sensor itself.

## 5. Active-Burst Energy Figures

**Advertisement / active-discovery burst.** The active-discovery sequence on the
nRF52840 (2 Mbit mode) is a fixed 976 ┬╡s burst comprising a leading beacon transmission,
a receive turnaround and listening window, and a trailing acknowledgement
transmission. Modeling the radio as running autonomously while the CPU is largely idle,
and adding a short CPU setup, yields the breakdown in Table 3.

**Table 3. Energy breakdown of a single advertisement / active-discovery burst (0 dBm, DC/DC, 3 V).**

| Phase | Current | Duration | Energy |
|---|---|---|---|
| Transmit (48 + 48 ┬╡s) | 4.8 mA | 96 ┬╡s | 1.38 ┬╡J |
| Receive (40 + 800 + 40 ┬╡s) | 4.6 mA | 880 ┬╡s | 12.14 ┬╡J |
| CPU setup / processing | 3.3 mA | Γëê 50 ┬╡s | 0.50 ┬╡J |
| **Total** | ΓÇö | **976 ┬╡s** | **Γëê 14.0 ┬╡J** |

A representative advertisement therefore costs approximately 14 ┬╡J at 0 dBm with the
DC/DC converter enabled; higher transmit power or LDO-only operation increases the
transmit and receive terms proportionally.

**Sleep tick.** A pure System ON idle floor (Γëê 1.5 ┬╡A, i.e. 4.5 ┬╡W or 4.5 nJ over a 1 ms
tick) understates the true per-tick cost, because every millisecond the CPU briefly
leaves idle to service the RTC interrupt, advance the slot counter, evaluate the
protocol decision, and return to idle. Modeling this as a short active interval atop the
idle floor,

$$E_\text{sleep} = P_\text{active}\,t_\text{wake} + P_\text{idle}\,(T - t_\text{wake}),$$

with $t_\text{wake} \approx 1\ \mu\text{s}$ and $T = 1$ ms, gives

$$E_\text{sleep} \approx 9.9\ \text{mW} \times 1\ \mu\text{s}
+ 4.5\ \mu\text{W} \times 997\ \mu\text{s} \approx 14.4\ \text{nJ},$$

corresponding to an average sleep current of Γëê 11 ┬╡A at 3 V. This figure deliberately
captures the wake-up overhead that an idle-current-only estimate would omit.

**Active discharge (busy-wait).** When the node is powered but has no scheduled work, it
keeps the CPU active to drain the capacitor deliberately, mirroring the active
discharging behavior of intermittent discovery firmware. At full 64 MHz operation over a
1 ms slot this costs

$$E_\text{busy} = P_\text{active} \times t_\text{slot}
= 9.9\ \text{mW} \times 1\ \text{ms} = 9.9\ \mu\text{J}.$$

## 6. Summary of Power Consumption by Mode

Table 4 consolidates the operating modes of the node, the corresponding device power
state, the instantaneous power, and the per-slot energy over the 1 ms protocol tick.
Together with the thresholds of Section 2, these figures fully specify the node's
energy behavior.

**Table 4. Power consumption of the nRF52840 node by operating mode (DC/DC, 3 V rail, 1 ms slot).**

| Operating mode | Device power state | Instantaneous power | Energy per 1 ms slot |
|---|---|---|---|
| Sleep (idle hold) | System ON idle (CPU WFI, RTC on, SRAM retained) | Γëê 4.5 ┬╡W floor; Γëê 34 ┬╡W average incl. tick wake | Γëê 34 nJ |
| Scan (listen) | System ON idle + GPIO-powered scan circuit (11.3 ┬╡W @ 3 V) | Γëê 45 ┬╡W effective (incl. CPU setup) | Γëê 45 nJ |
| Advertise (active discovery) | System ON, CPU + radio (TX/RX burst, 976 ┬╡s) | Γëê 14.3 mW during the burst | Γëê 14.0 ┬╡J |
| Active discharge (busy-wait) | System ON, CPU active @ 64 MHz | 9.9 mW | Γëê 9.9 ┬╡J |
| Off (brown-out) | Below $V_\text{off}$; rail collapsed | ΓÇö (SRAM lost, node resets) | ΓÇö |

The standalone scan circuit is the key enabler of this design: by reducing the cost of a
listen from Γëê 13.8 ┬╡J to Γëê 45 nJ, it allows the node to scan hundreds of times per
charge cycle within the Γëê 27.5 ┬╡J usable energy budget, while an advertisement ΓÇö the
energy-dominant operation at Γëê 14 ┬╡J ΓÇö remains affordable within a single activation.
