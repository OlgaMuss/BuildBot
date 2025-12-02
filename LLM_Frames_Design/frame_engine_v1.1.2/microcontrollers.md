cd "/Users/olga/Olga's workspace/ETHZ SBS/Marty project/LLM Frames Design/frame_engine_v1.1.1/code"# Microcontrollers Learning Material

## What is Marty's Brain?

Marty's "Brain" is located on the **Robot Interface Controller (RIC)**. The main component of this brain is a microcontroller called the **ESP32 module**. For programming and control, an **Arduino Nano** was connected to the RIC.

## What is a Microcontroller?

A **microcontroller** (or microcontroller unit) is a small computer on a single integrated circuit. It contains:
- One or more **CPUs** (processor cores)
- **Memory**
- **Programmable input/output peripherals**

Think of it as a tiny, specialized computer that can control things!

## Where Are Microcontrollers Used?

Microcontrollers are hidden behind almost every button press or touchscreen tap in our daily lives. You can find them in:
- **Coffee machines** ☕
- **Automatic doors** 🚪
- **Airbags** 🚗
- **Washing machines** 🧺
- **Microwave ovens** 
- **Remote controls** 📺
- And thousands of other devices!

They're everywhere, quietly making our lives easier.

## How Does a Microcontroller Work?

### Electrical Basics
A microcontroller is, first and foremost, an **electrical device**. That means:
- It needs to be connected to a **positive** terminal
- It needs to be connected to a **negative** terminal
- Just like a battery!

Without this connection, the microcontroller cannot function.

### Pins: The Microcontroller's Connectors

To control other devices, a microcontroller uses many connectors called **pins**. Here's how they work:

- A microcontroller can **output 3 volts (3V)** on its pins
- It can turn this voltage **on** or **off** for individual pins
- It can control one pin, two pins, three pins, or many pins at once
- Each pin can be controlled independently

### HIGH and LOW States

When we talk about pins, we use two important terms:
- **HIGH**: When a pin is turned **on** (voltage is flowing)
- **LOW**: When a pin is turned **off** (no voltage)

### Controlled by Programs

This switching between HIGH and LOW doesn't happen randomly! It's controlled by a **program**. For Marty, we can write programs using:
- **Blockly** (a visual programming language that's easy to learn)
- Under the hood, microcontrollers use a programming language called **C++**

## Key Concepts Summary

1. **Location**: Marty's brain (microcontroller) is in the RIC
2. **Name**: The microcontroller is an ESP32 module
3. **Definition**: A microcontroller is a small computer on a single chip
4. **Ubiquity**: They're in everyday devices all around us
5. **Power**: Needs positive and negative connections to work
6. **Control**: Uses pins to control other devices with 3V signals
7. **States**: Pins can be HIGH (on) or LOW (off)
8. **Programming**: Controlled by programs written in C++ (or Blockly for Marty)

## Fun Facts

- The ESP32 is powerful enough to connect to WiFi and Bluetooth!
- A single microcontroller can control multiple motors, sensors, and LEDs at the same time
- The programs that run on microcontrollers are usually quite small compared to apps on your phone
- Microcontrollers are designed to be energy-efficient so they can run for a long time

## Thinking Questions

- Why might it be useful that pins can be controlled independently?
- What happens if we switch a pin between HIGH and LOW very quickly?
- Can you think of a device in your home that probably has a microcontroller?
- How is a microcontroller different from the processor in a smartphone or computer?

In german:
Lerninhalte zu Mikrocontrollern:
- Martys „Gehirn“ befindet sich auf dem Robot Interface Controller (RIC). Seine Hauptkomponente ist ein Mikrocontroller, das sogenannte ESP32-Modul.
- Ein Mikrocontroller oder eine Mikrocontroller-Einheit ist ein kleiner Computer auf einem einzigen integrierten Schaltkreis, der eine oder mehrere CPUs (Prozessorkerne) sowie Speicher und programmierbare Ein-/Ausgabe-Peripheriegeräte enthält.
- Sie stecken hinter fast jedem Tastendruck oder Touchscreen in unserem Alltag, beispielsweise in Maschinen, automatischen Türen und Airbags.
- Ein Mikrocontroller ist in erster Linie ein elektrisches Gerät. Das bedeutet, dass er an einen Plus- und einen Minuspol angeschlossen werden muss, um zu funktionieren.
- Um andere Geräte zu steuern, kann ein Mikrocontroller an seinen zahlreichen Anschlüssen, den sogenannten Pins, eine Spannung von 3 V ausgeben. Er kann diese Spannung für einen Pin, zwei oder drei Pins einschalten, für einzelne Pins ausschalten oder sogar für viele Pins gleichzeitig aktivieren. Wenn ein Pin eingeschaltet ist, sagen wir, er ist „HIGH“; wenn er ausgeschaltet ist, ist er „LOW“. Dieses Umschalten zwischen „HIGH“ und „LOW“ geschieht nicht zufällig – es wird durch ein Programm gesteuert, wie beispielsweise Blockly für Marty.
- Mikrocontroller verwenden eine Programmiersprache namens C++.
