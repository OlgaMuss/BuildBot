# Week 4: Programming and Sensors + Make it Move + Make it Hear and Speak

## 📋 Overview
**Duration:** 2 hours 15 minutes  
**Theme:** Bringing Marty to Life  
**Storyline Steps:** Make Marty move + Make Marty hear and speak  
**Key Narrative:** "Programming Marty's First Steps - From Assembly to Intelligence"

---

## 🎯 Learning Objectives

### Primary Goals - Basic Programming Concepts
- **Functions:** Understand how functions work as reusable code blocks
- **Variables:** Learn to store and manipulate data using variables
- **Parameters:** Understand how to pass information to functions
- **Commands:** Learn basic programming commands and syntax
- **Libraries:** Understand how libraries provide pre-written code
- **Loops:** Master repetition structures (for, while loops)
- **Conditions:** Learn if-then logic and decision making
- **Data Structures:** Understand how to organize and store data

### Primary Goals - Marty Architecture
- **Marty's Architecture:** Understand Marty's internal structure and components
- **Motors:** Learn how motors transform electric energy into movement using electromagnetic fields
- **Sensors:** Understand how sensors capture environmental information and transmit it
- **Sensor Types:** Learn about different types of sensors and their applications
- **Marty's Sensors:** Understand Marty's 2 specific sensors:
  - **Infrared Sensor:** Reacts to temperature (electromagnetic waves)
  - **Color Sensor:** Reacts to colors (sends blue signal when sees blue, etc.)

### Storyline Goals
- **Storyline Step 2:** Make Marty move - Connect to Marty app, test controller and MartyBlocks
- **Storyline Step 3:** Make Marty hear and speak - Connect to an API using an LLM in MartyBlocks

### Secondary Goals
- Connect programming concepts to AI capabilities
- Develop problem-solving skills through coding
- Build foundation for autonomous operation
- Experience immediate feedback from programming

---

## 📅 Detailed Agenda

### 7:20 - 7:35 (15 minutes) - Programming Fundamentals
**Slide Storyline:** "Learning the Language of Robots"

#### Slide 1: Basic Programming Concepts - The Cooking Metaphor
**Visual Elements:**
- Cooking recipe visualization with ingredients and instructions
- Recipe book representing programming libraries
- Temperature settings representing parameters
- Connection between cooking and robot programming

**Teaching Points:**
- **Functions as Recipes:** Just like a recipe tells you how to make a dish, a function tells Marty how to perform a task
  - Example: "walk_forward()" is like a recipe for walking forward
  - Example: "turn_left()" is like a recipe for turning left
- **Variables as Ingredients:** Ingredients in cooking are like variables in programming
  - Example: speed = 50 (like using 50ml of oil)
  - Example: color = "red" (like using red food coloring)
- **Parameters as Temperatures:** Just like you adjust oven temperature, you adjust function parameters
  - Example: walk_forward(steps=5, speed=100) - like cooking at 200°C for 5 minutes
  - Example: turn_left(angle=90, speed=50) - like turning at medium heat for 90 degrees
- **Commands as Cooking Instructions:** Commands are like specific cooking instructions that tell Marty what to do
  - Example: "cook the chicken at 180°C for 20 minutes" is like "walk forward at speed 100 for 5 steps"
  - Example: "stir the soup gently" is like "turn left slowly at angle 45 degrees"
  - Commands are the basic instructions that tell Marty how to execute the recipe (function)
- **Libraries as Recipe Books:** A library is like a book of recipes - pre-written functions ready to use
  - Example: MartyBlocks library has ready-made movement functions
  - Example: Just like you don't need to invent how to make bread, you don't need to invent how to make Marty walk
- **MartyBlocks:** Visual programming environment using these concepts, like a visual recipe book

**Discussion Question:** "If Marty's 'walk_forward()' function was a recipe, what ingredients (variables) and temperatures (parameters) would it need?"

#### Slide 2: Control Structures
**Visual Elements:**
- Loop and condition examples
- Data structure visualizations
- Interactive programming demonstrations

**Teaching Points:**
- **Loops:** Repeat actions multiple times
  - For loops: Repeat a specific number of times (e.g., repeat 5 times)
  - While loops: Repeat while a condition is true (e.g., while sensor detects obstacle)
- **Conditions (If-Then):** Make decisions based on sensor data
  - If color sensor sees red, then turn left
  - If infrared sensor detects heat, then stop
