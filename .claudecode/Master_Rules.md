# MASTER PLAN AMENDMENT: HARD SOVEREIGNTY LOCK-IN
> Status: Critical Enforcement. Overrides existing Step 2 & Step 4 guidelines.

## 1. Eliminate LLM from Pre-Flight Filter Checks
You are PROHIBITED from using `await client.chat(...)` or ANY LLM interaction within the `ZeroErrorFilter` or the `UnitStandardizer` to perform verification.
LLMs are probabilistic; Zenith Kernel must be DETERMINISTIC.

## 2. Hardcode Local Mathematical Verification (Step-by-Step for Claude Code)

### Step A: Dynamic Registry Implementation
* Instead of static values in a YAML file, create `PhysicsQuantityRegistry` using NumPy's C++ back-end. Each registered physical quantity (L_D, E_a, flux) must be stored as a **Structural Tensor (an unmodifiable array holding normalized values, uncertainty, and SI dimensional tuple (M,L,T,I))**. Use `MappingProxyType` to enforce runtime immutability.

### Step B: The Deterministic `SIStandardizer`
* Build `UnitStandardizer` solely using Python's `re` for tokenization and `SciPy` for dimensional analysis and scaling. It must return a deterministic result (e.g., matching a predefined tuple). If it fails to tokenize a unique compound (e.g., J/(mol·K)), it must raise a `DimensionMissingError`, triggering the meta-metadata debate in Agent B, which then must rely on a hard Semantic Scholar reputation lookup (pre-defined Python function), NOT an LLM.

### Step C: The Rigid `ConservationFilter`
* Within `ZeroErrorFilter`, the fundamental law validators (like `_check_energy_conservation`) must be implemented as raw Python/C++ mathematical functions. They must receive Structural Tensors (NumPy arrays) of (value, scale, dim) directly. They will apply strict linear algebra for conservation validation against the local `PhysicsQuantityRegistry`. Any deviation outside the rigid `TOLERANCE_RIGID` (e.g., 1e-6) must result in a DETERMINISTIC `law_violation` verdict, with NO LLM REASONING allowed before rejection.

### Step D: Redefine the Role of Cloud Kimi k2.6
* Cloud NIM (Kimi k2.6) is demoted from "Brain" to "Reasoning Speculator." It receives ONLY natural language summaries and Structural Tensors for high-dimensional thought. It never handlesraw, raw data from tools. This makes it an L2 Intelligence consumer, while L3 is rigidly enforced by the deterministic Local Kernel (Nexus-Root).