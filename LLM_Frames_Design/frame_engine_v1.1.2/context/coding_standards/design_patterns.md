# Design Patterns

**Purpose:** Guide architectural decisions that minimize cognitive load and maximize maintainability.

**Philosophy:** Simpler is better. Avoid architectural complexity unless it solves a real, current problem.

---

## Core Principle: Fight Complexity

> Software systems are perhaps the most intricate and complex things humanity makes. The fewer components there are in the system, the fewer issues there will be.
>
> _Fred Brooks, The Mythical Man-Month_

**Our goal:** Keep the system as simple as possible while meeting actual requirements. Not theoretical future requirements.

---

## 1. Deep Modules Over Shallow Modules

**Deep module:** Simple interface, powerful functionality.
**Shallow module:** Complex interface, simple functionality.

### ❌ Don't: Create shallow modules

```javascript
// Complex interface for basic operations
const reader = FileReaderFactory.createReader(FileType.TEXT);
const asyncReader = AsyncFileReaderFactory.createAsyncReader();
const bufferedReader = new BufferedFileReaderBuilder().withBufferSize(1024).build();
```

**Cognitive load:** 🤯 Which one do I use? What's the difference?

### ✅ Do: Create deep modules (File I/O example)

```javascript
// Simple interface to powerful file operations
const file = open(path);
const data = file.read();
file.write(data);
file.close();
```

**Cognitive load:** 🧠 Learn 4 functions, handle all file operations.

**Rule:** If your interface is as complex as the implementation, you've created a shallow module.

---

## 2. Start with the Simplest Solution

### The YAGNI Principle (You Aren't Gonna Need It)

**Don't build for hypothetical future requirements.**

### ❌ Don't: Build elaborate frameworks prematurely

```javascript
// "We might need multiple user types someday..."
class AbstractUserFactory {
  createUser() {
    throw new Error('Not implemented');
  }
}

class AdminUserFactory extends AbstractUserFactory {
  createUser() {
    return new AdminUser();
  }
}

class RegularUserFactory extends AbstractUserFactory {
  createUser() {
    return new RegularUser();
  }
}

class UserFactoryProvider {
  getFactory(userType) {
    // ...mapping logic
  }
}
```

**Cognitive load:** 🤯 For creating a single user type that exists today.

### ✅ Do: Start simple, evolve when needed

```javascript
// Start with what you actually need
function createUser(name, email) {
  return new User(name, email);
}

// When you actually have 3+ user types, then refactor
```

**Cognitive load:** 🧠 Obvious, maintainable.

**Rule:** Wait for **3 concrete examples** before abstracting. Not 1, not 2, not "maybe someday."

---

## 3. Avoid Premature Optimization

### ❌ Don't: Optimize for theoretical performance

```javascript
// Complex caching system before you know if you need it
class TripleLayerCacheManager {
  constructor() {
    this.l1Cache = new LRUCache({ size: 100 });
    this.l2Cache = new RedisCache();
    this.l3Cache = new DatabaseCache();
  }

  get(key) {
    // Complex cache invalidation logic
    // Fallback chains
    // Cache warming strategies
  }
}
```

### ✅ Do: Measure first, optimize later

```javascript
// Start simple
function getUser(userId) {
  return database.query('SELECT * FROM users WHERE id = ?', userId);
}

// Add caching when metrics show it's needed
```

**Optimization checklist:**

1.  Does profiling show this is actually slow?
2.  Have we tried the simplest optimization first?
3.  Will this complexity pay for itself in 6 months?

---

## 4. Prefer Composition Over Inheritance

### ❌ Don't: Build deep inheritance hierarchies

```javascript
class Animal {}
class Mammal extends Animal {}
class Carnivore extends Mammal {}
class Feline extends Carnivore {}
class Cat extends Feline {}
```

**Cognitive load:** 🤯 Must understand 5 levels of hierarchy. Changes ripple unpredictably.

### ✅ Do: Use composition

```javascript
class Cat {
  constructor() {
    this.movement = new WalkBehavior();
    this.diet = new CarnivoreDiet();
  }

  move() {
    this.movement.execute();
  }
}
```

**Cognitive load:** 🧠 Clear, modular, easy to change.

**Rule:** Favor composition unless inheritance captures a genuine "is-a" relationship.

---

## 5. Colocate Related Code

**Things that change together should live together.**

### ❌ Don't: Separate by layer excessively

```
/controllers/userController.js
/services/userService.js
/repositories/userRepository.js
/models/userModel.js
/validators/userValidator.js
/serializers/userSerializer.js
```

**Cognitive load:** 🤯 Jump across 6 files to understand user operations.

### ✅ Do: Organize by feature

```
/users/
    user.js              // Model and core logic
    userApi.js           // API endpoints
    userDb.js            // Database operations
    userValidation.js    // Validation rules
```

**Cognitive load:** 🧠 Everything about users in one place.

**Rule:** Optimize for **reading and understanding**, not for abstract organizational purity.

---

## 6. Don't Overuse Design Patterns

**Design patterns are tools, not goals.**

### ❌ Don't: Apply patterns because they sound impressive