- **Data Structures:** Ways to organize information
  - Lists: Store multiple values (e.g., colors = ["red", "blue", "green"])
  - Arrays: Organized data collections

**Discussion Question:** "What conditions might Marty need to check using its sensors?"

### 7:35 - 7:55 (20 minutes) - Marty Architecture and Sensors
**Slide Storyline:** "Understanding Marty's Internal Structure"

#### Slide 3: Marty's Architecture
**Visual Elements:**
- Marty's internal structure diagram
- Component layout visualization
- Motor and sensor placement

**Teaching Points:**
- **Marty's Architecture:** Internal structure and components that make Marty work
- **Motors:** Transform electric energy into movement using electromagnetic fields
  - How motors work: Electric current creates magnetic field, which interacts with permanent magnets to create movement
  - Marty's motors control leg movement, turning, and gestures
- **Central Processing Unit:** Marty's "brain" that processes sensor data and controls motors
- **Power System:** Battery provides electric energy to motors and sensors

**Discussion Question:** "How do you think Marty's motors convert electricity into walking movements?"

#### Slide 4: Marty's Sensors
**Visual Elements:**
- Marty's 2 specific sensors highlighted
- Sensor data flow visualization
- Interactive sensor demonstrations

**Teaching Points:**
- **Sensor Definition:** Devices that capture information about the environment and transmit it
- **Sensor Types:** There are many types of sensors (distance, light, sound, touch, temperature, color)
- **Marty's 2 Sensors:**
  - **Infrared Sensor:** Reacts to temperature changes
    - Uses electromagnetic waves (infrared radiation)
    - Detects heat sources, body temperature, warm objects
    - Example: If infrared sensor detects heat, then stop or turn away
  - **Color Sensor:** Reacts to different colors
    - Sends specific signals based on detected colors
    - Sends blue signal when sees blue, red signal when sees red, etc.
    - Example: If color sensor sees red, then turn left; if sees green, then go straight

**Discussion Question:** "What could Marty do differently when it sees red vs blue vs green?"

### 7:55 - 8:15 (20 minutes) - Storyline Step 2: Make it Move
**Slide Storyline:** "Bringing Marty to Life"

#### Slide 5: Marty App Connection
**Visual Elements:**
- Marty app interface
- Connection process visualization
- Controller testing interface

**Teaching Points:**
- **Marty App:** Official application for controlling Marty robot
- **Connection Process:** Bluetooth pairing and communication setup
- **Controller Testing:** Manual control to verify robot functionality
- **Basic Movements:** Forward, backward, turn, dance, gestures
- **Safety Check:** Ensure all movements are safe and controlled

**Activity Setup:**
- Guide students through Marty app installation and setup
- Demonstrate connection process
- Test basic controller functions
- Verify robot responsiveness and safety

#### Slide 6: MartyBlocks Programming
**Visual Elements:**
- MartyBlocks interface
- Programming examples
- Movement block categories

**Teaching Points:**
- **MartyBlocks:** Visual programming environment for Marty
- **Movement Blocks:** Control robot locomotion and gestures
- **Programming Structure:** Sequence, loops, conditions
- **Testing and Debugging:** Run programs and fix issues
- **Creative Programming:** Encourage experimentation and creativity

**Programming Activity:**
- Guide students through MartyBlocks setup
- Demonstrate basic movement programming
- Create simple programs (walk forward, turn, dance)
- Test and debug programs
- Encourage creative movement combinations

### 8:15 - 8:30 (15 minutes) - Break
**Slide Storyline:** "Celebrating Marty's First Movements"

#### Slide 7: Break Reflection
**Visual Elements:**
- Movement celebration
- Programming progress
- Next activity preview

**Teaching Points:**
- **Programming Success:** Students have successfully programmed robot movements
- **Sensor Integration:** Understanding how sensors enable intelligent behavior
- **Creative Expression:** Programming allows for creative robot behaviors
- **Next Activity:** Adding AI capabilities for hearing and speaking

**Reflection Questions:**
1. What was most exciting about programming Marty to move?
2. How do you think sensors will make Marty smarter?
3. What movements would you like to program next?

### 8:30 - 9:15 (45 minutes) - Storyline Step 3: Make it Hear and Speak
**Slide Storyline:** "Adding Intelligence to Marty"

#### Slide 8: AI Integration Introduction
**Visual Elements:**
- AI integration diagram
- LLM connection visualization
- Voice interaction examples

