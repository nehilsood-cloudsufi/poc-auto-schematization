# React Basics for Python Developers

This guide explains core React concepts using Python analogies.

## Components = Functions That Return HTML

A React component is a function that returns JSX (HTML-like markup). Think of it like a Python function that returns a string — but reactive: when inputs change, React automatically re-renders the output.

```tsx
// React component
function Greeting({ name }: { name: string }) {
  return <h1>Hello, {name}!</h1>;
}
```

```python
# Python analogy
def greeting(name: str) -> str:
    return f"<h1>Hello, {name}!</h1>"
```

The key difference: when `name` changes in React, the UI updates automatically. In Python, you'd have to call the function again and re-render manually.

## Props = Function Parameters (kwargs)

Props are how you pass data into a component — equivalent to keyword arguments in Python.

```tsx
// React: pass data via props
<ProgressTracker runId="abc123" showDetails={true} />
```

```python
# Python analogy
progress_tracker(run_id="abc123", show_details=True)
```

Props are read-only inside the component (like function args — you don't mutate them).

## State (useState) = Reactive Variables

State is a variable that, when changed, triggers the component to re-render. Unlike a plain Python variable, assigning to state via the setter function schedules a re-render.

```tsx
import { useState } from "react";

function Counter() {
  const [count, setCount] = useState(0);  // [current value, setter]

  return (
    <button onClick={() => setCount(count + 1)}>
      Clicked {count} times
    </button>
  );
}
```

```python
# Python analogy (without reactivity)
count = 0

def increment():
    global count
    count += 1
    re_render()  # you'd have to call this manually
```

`useState` returns a tuple: the current value and a setter. Always use the setter — never mutate state directly.

## Effects (useEffect) = "Run This When X Changes"

`useEffect` is like a watcher/observer: "run this side effect when these dependencies change."

```tsx
import { useEffect, useState } from "react";

function DataLoader({ runId }: { runId: string }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    // Runs whenever runId changes
    fetch(`/api/runs/${runId}`).then(r => r.json()).then(setData);
  }, [runId]);  // dependency array: re-run when runId changes

  return <div>{JSON.stringify(data)}</div>;
}
```

```python
# Python analogy: observer pattern
@on_change("run_id")
def load_data(run_id):
    data = requests.get(f"/api/runs/{run_id}").json()
    update_ui(data)
```

- Empty dependency array `[]` = run once on mount (like `__init__`)
- No dependency array = run after every render (usually a bug)
- Return a cleanup function to handle teardown (e.g., close WebSocket)

## Hooks = Reusable Stateful Logic

Hooks are functions that encapsulate state and effects for reuse across components. They're prefixed with `use`. Think of them like Python decorators that inject behavior — except they're plain functions you call inside components.

```tsx
// Custom hook: encapsulates WebSocket logic
function useWebSocket(url: string) {
  const [messages, setMessages] = useState<string[]>([]);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");

  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onmessage = (e) => setMessages(prev => [...prev, e.data]);
    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    return () => ws.close();  // cleanup on unmount
  }, [url]);

  return { messages, status };
}

// Usage in any component
function ProgressPage({ runId }: { runId: string }) {
  const { messages, status } = useWebSocket(`ws://localhost:8000/ws/${runId}`);
  return <pre>{messages.join("\n")}</pre>;
}
```

```python
# Python analogy: mixin or decorator
class WebSocketMixin:
    def __init__(self, url):
        self.ws = WebSocket(url)
        self.messages = []
```

Rules for hooks: only call them at the top level of a component (not inside loops or conditionals), and only inside React components or other custom hooks.

## JSX = HTML-Like Syntax Inside JavaScript

JSX lets you write HTML-like markup directly in TypeScript/JavaScript. It compiles to regular function calls. Think of it like f-strings, but for building UI trees.

```tsx
// JSX
const element = (
  <div className="card">
    <h2>{title}</h2>
    <p>{description}</p>
  </div>
);
```

```python
# Python analogy (approximate)
element = f"""
<div class="card">
  <h2>{title}</h2>
  <p>{description}</p>
</div>
"""
```

Key differences from HTML:
- `className` instead of `class` (reserved word in JS)
- `{expression}` for dynamic values (like f-string `{var}`)
- Self-closing tags required: `<input />` not `<input>`
- Event handlers are camelCase: `onClick`, `onChange`
- Boolean props: `<input disabled />` is shorthand for `disabled={true}`