```javascript
// Unnecessary Strategy + Factory + Singleton pattern
class PaymentStrategyFactory extends Singleton {
  createStrategy(paymentType) {
    if (paymentType === 'credit_card') {
      return new CreditCardPaymentStrategy();
    } else if (paymentType === 'paypal') {
      return new PayPalPaymentStrategy();
    }
  }
}

const paymentProcessor = new PaymentContext(PaymentStrategyFactory.getInstance().createStrategy('credit_card'));
paymentProcessor.execute();
```

### ✅ Do: Use simple conditional logic

```javascript
function processPayment(paymentType, amount) {
  if (paymentType === 'credit_card') {
    chargeCreditCard(amount);
  } else if (paymentType === 'paypal') {
    chargePaypal(amount);
  }
}
```

**When to use a pattern:** When the simplicity gain outweighs the abstraction cost.

---

## 7. Design Sacrifices (Simplicity Through Constraints)

**Sometimes the best design is saying "no" to features that add disproportionate complexity.**

### Example 1: Redis Hash Expiration

Redis didn't support hash item expiration for years because it would have:

- Complicated the data model
- Required changes across many subsystems
- Added performance overhead

**The design sacrifice:** Top-level keys expire, items inside don't. Simple rule, simple implementation.

### Example 2: Vector Databases

Some vector databases sacrifice storing full-precision vectors. Instead, they:

- Normalize on insert
- Quantize to smaller formats
- Don't retain original floats

**The design sacrifice:** You can't retrieve the exact vector you put in. But the system is simpler and faster.

**Ask yourself:**

- Can I remove 5% of features to eliminate 50% of complexity?
- What if this feature just didn't exist? Would it really hurt?
- Am I building this because users need it, or because it's architecturally elegant?

---

## 8. Avoid Microservices Unless You Have a Reason

### ❌ Don't: Split into microservices prematurely

```
UserService → AuthService → EmailService → NotificationService → LoggingService
```

**Cognitive load:** 🤯

- Network failures to handle
- Distributed debugging
- Service discovery
- Eventual consistency
- Multiple deployments

### ✅ Do: Start with a modular monolith

```
// Well-organized modules in one codebase
/app
    /users
    /auth
    /email
    /notifications
```

**Cognitive load:** 🧠

- Simple debugging
- Easy refactoring
- One deployment
- Direct function calls

**When to split:** When you have **organizational** reasons (separate teams) or **scaling** reasons (measured, not imagined).

---

## 9. Boring Technology is Good

**The best software systems that stood the test of time - Linux, Kubernetes, Chrome, Redis - are boring inside.**

### ✅ Choose boring, proven solutions

- PostgreSQL over the latest NoSQL hype
- REST over GraphQL (unless you need it)
- Simple queues over complex event streams
- Standard libraries over fancy frameworks

### Why boring wins

- Fewer surprises
- Better documentation
- More developers know it
- Proven at scale
- Easier to debug

**Ask yourself:** Will this fancy technology still seem like a good idea in 2 years when I'm debugging a production issue at 2am?

---

## 10. Make Dependencies Explicit

### ❌ Don't: Hide dependencies

```javascript
class UserService {
  createUser(name) {
    // Surprise! This also depends on EmailService and LogService
    const user = new User(name);
    new EmailService().sendWelcomeEmail(user);
    new LogService().logUserCreation(user);
    return user;
  }
}
```

**Cognitive load:** 🤯 Must read implementation to discover hidden dependencies.

### ✅ Do: Inject dependencies explicitly

```javascript
class UserService {
  constructor(emailService, logService) {
    this.emailService = emailService;
    this.logService = logService;
  }

  createUser(name) {
    const user = new User(name);
    this.emailService.sendWelcomeEmail(user);
    this.logService.logUserCreation(user);
    return user;
  }
}
```

**Cognitive load:** 🧠 Dependencies clear from constructor.

---

## 11. Avoid Event-Driven Architecture Unless Necessary

### ❌ Don't: Use events for simple workflows

```
// Order created → Event → Inventory service listens →
// Inventory updated → Event → Email service listens →
// Email sent → Event → Analytics service listens...
```

**Cognitive load:** 🤯

- Hard to trace execution
- Debugging requires log aggregation
- Hard to reason about ordering
- Hidden coupling through event contracts

### ✅ Do: Use direct calls for simple workflows

```javascript
function processOrder(order) {
  inventory.reserveItems(order);
  email.sendConfirmation(order);
  analytics.trackPurchase(order);
}
```

**Cognitive load:** 🧠

- Clear sequence
- Easy to debug
- Easy to test
- Obvious dependencies

**When to use events:** When you need **temporal decoupling** (fire and forget) or **unknown consumers** (plugins).

---

## 12. The Interface Principle

**Your API/interface is your commitment to your users. Make it small, stable, and obvious.**

### ❌ Poor interface design

