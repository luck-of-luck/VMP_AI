"""Pattern equivalence database for cross-language operations.

This module contains a comprehensive database of equivalent patterns
across programming languages, organized by category.
"""

from typing import Any, Dict, List

from ...constants import ExampleDataDefaults

# =============================================================================
# Pattern Categories
# =============================================================================

PATTERN_CATEGORIES = [
    "control_flow",
    "functions",
    "data_structures",
    "iteration",
    "error_handling",
    "async",
    "classes",
    "type_system",
]

# =============================================================================
# Pattern Equivalence Database
# =============================================================================

PATTERN_DATABASE: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # Control Flow Patterns
    # -------------------------------------------------------------------------
    "if_else": {
        "concept": "Conditional branching",
        "category": "control_flow",
        "description": "Basic if-else conditional branching",
        "examples": {
            "python": {
                "code": "if condition:\n    do_something()\nelse:\n    do_other()",
                "description": "Python uses indentation for blocks",
            },
            "javascript": {
                "code": "if (condition) {\n    doSomething();\n} else {\n    doOther();\n}",
                "description": "JavaScript uses braces for blocks",
            },
            "typescript": {
                "code": "if (condition) {\n    doSomething();\n} else {\n    doOther();\n}",
                "description": "TypeScript syntax identical to JavaScript",
            },
            "java": {
                "code": "if (condition) {\n    doSomething();\n} else {\n    doOther();\n}",
                "description": "Java uses C-style syntax",
            },
            "go": {
                "code": "if condition {\n    doSomething()\n} else {\n    doOther()\n}",
                "description": "Go doesn't require parentheses around condition",
            },
            "rust": {
                "code": "if condition {\n    do_something();\n} else {\n    do_other();\n}",
                "description": "Rust if is an expression, can return values",
            },
        },
        "related_patterns": ["ternary_operator", "switch_case"],
    },
    "ternary_operator": {
        "concept": "Conditional expression",
        "category": "control_flow",
        "description": "Inline conditional expression (ternary operator)",
        "examples": {
            "python": {
                "code": "result = value_if_true if condition else value_if_false",
                "description": "Python's conditional expression syntax",
            },
            "javascript": {
                "code": "const result = condition ? valueIfTrue : valueIfFalse;",
                "description": "JavaScript ternary operator",
            },
            "typescript": {
                "code": "const result = condition ? valueIfTrue : valueIfFalse;",
                "description": "TypeScript ternary operator",
            },
            "java": {
                "code": "var result = condition ? valueIfTrue : valueIfFalse;",
                "description": "Java ternary operator",
            },
            "go": {
                "code": "// Go has no ternary operator\nvar result int\nif condition {\n    result = valueIfTrue\n} else {\n    result = valueIfFalse\n}",
                "description": "Go lacks ternary - use if-else",
                "notes": ["Go intentionally omits ternary for clarity"],
            },
            "rust": {
                "code": "let result = if condition { value_if_true } else { value_if_false };",
                "description": "Rust if-else is an expression",
            },
        },
        "related_patterns": ["if_else", "null_coalescing"],
    },
    "switch_case": {
        "concept": "Multi-way branching",
        "category": "control_flow",
        "description": "Switch/case or pattern matching statement",
        "examples": {
            "python": {
                "code": "match value:\n    case 1:\n        handle_one()\n    case 2:\n        handle_two()\n    case _:\n        handle_default()",
                "description": "Python 3.10+ match statement with pattern matching",
            },
            "javascript": {
                "code": "switch (value) {\n    case 1:\n        handleOne();\n        break;\n    case 2:\n        handleTwo();\n        break;\n    default:\n        handleDefault();\n}",
                "description": "JavaScript switch with explicit break",
            },
            "typescript": {
                "code": "switch (value) {\n    case 1:\n        handleOne();\n        break;\n    case 2:\n        handleTwo();\n        break;\n    default:\n        handleDefault();\n}",
                "description": "TypeScript switch statement",
            },
            "java": {
                "code": "switch (value) {\n    case 1 -> handleOne();\n    case 2 -> handleTwo();\n    default -> handleDefault();\n}",
                "description": "Java 14+ switch expression (no fall-through)",
            },
            "go": {
                "code": "switch value {\ncase 1:\n    handleOne()\ncase 2:\n    handleTwo()\ndefault:\n    handleDefault()\n}",
                "description": "Go switch - no fall-through by default",
            },
            "rust": {
                "code": "match value {\n    1 => handle_one(),\n    2 => handle_two(),\n    _ => handle_default(),\n}",
                "description": "Rust match expression - exhaustive pattern matching",
            },
        },
        "related_patterns": ["if_else", "pattern_matching"],
    },
    # -------------------------------------------------------------------------
    # Function Patterns
    # -------------------------------------------------------------------------
    "function_definition": {
        "concept": "Function declaration",
        "category": "functions",
        "description": "Basic function definition with parameters and return",
        "examples": {
            "python": {
                "code": "def add(a: int, b: int) -> int:\n    return a + b",
                "description": "Python function with type hints",
            },
            "javascript": {
                "code": "function add(a, b) {\n    return a + b;\n}",
                "description": "JavaScript function declaration",
            },
            "typescript": {
                "code": "function add(a: number, b: number): number {\n    return a + b;\n}",
                "description": "TypeScript function with types",
            },
            "java": {
                "code": "public int add(int a, int b) {\n    return a + b;\n}",
                "description": "Java method declaration",
            },
            "go": {
                "code": "func add(a int, b int) int {\n    return a + b\n}",
                "description": "Go function declaration",
            },
            "rust": {
                "code": "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}",
                "description": "Rust function - implicit return for last expression",
            },
        },
        "related_patterns": ["arrow_function", "async_function", "generator"],
    },
    "arrow_function": {
        "concept": "Lambda/arrow function",
        "category": "functions",
        "description": "Short-form anonymous function",
        "examples": {
            "python": {
                "code": "add = lambda a, b: a + b",
                "description": "Python lambda expression",
            },
            "javascript": {
                "code": "const add = (a, b) => a + b;",
                "description": "JavaScript arrow function",
            },
            "typescript": {
                "code": "const add = (a: number, b: number): number => a + b;",
                "description": "TypeScript arrow function with types",
            },
            "java": {
                "code": "BiFunction<Integer, Integer, Integer> add = (a, b) -> a + b;",
                "description": "Java lambda expression",
            },
            "go": {
                "code": "add := func(a, b int) int {\n    return a + b\n}",
                "description": "Go anonymous function",
            },
            "rust": {
                "code": "let add = |a: i32, b: i32| -> i32 { a + b };",
                "description": "Rust closure",
            },
        },
        "related_patterns": ["function_definition", "closure"],
    },
    "default_parameters": {
        "concept": "Default parameter values",
        "category": "functions",
        "description": "Function parameters with default values",
        "examples": {
            "python": {
                "code": "def greet(name: str, greeting: str = 'Hello') -> str:\n    return f'{greeting}, {name}!'",
                "description": "Python default parameter",
            },
            "javascript": {
                "code": "function greet(name, greeting = 'Hello') {\n    return `${greeting}, ${name}!`;\n}",
                "description": "JavaScript ES6 default parameter",
            },
            "typescript": {
                "code": "function greet(name: string, greeting: string = 'Hello'): string {\n    return `${greeting}, ${name}!`;\n}",
                "description": "TypeScript default parameter",
            },
            "java": {
                "code": '// Java uses method overloading\npublic String greet(String name) {\n    return greet(name, "Hello");\n}\n\npublic String greet(String name, String greeting) {\n    return greeting + ", " + name + "!";\n}',
                "description": "Java simulates defaults via overloading",
                "notes": ["Java doesn't have native default parameters"],
            },
            "go": {
                "code": '// Go uses variadic or options pattern\nfunc greet(name string, opts ...string) string {\n    greeting := "Hello"\n    if len(opts) > 0 {\n        greeting = opts[0]\n    }\n    return greeting + ", " + name + "!"\n}',
                "description": "Go uses variadic arguments pattern",
                "notes": ["Go doesn't have native default parameters"],
            },
            "rust": {
                "code": '// Rust uses builder pattern or Option\nfn greet(name: &str, greeting: Option<&str>) -> String {\n    let g = greeting.unwrap_or("Hello");\n    format!("{}, {}!", g, name)\n}',
                "description": "Rust uses Option for optional params",
            },
        },
        "related_patterns": ["function_definition", "variadic_arguments"],
    },
    # -------------------------------------------------------------------------
    # Data Structure Patterns
    # -------------------------------------------------------------------------
    "list_comprehension": {
        "concept": "List transformation with filter",
        "category": "data_structures",
        "description": "Create a new list by transforming and filtering elements",
        "examples": {
            "python": {
                "code": "doubled = [x * 2 for x in numbers if x > 0]",
                "description": "Python list comprehension",
            },
            "javascript": {
                "code": "const doubled = numbers.filter(x => x > 0).map(x => x * 2);",
                "description": "JavaScript filter + map chain",
            },
            "typescript": {
                "code": "const doubled = numbers.filter(x => x > 0).map(x => x * 2);",
                "description": "TypeScript filter + map chain",
            },
            "java": {
                "code": "List<Integer> doubled = numbers.stream()\n    .filter(x -> x > 0)\n    .map(x -> x * 2)\n    .collect(Collectors.toList());",
                "description": "Java Stream API",
            },
            "go": {
                "code": "var doubled []int\nfor _, x := range numbers {\n    if x > 0 {\n        doubled = append(doubled, x * 2)\n    }\n}",
                "description": "Go explicit loop",
                "notes": ["Go has no list comprehension syntax"],
            },
            "rust": {
                "code": "let doubled: Vec<i32> = numbers.iter()\n    .filter(|&x| *x > 0)\n    .map(|x| x * 2)\n    .collect();",
                "description": "Rust iterator chain",
            },
        },
        "related_patterns": ["map_function", "filter_function", "reduce_function"],
    },
    "dictionary_literal": {
        "concept": "Key-value map creation",
        "category": "data_structures",
        "description": "Creating a dictionary/map with key-value pairs",
        "examples": {
            "python": {
                "code": f"person = {{'name': 'Alice', 'age': {ExampleDataDefaults.PERSON_AGE}}}",
                "description": "Python dictionary literal",
            },
            "javascript": {
                "code": f"const person = {{ name: 'Alice', age: {ExampleDataDefaults.PERSON_AGE} }};",
                "description": "JavaScript object literal",
            },
            "typescript": {
                "code": (f"const person: {{ name: string; age: number }} = {{ name: 'Alice', age: {ExampleDataDefaults.PERSON_AGE} }};"),
                "description": "TypeScript object with type annotation",
            },
            "java": {
                "code": f'Map<String, Object> person = Map.of("name", "Alice", "age", {ExampleDataDefaults.PERSON_AGE});',
                "description": "Java immutable map (Java 9+)",
            },
            "go": {
                "code": (f'person := map[string]interface{{}}{{\n    "name": "Alice",\n    "age":  {ExampleDataDefaults.PERSON_AGE},\n}}'),
                "description": "Go map literal",
            },
            "rust": {
                "code": (
                    "let person: HashMap<&str, &str> = HashMap::from([\n"
                    '    ("name", "Alice"),\n'
                    f'    ("age", "{ExampleDataDefaults.PERSON_AGE}"),\n'
                    "]);"
                ),
                "description": "Rust HashMap from array",
            },
        },
        "related_patterns": ["list_literal", "destructuring"],
    },
    "destructuring": {
        "concept": "Destructuring assignment",
        "category": "data_structures",
        "description": "Extract values from objects/arrays into variables",
        "examples": {
            "python": {
                "code": (
                    "name, age = person['name'], person['age']\n"
                    "# or with dataclass:\n"
                    "from dataclasses import dataclass\n"
                    "@dataclass\n"
                    "class Person:\n"
                    "    name: str\n"
                    "    age: int\n"
                    f"p = Person('Alice', {ExampleDataDefaults.PERSON_AGE})\n"
                    "name, age = p.name, p.age"
                ),
                "description": "Python unpacking (limited destructuring)",
            },
            "javascript": {
                "code": "const { name, age } = person;\nconst [first, second] = array;",
                "description": "JavaScript destructuring",
            },
            "typescript": {
                "code": "const { name, age }: { name: string; age: number } = person;\nconst [first, second] = array;",
                "description": "TypeScript destructuring with types",
            },
            "java": {
                "code": (
                    "// Java 16+ record pattern\n"
                    "record Person(String name, int age) {}\n"
                    f'Person p = new Person("Alice", {ExampleDataDefaults.PERSON_AGE});\n'
                    "String name = p.name();\n"
                    "int age = p.age();"
                ),
                "description": "Java records (no true destructuring)",
                "notes": ["Java lacks destructuring syntax"],
            },
            "go": {
                "code": '// Go has no destructuring\nname := person["name"]\nage := person["age"]',
                "description": "Go manual extraction",
            },
            "rust": {
                "code": "let Person { name, age } = person;\nlet [first, second, ..] = array;",
                "description": "Rust pattern matching destructuring",
            },
        },
        "related_patterns": ["dictionary_literal", "spread_operator"],
    },
    # -------------------------------------------------------------------------
    # Error Handling Patterns
    # -------------------------------------------------------------------------
    "try_catch": {
        "concept": "Exception handling",
        "category": "error_handling",
        "description": "Try-catch block for exception handling",
        "examples": {
            "python": {
                "code": "try:\n    result = risky_operation()\nexcept ValueError as e:\n    handle_error(e)\nfinally:\n    cleanup()",
                "description": "Python try-except-finally",
            },
            "javascript": {
                "code": "try {\n    result = riskyOperation();\n} catch (e) {\n    handleError(e);\n} finally {\n    cleanup();\n}",
                "description": "JavaScript try-catch-finally",
            },
            "typescript": {
                "code": "try {\n    result = riskyOperation();\n} catch (e) {\n    if (e instanceof Error) {\n        handleError(e);\n    }\n} finally {\n    cleanup();\n}",
                "description": "TypeScript try-catch with type narrowing",
            },
            "java": {
                "code": "try {\n    result = riskyOperation();\n} catch (IOException e) {\n    handleError(e);\n} finally {\n    cleanup();\n}",
                "description": "Java try-catch-finally",
            },
            "go": {
                "code": "// Go uses explicit error returns\nresult, err := riskyOperation()\nif err != nil {\n    handleError(err)\n    return\n}\ndefer cleanup()",
                "description": "Go error handling pattern",
                "notes": ["Go has no exceptions - uses error values"],
            },
            "rust": {
                "code": "// Rust uses Result type\nmatch risky_operation() {\n    Ok(result) => use_result(result),\n    Err(e) => handle_error(e),\n}",
                "description": "Rust Result pattern matching",
                "notes": ["Rust has no exceptions - uses Result<T, E>"],
            },
        },
        "related_patterns": ["error_propagation", "custom_exception"],
    },
    "error_propagation": {
        "concept": "Error propagation",
        "category": "error_handling",
        "description": "Propagating errors up the call stack",
        "examples": {
            "python": {
                "code": "def process():\n    result = risky_operation()  # Exception propagates\n    return result",
                "description": "Python auto-propagation (re-raise)",
            },
            "javascript": {
                "code": "function process() {\n    const result = riskyOperation(); // throws propagate\n    return result;\n}",
                "description": "JavaScript auto-propagation",
            },
            "typescript": {
                "code": "function process(): Result {\n    const result = riskyOperation(); // throws propagate\n    return result;\n}",
                "description": "TypeScript auto-propagation",
            },
            "java": {
                "code": "public Result process() throws IOException {\n    return riskyOperation();\n}",
                "description": "Java checked exception declaration",
            },
            "go": {
                "code": "func process() (Result, error) {\n    result, err := riskyOperation()\n    if err != nil {\n        return nil, err\n    }\n    return result, nil\n}",
                "description": "Go explicit error return",
            },
            "rust": {
                "code": "fn process() -> Result<MyResult, Error> {\n    let result = risky_operation()?; // ? operator\n    Ok(result)\n}",
                "description": "Rust ? operator for propagation",
            },
        },
        "related_patterns": ["try_catch", "custom_exception"],
    },
    # -------------------------------------------------------------------------
    # Async Patterns
    # -------------------------------------------------------------------------
    "async_await": {
        "concept": "Async/await pattern",
        "category": "async",
        "description": "Asynchronous function with await",
        "examples": {
            "python": {
                "code": "async def fetch_data():\n    response = await http_client.get(url)\n    return response.json()",
                "description": "Python asyncio async/await",
            },
            "javascript": {
                "code": "async function fetchData() {\n    const response = await fetch(url);\n    return response.json();\n}",
                "description": "JavaScript async/await",
            },
            "typescript": {
                "code": "async function fetchData(): Promise<Data> {\n    const response = await fetch(url);\n    return response.json();\n}",
                "description": "TypeScript async with Promise type",
            },
            "java": {
                "code": "public CompletableFuture<Data> fetchData() {\n    return httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString())\n        .thenApply(response -> parseJson(response.body()));\n}",
                "description": "Java CompletableFuture",
            },
            "go": {
                "code": "// Go uses goroutines and channels\nfunc fetchData() <-chan Data {\n    ch := make(chan Data)\n    go func() {\n        resp, _ := http.Get(url)\n        data := parseJson(resp.Body)\n        ch <- data\n    }()\n    return ch\n}",
                "description": "Go goroutine with channel",
            },
            "rust": {
                "code": "async fn fetch_data() -> Result<Data, Error> {\n    let response = client.get(url).await?;\n    let data = response.json().await?;\n    Ok(data)\n}",
                "description": "Rust async/await",
            },
        },
        "related_patterns": ["promise", "callback", "concurrent_execution"],
    },
    "promise": {
        "concept": "Promise/Future",
        "category": "async",
        "description": "Promise-based asynchronous operation",
        "examples": {
            "python": {
                "code": 'import asyncio\n\nasync def operation():\n    return "result"\n\n# Create task (like Promise)\ntask = asyncio.create_task(operation())\nresult = await task',
                "description": "Python asyncio Task",
            },
            "javascript": {
                "code": "const promise = new Promise((resolve, reject) => {\n    if (success) {\n        resolve(result);\n    } else {\n        reject(error);\n    }\n});\n\npromise.then(result => console.log(result));",
                "description": "JavaScript Promise",
            },
            "typescript": {
                "code": "const promise: Promise<string> = new Promise((resolve, reject) => {\n    if (success) {\n        resolve(result);\n    } else {\n        reject(error);\n    }\n});",
                "description": "TypeScript typed Promise",
            },
            "java": {
                "code": "CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {\n    return computeResult();\n});\n\nfuture.thenAccept(result -> System.out.println(result));",
                "description": "Java CompletableFuture",
            },
            "rust": {
                "code": '// Rust uses Future trait\nasync fn operation() -> String {\n    "result".to_string()\n}\n\n// Spawn and await\nlet future = operation();\nlet result = future.await;',
                "description": "Rust Future",
            },
        },
        "related_patterns": ["async_await", "callback"],
    },
    # -------------------------------------------------------------------------
    # Class/OOP Patterns
    # -------------------------------------------------------------------------
    "class_definition": {
        "concept": "Class definition",
        "category": "classes",
        "description": "Basic class with constructor and methods",
        "examples": {
            "python": {
                "code": "class Person:\n    def __init__(self, name: str, age: int):\n        self.name = name\n        self.age = age\n\n    def greet(self) -> str:\n        return f'Hello, {self.name}'",
                "description": "Python class with type hints",
            },
            "javascript": {
                "code": "class Person {\n    constructor(name, age) {\n        this.name = name;\n        this.age = age;\n    }\n\n    greet() {\n        return `Hello, ${this.name}`;\n    }\n}",
                "description": "JavaScript ES6 class",
            },
            "typescript": {
                "code": "class Person {\n    constructor(\n        public name: string,\n        public age: number\n    ) {}\n\n    greet(): string {\n        return `Hello, ${this.name}`;\n    }\n}",
                "description": "TypeScript class with parameter properties",
            },
            "java": {
                "code": 'public class Person {\n    private String name;\n    private int age;\n\n    public Person(String name, int age) {\n        this.name = name;\n        this.age = age;\n    }\n\n    public String greet() {\n        return "Hello, " + name;\n    }\n}',
                "description": "Java class",
            },
            "go": {
                "code": 'type Person struct {\n    Name string\n    Age  int\n}\n\nfunc NewPerson(name string, age int) *Person {\n    return &Person{Name: name, Age: age}\n}\n\nfunc (p *Person) Greet() string {\n    return "Hello, " + p.Name\n}',
                "description": "Go struct with constructor function and methods",
            },
            "rust": {
                "code": 'struct Person {\n    name: String,\n    age: u32,\n}\n\nimpl Person {\n    fn new(name: String, age: u32) -> Self {\n        Person { name, age }\n    }\n\n    fn greet(&self) -> String {\n        format!("Hello, {}", self.name)\n    }\n}',
                "description": "Rust struct with impl block",
            },
        },
        "related_patterns": ["inheritance", "interface", "abstract_class"],
    },
    "interface": {
        "concept": "Interface/Protocol",
        "category": "classes",
        "description": "Interface or protocol definition",
        "examples": {
            "python": {
                "code": "from abc import ABC, abstractmethod\n\nclass Greeter(ABC):\n    @abstractmethod\n    def greet(self) -> str:\n        pass",
                "description": "Python ABC (Abstract Base Class)",
            },
            "javascript": {
                "code": "// JavaScript has no native interfaces\n// Use JSDoc for documentation\n/**\n * @interface\n * @property {function(): string} greet\n */",
                "description": "JavaScript uses duck typing",
            },
            "typescript": {
                "code": "interface Greeter {\n    greet(): string;\n}",
                "description": "TypeScript interface",
            },
            "java": {
                "code": "public interface Greeter {\n    String greet();\n}",
                "description": "Java interface",
            },
            "go": {
                "code": "type Greeter interface {\n    Greet() string\n}",
                "description": "Go interface (implicit implementation)",
            },
            "rust": {
                "code": "trait Greeter {\n    fn greet(&self) -> String;\n}",
                "description": "Rust trait",
            },
        },
        "related_patterns": ["class_definition", "abstract_class"],
    },
}