**Teaching Points:**
- **AI Integration:** Connecting Marty to Large Language Models
- **Voice Capabilities:** Speech recognition and text-to-speech
- **LLM Connection:** Using APIs to access AI language models
- **Interactive Communication:** Marty can understand and respond to students
- **Educational Applications:** Tutoring, answering questions, providing explanations

**Discussion Question:** "How do you think Marty will use AI to help with learning?"

#### Slide 9: API Integration
**Visual Elements:**
- API connection diagram
- Data flow visualization
- Security considerations

**Teaching Points:**
- **API Definition:** Application Programming Interface - allows programs to communicate
- **LLM APIs:** Connect to AI language models for natural language processing
- **Data Flow:** Student input → API → AI processing → Response → Marty output
- **Security:** Safe API usage, data protection, appropriate content filtering
- **MartyBlocks Integration:** Visual blocks for API connections

**Activity Setup:**
- Guide students through API setup process
- Demonstrate safe API usage
- Show how to integrate APIs with MartyBlocks
- Test basic voice interaction capabilities

#### Slide 10: Voice Programming
**Visual Elements:**
- Voice programming examples
- Speech recognition visualization
- Text-to-speech examples

**Teaching Points:**
- **Speech Recognition:** Converting spoken words to text
- **Natural Language Processing:** Understanding meaning and intent
- **Text-to-Speech:** Converting text responses to spoken words
- **Conversation Flow:** Listening, understanding, responding appropriately
- **Educational Focus:** Designing helpful learning interactions

**Programming Activity:**
- Guide students through voice programming setup
- Create simple conversation programs
- Test speech recognition and response generation
- Design educational interaction scenarios
- Debug and improve voice interactions

#### Slide 11: Testing and Refinement
**Visual Elements:**
- Testing checklist
- Improvement strategies
- Quality assurance guidelines

**Teaching Points:**
- **Testing Process:** Verify all functions work correctly
- **User Experience:** Ensure interactions are helpful and engaging
- **Error Handling:** Manage cases where AI doesn't understand or respond appropriately
- **Continuous Improvement:** Iteratively refine and improve interactions
- **Safety Considerations:** Ensure all interactions are appropriate and safe

**Testing Activity:**
- Test voice recognition accuracy
- Verify response appropriateness
- Check for bias or inappropriate content
- Refine interaction design based on testing
- Document successful interaction patterns

### 9:15 - 9:30 (15 minutes) - Integration and Testing
**Slide Storyline:** "Combining Movement and Intelligence"

#### Slide 12: Combined Programming
**Visual Elements:**
- Combined program examples
- Integration flow diagram
- Testing scenarios

**Teaching Points:**
- **Program Integration:** Combining movement and voice capabilities
- **Complex Behaviors:** Marty can move and speak simultaneously
- **Interactive Scenarios:** Responding to voice commands with movement
- **Educational Applications:** Creating engaging learning experiences
- **Creative Possibilities:** Encouraging innovative interaction design

**Integration Activity:**
- Create programs that combine movement and voice
- Design interactive learning scenarios
- Test combined functionality
- Share and demonstrate creative programs
- Document successful integration patterns

### 9:30 - 9:35 (5 minutes) - Assessment and Reflection
**Slide Storyline:** "Reflecting on Marty's New Capabilities"

#### Slide 13: Weekly Learning Reflection
**Visual Elements:**
- Learning objectives checklist
- Capability progression
- Next week preview

**Teaching Points:**
- **Programming Skills:** Visual programming with Blockly and MartyBlocks
- **Sensor Integration:** Understanding and using robot sensors
- **AI Integration:** Connecting Marty to language models
- **Voice Capabilities:** Speech recognition and text-to-speech
- **Combined Functionality:** Movement and intelligence working together

**Reflection Questions:**
1. What was most challenging about programming Marty?
2. How do you think AI makes Marty more helpful?
3. What are you most excited about for next week?

---

## 🎨 Slide Design Storyline

### Visual Theme: "Programming in Action"
- **Color Palette:** Orange (creativity), Blue (technology), Green (success)
- **Typography:** Modern, tech-inspired, clear hierarchy
- **Icons:** Programming, sensors, and AI symbols
- **Layout:** Clean, focused on hands-on programming concepts

### Interactive Elements
- **Hands-on Programming:** Live coding demonstrations
- **Sensor Testing:** Interactive sensor demonstrations
- **Voice Testing:** Real-time voice interaction testing
- **Progress Tracking:** Programming and capability progress