```javascript
class Cache {
  get(key) {}
  getOrDefault(key, defaultValue) {}
  getMulti(keys) {}
  set(key, value) {}
  setWithTtl(key, value, ttl) {}
  setMulti(items) {}
  setIfNotExists(key, value) {}
  delete(key) {}
  deleteMulti(keys) {}
  deleteMatching(pattern) {}
  exists(key) {}
  getTtl(key) {}
}
```

**12+ methods. Cognitive overload. Easy to use wrong.**

### ✅ Good interface design

```javascript
class Cache {
  get(key) {}
  set(key, value) {}
  delete(key) {}
}
```

**3 methods. Obvious what they do. Hard to use wrong.**

**Rule:** Every method you add is a forever commitment. Start minimal.

---

## 13. Configuration vs. Code

### ❌ Don't: Make everything configurable

```yaml
# config.yaml with 200 options
database:
  connection:
    pool:
      size: 10
      timeout: 5000
      max_overflow: 20
      connection_timeout: 30
      idle_timeout: 300
  retry:
    max_attempts: 3
    backoff: exponential
    base_delay: 100
# ... 190 more options
```

**Cognitive load:** 🤯 Which options matter? What are safe values?

### ✅ Do: Sensible defaults, minimal configuration

```yaml
# config.yaml
database:
  url: postgresql://localhost/mydb
  pool_size: 10 # Only if you need to change it
```

**Cognitive load:** 🧠 Obvious and simple.

**Rule:** Configuration is for **things that change between environments**, not for every parameter you can think of.

---

## 14. Error Handling: Fail Fast, Fail Loud

### ❌ Don't: Silently recover or return nulls

```javascript
function getUser(userId) {
  try {
    return db.query(userId);
  } catch (error) {
    return null; // What went wrong?
  }
}
```

### ✅ Do: Fail explicitly with context

```javascript
function getUser(userId) {
  try {
    return db.query(userId);
  } catch (error) {
    if (error instanceof DatabaseConnectionError) {
      throw new UserServiceError(`Cannot fetch user ${userId}: database unavailable`, { cause: error });
    } else if (error instanceof UserNotFoundError) {
      throw error; // This is expected, pass it up
    }
    throw error; // Rethrow unexpected errors
  }
}
```

**Rule:** Fail fast, with clear error messages that help debugging.

---

## 15. Review Your Architecture for Cognitive Load

**Questions to ask in architecture reviews:**

1.  **Can a new developer understand the system in a day?**
    - If no: Too complex.
2.  **Can you trace a request from start to finish without jumping through 10+ files/services?**
    - If no: Too distributed.
3.  **Do you need a diagram to explain basic operations?**
    - If yes: Might be overengineered.
4.  **How easy is it to reproduce and debug an issue?**
    - If hard: Cognitive load is too high.
5.  **Are there unique mental models or architectures developers must learn?**
    - If yes: Question if they add value.
6.  **Would removing a component/layer make things simpler without losing important functionality?**
    - If yes: Consider removing it.

**Involve junior developers in reviews.** They will identify mentally demanding areas that senior developers have gotten used to.

---

## 16. The Boring Test

**Before adding architectural complexity, ask:**

1.  Do we have a **measured, current problem** this solves?
2.  Have we tried simpler solutions first?
3.  Will this complexity pay for itself in 6 months?
4.  Can a junior developer maintain this?
5.  Would I want to debug this at 2am?

**If any answer is "no," choose the boring solution.**

---

## Architecture Patterns We Recommend

### For most projects (start here)

- **Modular monolith** with clear boundaries
- **Layered architecture** (API → Service → Data) - but colocated by feature
- **Boring tech stack** (proven databases, standard frameworks)
- **Direct function calls** for workflows
- **Simple interfaces** (deep modules)

### When you've outgrown the above

- **Microservices** (when you have organizational/scaling reasons)
- **Event-driven** (when you need temporal decoupling)
- **CQRS** (when reads/writes have drastically different requirements)

---

## Architecture Patterns We Are Skeptical Of

### Use with extreme caution

- Clean Architecture / Hexagonal Architecture (often creates shallow modules)
- DDD (often leads to over-abstraction)
- Event Sourcing (unless you truly need an audit trail)
- Microservices-first (start monolith, split later)
- GraphQL (unless clients genuinely need flexible queries)

**Why skepticism?** These patterns trade simplicity for theoretical benefits. They work **if** you have the specific problems they solve. Otherwise, they're pure cognitive load.

---

## Remember

**The best architecture:**

- Is boring
- Has few components
- Has simple interfaces
- Is easy to debug
- Can be explained in 10 minutes
- Doesn't require special mental models

**The worst architecture:**

- Is "clever"
- Has many layers of abstraction
- Requires understanding 6 design patterns to add a feature
- Makes debugging feel like archaeology
- Requires a PhD to onboard

---

## Further Reading

- [_A Philosophy of Software Design_](https://web.stanford.edu/~ouster/cgi-bin/book.php) by John Ousterhout
- [Cognitive Load Developer's Handbook](https://github.com/zakirullin/cognitive-load)
- [_The Mythical Man-Month_](https://en.wikipedia.org/wiki/The_Mythical_Man-Month) by Fred Brooks

---

**Choose boring. Future you will thank you.**