# =============================================================================
# Semantic Search Patterns
# =============================================================================

SEMANTIC_PATTERNS: Dict[str, Dict[str, str]] = {
    "function_with_error_handling": {
        "description": "Function that includes error handling",
        "python": "def $FUNC($ARGS):\n    try:\n        $BODY\n    except $ERR:\n        $HANDLER",
        "javascript": "function $FUNC($ARGS) {\n    try {\n        $BODY\n    } catch ($ERR) {\n        $HANDLER\n    }\n}",
        "typescript": "function $FUNC($ARGS): $RET {\n    try {\n        $BODY\n    } catch ($ERR) {\n        $HANDLER\n    }\n}",
    },
    "async_function": {
        "description": "Asynchronous function",
        "python": "async def $FUNC($ARGS):\n    $BODY",
        "javascript": "async function $FUNC($ARGS) {\n    $BODY\n}",
        "typescript": "async function $FUNC($ARGS): Promise<$RET> {\n    $BODY\n}",
    },
    "class_with_constructor": {
        "description": "Class with constructor",
        "python": "class $CLASS:\n    def __init__(self, $ARGS):\n        $BODY",
        "javascript": "class $CLASS {\n    constructor($ARGS) {\n        $BODY\n    }\n}",
        "typescript": "class $CLASS {\n    constructor($ARGS) {\n        $BODY\n    }\n}",
        "java": "public class $CLASS {\n    public $CLASS($ARGS) {\n        $BODY\n    }\n}",
    },
    "api_route_handler": {
        "description": "API route handler function",
        "python": "@app.route($PATH)\ndef $HANDLER($ARGS):\n    $BODY",
        "javascript": "app.$METHOD($PATH, ($REQ, $RES) => {\n    $BODY\n});",
        "typescript": "app.$METHOD($PATH, ($REQ: Request, $RES: Response) => {\n    $BODY\n});",
    },
    "test_function": {
        "description": "Test function",
        "python": "def test_$NAME($ARGS):\n    $BODY",
        "javascript": "test($DESC, () => {\n    $BODY\n});",
        "typescript": "test($DESC, () => {\n    $BODY\n});",
    },
}

