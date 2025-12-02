# Coding Standards

**Purpose:** Reduce cognitive load and maintain code that future developers (including yourself) can understand quickly.

**Philosophy:** We optimize for reading and understanding, not for writing. Code is read far more often than it's written.

---

## Core Principle: Minimize Cognitive Load

> Cognitive load is how much a developer needs to think to complete a task.

The average person can hold roughly **4 chunks** in working memory. Once cognitive load exceeds this threshold, understanding becomes exponentially harder.

**Our goal:** Reduce any cognitive load beyond what is intrinsic to the problem we're solving.

---

## 1. Write Obvious Code

### ❌ Don't: Use clever abbreviations

```javascript
function calcUsrSubRen(uid, st) {
  // What does this mean?
}
```

### ✅ Do: Use clear, explicit names

```javascript
function calculateUserSubscriptionRenewalDate(userId, subscriptionType) {
  // Clear what this does
}
```

**Why:** Every unclear name adds cognitive load. Developers must pause, figure out the meaning, and hold it in memory.

---

## 2. Avoid Deeply Nested Logic

### ❌ Don't: Nest conditions deeply

```javascript
if (user) {
  if (user.isActive) {
    if (user.hasSubscription) {
      if (subscription.isValid()) {
        // Do something
      }
    }
  }
}
```

**Cognitive load:** 🤯 You must hold 4 conditions in your head simultaneously.

### ✅ Do: Use early returns (guard clauses)

```javascript
if (!user) {
  return new Error('User not found');
}
if (!user.isActive) {
  return new Error('User inactive');
}
if (!user.hasSubscription) {
  return new Error('No subscription');
}
if (!subscription.isValid()) {
  return new Error('Invalid subscription');
}

// Now do the actual work
```

**Cognitive load:** 🧠 Each condition is independent. Linear, easy to follow.

---

## 3. Limit Function Arguments

### ❌ Don't: Pass many individual arguments

```javascript
function createUser(name, email, age, address, city, country, postalCode, phone) {
  // ...
}
```

**Cognitive load:** 🤯 8 parameters to remember and order correctly.

### ✅ Do: Group related data

```javascript
function createUser(userProfile, contactInfo) {
  // ...
}
```

**Cognitive load:** 🧠 Only 2 meaningful chunks to remember.

**Rule of thumb:** If you have more than 3-4 parameters, consider grouping them into an object or class.

---

## 4. Keep Functions Focused (Single Responsibility)

### ❌ Don't: Mix unrelated concerns

```javascript
function processOrder(order) {
  // Validate payment
  // Update inventory
  // Send email
  // Log analytics
  // Update customer points
  // Generate invoice
}
```

**Cognitive load:** 🤯 Must understand 6 different domains simultaneously.

### ✅ Do: One function, one job

```javascript
function processOrder(order) {
  validatePayment(order);
  updateInventory(order);
  sendConfirmationEmail(order);

  // Clear sequence of high-level steps
}
```

---

## 5. Avoid "Smart" Code

### ❌ Don't: Write clever one-liners

```javascript
const result = items.filter(
  (x) => x.status === 'active' && x.created > cutoffDate && validOwners.includes(x.owner) && !x.archived,
);
```

**Cognitive load:** 🤯 Must parse and understand 4 conditions in one dense line.

### ✅ Do: Write boring, obvious code

```javascript
const activeItems = items.filter((x) => x.status === 'active');
const recentItems = activeItems.filter((x) => x.created > cutoffDate);
const authorizedItems = recentItems.filter((x) => validOwners.includes(x.owner));
const result = authorizedItems.filter((x) => !x.archived);
```

**Cognitive load:** 🧠 Each step is trivial to understand.

**Remember:** If you write the code as cleverly as possible, you are, by definition, not smart enough to debug it. _(Brian Kernighan)_

---

## 6. Avoid Unnecessary Abstractions

### ❌ Don't: Create abstractions prematurely

```javascript
class AbstractUserFactoryBuilder {
  createBuilder() {
    return new UserFactory();
  }
}

class UserFactory {
  createUser() {
    return new User();
  }
}
```

**Cognitive load:** 🤯 Must understand an architecture that adds no value.

### ✅ Do: Start simple, add abstractions when needed

```javascript
function createUser(name, email) {
  return new User(name, email);
}
```

**Cognitive load:** 🧠 Obvious what this does.

**When to abstract:** When you have 3+ concrete examples showing a pattern. Not before.

---

## 7. Reduce Intermediate Variables for Simple Operations

### ❌ Don't: Create variables that don't add clarity

```javascript
const user = getUser(userId);
const email = user.email;
const lowercaseEmail = email.toLowerCase();
return lowercaseEmail;
```

**Cognitive load:** 🧠++ Must track 4 variables for a trivial operation.

### ✅ Do: Chain simple operations

```javascript
return getUser(userId).email.toLowerCase();
```

**Cognitive load:** 🧠 One clear intent: get the lowercase email.

**But:** If operations are complex, break them down for clarity.

---

## 8. Name Booleans Positively

### ❌ Don't: Use negative boolean names

```javascript
if (!isNotValid) {
  // Wait, what?
}
```

**Cognitive load:** 🤯 Double negatives require mental gymnastics.

### ✅ Do: Use positive names

