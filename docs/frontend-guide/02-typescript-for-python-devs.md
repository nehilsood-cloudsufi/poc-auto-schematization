# TypeScript for Python Developers

TypeScript is JavaScript with static types. If you know Python type annotations, most TypeScript concepts will feel familiar — though TypeScript types are more pervasive and enforced at compile time.

## `interface` = TypedDict / dataclass

An `interface` defines the shape of an object — like a Python `TypedDict` or `dataclass`.

```typescript
// TypeScript
interface Run {
  id: string;
  dataset: string;
  status: "pending" | "running" | "done" | "failed";
  created_at: string;
}
```

```python
# Python TypedDict equivalent
from typing import TypedDict, Literal

class Run(TypedDict):
    id: str
    dataset: str
    status: Literal["pending", "running", "done", "failed"]
    created_at: str
```

```python
# Python dataclass equivalent
from dataclasses import dataclass
from typing import Literal

@dataclass
class Run:
    id: str
    dataset: str
    status: Literal["pending", "running", "done", "failed"]
    created_at: str
```

Interfaces are structural (duck-typed): any object with the right shape satisfies the interface, even if it wasn't explicitly declared as that type.

## `type` = Union Type / Type Alias

`type` creates an alias, including union types.

```typescript
// Type alias
type RunId = string;

// Union type
type Status = "pending" | "running" | "done" | "failed";

// Complex alias
type ApiResponse<T> = { data: T; error: string | null };
```

```python
# Python equivalents
RunId = str  # type alias

from typing import Literal, Union
Status = Literal["pending", "running", "done", "failed"]

from typing import Generic, TypeVar, Optional
T = TypeVar("T")
class ApiResponse(Generic[T]):
    data: T
    error: Optional[str]
```

When to use `interface` vs `type`: use `interface` for object shapes (can be extended/merged), use `type` for unions, primitives, and complex compositions.

## Generics = Similar to Python Generics, More Commonly Used

TypeScript generics use `<T>` syntax, like Python's `TypeVar`. They're used far more pervasively in TypeScript — you'll see them constantly in React.

```typescript
// Generic function
function first<T>(arr: T[]): T | undefined {
  return arr[0];
}

// Generic interface
interface ApiResponse<T> {
  data: T;
  status: number;
}

// Usage
const response: ApiResponse<Run[]> = await fetchRuns();
```

```python
from typing import TypeVar, Generic, Optional

T = TypeVar("T")

def first(arr: list[T]) -> Optional[T]:
    return arr[0] if arr else None

class ApiResponse(Generic[T]):
    data: T
    status: int
```

In React, you'll see generics most often with `useState<T>()`, `useRef<T>()`, and typed event handlers.

## `string | null` = `Optional[str]`

TypeScript union with `null` maps directly to Python's `Optional`.

```typescript
// TypeScript
let name: string | null = null;
let count: number | undefined = undefined;

// Nullish coalescing (like Python's "or" for None)
const display = name ?? "Unknown";

// Optional chaining (like Python's getattr with default)
const length = name?.length;  // undefined if name is null
```

```python
# Python
from typing import Optional
name: Optional[str] = None
count: Optional[int] = None

# Python equivalent
display = name or "Unknown"
length = len(name) if name is not None else None
```

Key differences: TypeScript distinguishes `null` (explicit absence) and `undefined` (unset). Python only has `None`. TypeScript also has strict null checks — the compiler forces you to handle `null` before using a value.

## `Record<string, unknown>` = `Dict[str, Any]`

`Record<K, V>` is a typed dictionary where all keys are type `K` and all values are type `V`.

```typescript
// TypeScript
const config: Record<string, unknown> = { key: "value", count: 42 };
const scores: Record<string, number> = { alice: 95, bob: 87 };
```

```python
# Python
from typing import Any
config: dict[str, Any] = {"key": "value", "count": 42}
scores: dict[str, int] = {"alice": 95, "bob": 87}
```

Use `Record<string, unknown>` (not `any`) when you don't know the value types — `unknown` forces a type check before use, while `any` opts out of type checking entirely (like `Any` vs `object` in Python).

## Other Common Patterns

### Optional Properties

```typescript
interface Config {
  dataset: string;
  maxRetries?: number;  // optional (may be undefined)
}
```

```python
class Config(TypedDict, total=False):
    dataset: str
    max_retries: int  # optional
```

### Readonly

```typescript
interface Props {
  readonly id: string;  // can't be reassigned
  items: readonly string[];  // immutable array
}
```

```python
from typing import Final, Sequence
id: Final[str] = "abc"
items: Sequence[str] = ["a", "b"]  # read-only view
```

### Enums (prefer union literals instead)

```typescript
// TypeScript enum (avoid — prefer union literals)
enum Status { Pending = "pending", Running = "running" }

// Better: union literal type
type Status = "pending" | "running" | "done" | "failed";
```

```python
# Python enum
from enum import Enum
class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
```

### Type Narrowing = `isinstance` checks

```typescript
function process(value: string | number) {
  if (typeof value === "string") {
    // TypeScript knows value is string here
    console.log(value.toUpperCase());
  } else {
    // TypeScript knows value is number here
    console.log(value.toFixed(2));
  }
}
```

```python
def process(value: str | int):
    if isinstance(value, str):
        print(value.upper())
    else:
        print(f"{value:.2f}")
```