# =============================================================================
# Type Mappings for Conversion
# =============================================================================

TYPE_MAPPINGS: Dict[str, Dict[str, str]] = {
    "python_to_typescript": {
        "str": "string",
        "int": "number",
        "float": "number",
        "bool": "boolean",
        "None": "null",
        "list": "Array",
        "List": "Array",
        "dict": "Record",
        "Dict": "Record",
        "Any": "any",
        "Optional": "| undefined",
        "Union": "|",
        "Tuple": "[...]",
    },
    "python_to_javascript": {
        "str": "string",
        "int": "number",
        "float": "number",
        "bool": "boolean",
        "None": "null",
        "list": "Array",
        "dict": "Object",
    },
    "typescript_to_python": {
        "string": "str",
        "number": "float",
        "boolean": "bool",
        "null": "None",
        "undefined": "None",
        "any": "Any",
        "Array": "List",
        "Record": "Dict",
        "void": "None",
    },
    "java_to_kotlin": {
        "String": "String",
        "int": "Int",
        "Integer": "Int",
        "long": "Long",
        "Long": "Long",
        "double": "Double",
        "Double": "Double",
        "float": "Float",
        "Float": "Float",
        "boolean": "Boolean",
        "Boolean": "Boolean",
        "void": "Unit",
        "Object": "Any",
        "List": "List",
        "Map": "Map",
        "Set": "Set",
    },
}