### Accessibility Features
- **Clear Contrast:** High contrast for readability
- **Readable Fonts:** Large, clear typography
- **Visual Hierarchy:** Important programming concepts emphasized
- **Multilingual Support:** English and German versions

---

## 📚 Teaching Materials

### Required Resources
- **Week 4 Teaching Materials:** [Link to be added]
- **Robotical Learning Portal:** [Marty v2 Learning Resources](https://learn.robotical.io/lessons/martyVersions/2)
- **MartyBlocks Lessons:** 58 Scratch-based programming lessons
- **Sensor-Specific Lessons:** 
  - Color Sensor (17 lessons)
  - Infrared (IR) Sensor (8 lessons)
  - Light Sensors (4 lessons)
  - Distance Sensors (3 lessons)
- **Programming Concepts:** Functions, variables, loops, conditions tutorials
- **Marty v2 User Guides:** Official technical documentation

### Hardware Requirements
- Completed Marty robot kits with built-in sensors:
  - Infrared sensor (temperature detection)
  - Color sensor (color detection)
- Marty's internal motors and architecture
- Computers/tablets for MartyBlocks programming
- Marty app for mobile device control

### Software Requirements
- **MartyBlocks:** Scratch-based visual programming environment (web-based)
- **Marty App:** Mobile application for robot control and testing
- **Marty Controller:** Manual control interface
- **LLM Platforms:** Soekia GPT, ChatGPT, Claude for AI integration
- **Online Learning Portal:** Access to [Robotical learning resources](https://learn.robotical.io/lessons/martyVersions/2)

---

## 📊 Assessment Strategy

### Weekly Assessment (T4) - 5 minutes
- **Basic Programming Concepts:** Functions, variables, parameters, commands, libraries, loops, conditions, data structures
- **Marty Architecture:** Understanding of motors, sensors, and internal structure
- **Sensor Knowledge:** Infrared sensor (temperature/electromagnetic waves) and color sensor (color detection)
- **Programming Application:** Using MartyBlocks to control Marty's movement and sensors

### Activity Assessments
- **Programming Exercises:** Demonstrate understanding of functions, variables, loops, and conditions
- **Sensor Testing:** Successfully program Marty to respond to infrared and color sensor inputs
- **Architecture Understanding:** Explain how motors convert electricity to movement using electromagnetic fields
- **AI Integration:** Connect Marty to LLM for voice interaction capabilities

---

## 🎯 Success Indicators

### Student Engagement
- Active participation in programming activities
- Enthusiastic testing of robot capabilities
- Creative program development
- Successful AI integration

### Learning Outcomes
- Clear understanding of visual programming concepts
- Ability to program robot movements and behaviors
- Successful sensor integration and usage
- Effective AI and voice integration

### Teacher Observations
- Smooth transitions between activities
- Effective hands-on learning
- Student collaboration and support
- Clear understanding of programming concepts

---

## 🔄 Differentiation Strategies

### For Advanced Students
- **Extension Programming:** More complex program development
- **Advanced Integration:** Sophisticated AI and sensor combinations
- **Leadership Roles:** Help peers with programming challenges

### For Struggling Students
- **Additional Support:** Individual assistance during programming
- **Simplified Examples:** Step-by-step programming guidance
- **Peer Collaboration:** Pair with supportive classmates

### For Different Learning Styles
- **Visual Learners:** Rich diagrams and visual programming
- **Kinesthetic Learners:** Hands-on programming and testing
- **Auditory Learners:** Discussion and verbal explanations

---

## 📝 Notes and Observations

### Implementation Tips
- **Preparation:** Set up programming environments in advance
- **Technology:** Ensure reliable internet and device compatibility
- **Engagement:** Use immediate feedback to maintain interest
- **Flexibility:** Adjust timing based on programming progress

### Common Challenges
- **Technical Issues:** Programming environment setup or connectivity
- **Complexity:** Some students may struggle with programming concepts
- **Time Management:** Balancing programming with testing and refinement
- **AI Integration:** API setup and connection challenges

### Success Factors
- **Clear Objectives:** Well-defined learning goals
- **Hands-on Learning:** Immediate practical application
- **Collaborative Environment:** Peer support and teamwork
- **Progressive Complexity:** Building on previous weeks' learning

---

*This detailed curriculum provides comprehensive guidance for implementing Week 4 of the Marty AI Literacy Curriculum. The focus on programming and AI integration brings Marty to life while building essential technical skills.*
