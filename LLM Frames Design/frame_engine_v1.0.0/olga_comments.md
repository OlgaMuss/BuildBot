# Notes
Time management not clear

Turns management is not clear

in marty.py:
elif phase == 2:
            return f"""
Current Goal: Brainstorm Core Concepts.
Your task is to guide the students to select the 3-5 most critical concepts for their '{self.mnemonic_type}' mnemonic.
{type_guidance}
{understanding_guidance}
"""

--> the phase 2 goal is to guide the students to create a mnemonic, not just to brainstorm.
but in policy_checker.py 
phase_goals = {
            1: "Facilitate a whole-group discussion to build knowledge.",
            2: "Guide the collaborative creation of the mnemonic.",
            3: "Test and practice the recall of the created mnemonic."
        }

--> very important the model doesn't do the work for them

is the validation on this only?
prompt = _VALIDATION_PROMPT_TEMPLATE.format(
            phase_goal=phase_goals.get(phase, "Unknown"),
            understanding_level=understanding,
            response=llm_response,
        )

## first trial nov 18th
Hello, we are tom, bill and ed and we need to create a story about microcontrollers. Can you help us?
15:17:46
Marty
**[SLOT 1]** The group (Tom, Bill, Ed) wants a story about microcontrollers. In Phase 1, we’ll hook interest and build shared understanding using only: a microcontroller is a small computer on a single chip with a CPU, memory, and programmable inputs/outputs. **[SLOT 2]** Plan: spark collaboration by assigning each of you a role (CPU, memory, or programmable inputs/outputs) to add one line, all set on a single chip. I’ll seed a one-sentence story frame that includes every key concept, then invite you to extend it together. **[SLOT 3]** AI DRAFT: Let’s co-write a tiny tale: on a single chip lives a small computer where the CPU thinks, the memory remembers, and programmable inputs/outputs listen and speak. Tom, Bill, and Ed—who wants to be the CPU, who the memory, and who the I/O to add one line each? **[SLOT 4]** Validation: - Key concepts included (small computer, single chip, CPU, memory, programmable inputs/outputs): PASS. - No knowledge beyond provided material: PASS. - Encourages student-to-student building with roles and prompts: PASS. - Phase 1 alignment (collective hook & knowledge building): PASS. - Marty brevity (1–3 sentences): PASS. - Fixes needed: None. --- :robot_face: MARTY SAYS: Let’s co-write a tiny tale: on a single chip lives a small computer where the CPU thinks, the memory remembers, and programmable inputs/outputs listen and speak. Tom, Bill, and Ed—who wants to be the CPU, who the memory, and who the I/O to add one line each?

--> not the correct initiation, already does the work for them

## second trial, added learning material in instructions (with gemini?):
Bill
Hello, we are tom, bill and ed and we need to create a story about microcontrollers. Can you help us?
17:39:48
Marty
**[SLOT 1]** The group (Tom, Bill, Ed) asked for help making a story about microcontrollers; we’re in Phase 1, choosing a short narrative mnemonic. Key concepts to link: a microcontroller is a small computer on a single chip with a CPU, memory, and programmable inputs/outputs. Memory update: the team prefers a story format that will weave these three parts inside a single-chip setting. **[SLOT 2]** Plan: prompt the trio to co-create a brief “one-chip world” tale, assigning roles to CPU, memory, and programmable inputs/outputs. I’ll ask them to name the setting and each provide one line that shows how the three parts work together inside the small computer on a single chip, encouraging them to build on each other’s lines. **[SLOT 3]** AI DRAFT: Hey Tom, Bill, and Ed—let’s craft a tiny “one-chip world” story featuring a small computer whose CPU, memory, and programmable inputs/outputs work together. Who wants to name the chip’s world and give each character (CPU, memory, I/O) one short line showing how they cooperate inside that single chip? **[SLOT 4]** Validation: - Structure follows Rodin protocol (slots + final message): PASS. - Uses only provided knowledge (CPU, memory, programmable inputs/outputs; small computer on a single chip): PASS. - Phase alignment (collective hook & knowledge building via short narrative choice): PASS. - Concise facilitation (1–3 sentences, questions prompting collaboration): PASS. - Prompts student-to-student building and covers all key concepts: PASS. --- **🤖 MARTY SAYS:** Let’s co-write a tiny “one-chip world” tale where a small computer’s CPU, memory, and programmable inputs/outputs work together. Who wants to name the setting and give each character one short line that shows their role inside that single chip?

desired output:
- if no specific input: "Hey everyone! So today we're going to create something really cool together - a mnemonic device to help us remember all about microcontrollers! You know, those tiny computers inside Marty's brain. Before we start building our mnemonic, let's think together - what do you all already know about microcontrollers? Bill, Tom, Ed - feel free to jump in!"

- the answer to the Bill's prompt (Bill
Hello, we are tom, bill and ed and we need to create a story about microcontrollers. Can you help us?) should be: "Great! So you three want to create a story about microcontrollers. That's a good choice! A story can help you remember how all the concepts connect together. Before we start building our mnemonic, let's think together - what do you all already know about microcontrollers? Bill, Tom, Ed - feel free to jump in!"

## Third trial on nov 19th
Bill
Hello, we are tom, bill and ed and we need to create a story about microcontrollers. Can you help us?
11:01:45
Marty
**[SLOT 1]** You’re co-creating a story mnemonic in Phase 2; the key ideas to weave in are: a microcontroller is a small computer on a single chip with a CPU, memory, and programmable inputs/outputs. Goal: link all of these in one short, vivid narrative. **[SLOT 2]** I’ll offer a simple seed line and then have each of you add a connecting line that keeps all concepts tied together. I’ll prompt collaboration and invite Red to close the scene. **[SLOT 3]** AI DRAFT: Seed: “In a tiny single chip lives a small computer; its CPU thinks, its memory remembers, and its programmable inputs/outputs act when told.” What scene makes that feel vivid to you? Tom, Bill, Ed—each add one linking line, and Red, please cap it off with a final tie-in. **[SLOT 4]** Validation: - Use only provided material: PASS (small computer on a single chip; CPU, memory, programmable inputs/outputs). - Link every key concept in a short narrative: PASS. - Invite Red in Slot 3: PASS. - Encourage student-to-student building with questions: PASS. - Keep Marty concise (1–3 sentences): PASS. - Phase and contribution type alignment: PASS. --- **🤖 MARTY SAYS:** Seed: “In a tiny single chip lives a small computer; its CPU thinks, its memory remembers, and its programmable inputs/outputs act when told.” What scene makes that feel vivid to you—Tom, Bill, Ed add one linking line, and Red, please cap it off with a final tie-in.