def get_pattern(pattern_id: str) -> Dict[str, Any] | None:
    """Get a pattern by its ID.

    Args:
        pattern_id: Pattern identifier

    Returns:
        Pattern dictionary or None if not found
    """
    return PATTERN_DATABASE.get(pattern_id)


def search_patterns(query: str, category: str | None = None) -> List[Dict[str, Any]]:
    """Search patterns by query and optional category.

    Args:
        query: Search query (matches concept, description)
        category: Optional category filter

    Returns:
        List of matching patterns
    """
    results = []
    query_lower = query.lower()

    for pattern_id, pattern in PATTERN_DATABASE.items():
        if category and pattern.get("category") != category:
            continue

        # Match against concept, description, and pattern_id
        if (
            query_lower in pattern.get("concept", "").lower()
            or query_lower in pattern.get("description", "").lower()
            or query_lower in pattern_id.lower()
        ):
            results.append({"pattern_id": pattern_id, **pattern})

    return results


def get_equivalents(
    pattern_id: str,
    source_language: str | None = None,
    target_languages: List[str] | None = None,
) -> Dict[str, Any] | None:
    """Get equivalent patterns across languages.

    Args:
        pattern_id: Pattern identifier
        source_language: Optional source language to highlight
        target_languages: Optional list of target languages to filter

    Returns:
        Pattern equivalence data or None if not found
    """
    pattern = PATTERN_DATABASE.get(pattern_id)
    if not pattern:
        return None

    examples = pattern.get("examples", {})

    if target_languages:
        examples = {lang: ex for lang, ex in examples.items() if lang in target_languages}

    return {
        "pattern_id": pattern_id,
        "concept": pattern.get("concept"),
        "category": pattern.get("category"),
        "description": pattern.get("description"),
        "source_language": source_language,
        "examples": examples,
        "related_patterns": pattern.get("related_patterns", []),
    }


def get_type_mapping(from_lang: str, to_lang: str) -> Dict[str, str]:
    """Get type mappings between two languages.

    Args:
        from_lang: Source language
        to_lang: Target language

    Returns:
        Dictionary of type mappings
    """
    key = f"{from_lang}_to_{to_lang}"
    return TYPE_MAPPINGS.get(key, {})