```javascript
if (isValid) {
  // Clear
}
```

---

## 9. Avoid Long Parameter Lists with Booleans

### ❌ Don't: Use boolean flags to change behavior

```javascript
sendEmail(user, subject, body, true, false, true, false);
// What do these booleans mean?
```

**Cognitive load:** 🤯 Must look up function signature every time.

### ✅ Do: Use explicit method names or named parameters

```javascript
sendEmail({
  user: user,
  subject: subject,
  body: body,
  includeAttachment: true,
  sendImmediately: false,
});
```

Or better, use distinct functions:

```javascript
sendEmailWithAttachment(user, subject, body);
scheduleEmail(user, subject, body);
```

---

## 10. Comments Explain "Why", not "What"

### ❌ Don't: State the obvious

```javascript
// Increment the counter
counter++;
```

### ✅ Do: Explain non-obvious decisions

```javascript
// We retry 3 times because the payment gateway times out intermittently
// under load. See ticket: DI-12345
const maxRetries = 3;
```

---

## 11. Keep Modules Deep, Not Shallow

**Deep module:** Simple interface hiding complex implementation.

**Shallow module:** Complex interface for simple implementation.

### ❌ Example: Shallow Modules

```
// Many different methods for reading a file
readFile(), readFileAsync(), readFileWithEncoding(),
readFileLineByLine(), readFileInChunks(), ...
```

**Cognitive load:** 🤯 Which one do I use? What's the difference?

### ✅ Example: Unix File I/O (deep module)

```
// A small set of functions for all file operations
open(), read(), write(), seek(), close()
```

**Cognitive load:** 🧠 Learn 5 functions, do everything with files.

**Aim for:** Powerful functionality behind simple interfaces.

---

## 12. Make Errors Obvious

### ❌ Don't: Silently fail or return cryptic codes

```javascript
function getUser(userId) {
  // Returns null on error, but why?
  return null;
}
```

### ✅ Do: Fail loudly with clear messages

```javascript
function getUser(userId) {
  if (!userExists(userId)) {
    throw new UserNotFoundError(`User ${userId} does not exist`);
  }
  return fetchUser(userId);
}
```

---

## 13. Consistency Trumps Personal Preference

**Pick one style and stick to it across the codebase.**

### ❌ Don't: Mix styles

```javascript
getUserEmail(); // camelCase
get_user_name(); // snake_case
GetUserID(); // PascalCase
```

### ✅ Do: Be consistent

```javascript
getUserEmail();
getUserName();
getUserId();
```

---

## 14. Avoid Hidden Side Effects

### ❌ Don't: Hide state changes in innocent-looking functions

```javascript
function calculateTotal(items) {
  // Surprise! This also updates the database
  db.updateLastCalculationTime();
  return items.reduce((sum, item) => sum + item.price, 0);
}
```

**Cognitive load:** 🤯 Must read implementation to know it modifies state.

### ✅ Do: Make side effects explicit

```javascript
function calculateAndRecordTotal(items) {
  const total = items.reduce((sum, item) => sum + item.price, 0);
  db.updateLastCalculationTime();
  return total;
}
```

Or better, separate concerns:

```javascript
function calculateTotal(items) {
  return items.reduce((sum, item) => sum + item.price, 0);
}

function recordCalculation() {
  db.updateLastCalculationTime();
}
```

---

## 15. Avoid Magic Numbers and Strings

### ❌ Don't: Use unexplained literals

```javascript
if (status === 3) {
  // What does 3 mean?
}
```

### ✅ Do: Use named constants

```javascript
const STATUS_APPROVED = 3;

if (status === STATUS_APPROVED) {
  // Clear
}
```

---

## Code Review Checklist

When reviewing code (yours or others'), ask:

1. **Can I understand this in under 30 seconds?** If not, cognitive load is too high.
2. **Do I need to jump around to understand what's happening?** If yes, consider consolidating.
3. **Are there variables/functions/classes with unclear names?** Rename them.
4. **Is there clever code that makes me feel dumb?** Simplify it.
5. **Would a middle developer understand this quickly?** If not, it's too complex.
6. **Am I adding abstractions because I might need them someday?** YAGNI (You Aren't Gonna Need It).

---

## Remember

> Debugging is twice as hard as writing the code in the first place. Therefore, if you write the code as cleverly as possible, you are, by definition, not smart enough to debug it.
>
> _Brian Kernighan_

**Write code for the next developer.** That developer might be you in 6 months, and you will have forgotten everything.

---

## General Conventions

- **Follow established community conventions for your language.** (e.g., ESLint for JavaScript, RuboCop for Ruby, Checkstyle for Java).
- **Consistency within the codebase is more important than personal preference.** If the project uses tabs, use tabs. If it uses a certain naming convention, follow it.
- **Configure your IDE** to automatically format code according to the project's standards. This eliminates style debates and keeps diffs clean.
- **Aim for a maximum line length of around 120 characters.** This aids readability, especially on smaller screens or side-by-side diffs.
- **Sort imports logically:** standard library, external libraries, internal modules. This makes it easier to see a file's dependencies.
- **Avoid commented-out code.** Use version control to keep track of old code. Commented-out blocks add noise and are rarely re-enabled.
- **No spaces or tabs on empty lines.** This prevents unnecessary noise in commits.
