# Zenith Refactor Plan — Amplifying Architecture

## Core Principle
K2.6 is a strong model. Don't constrain it. Give it capabilities it LACKS:
- Memory (it has none between sessions)
- OS control (it can't touch the system)
- Privacy (it sees everything we send)
- Personalization (it doesn't know the user)
- Physical constraints (it can generate impossible actions)

## What Changes

### 1. Fix the ReAct Loop (CRITICAL)
**Problem:** Current loop REWRITES messages after each tool call. Model loses history.
**Fix:** Append observations, don't rewrite. Model sees full conversation.

### 2. Native Function Calling
**Problem:** ACT:TOKEN regex parsing is fragile, wastes tokens.
**Fix:** Use OpenAI-compatible `tools=[...]` format. Codebook generates tool schemas.
**Innovation stays:** Codebook defines WHAT tools exist, risk levels, parameters.

### 3. User Profile System
**Problem:** Model doesn't know who the user is.
**Fix:** Always-inject user profile into system prompt. Model adapts style automatically.

### 4. Physical Intuition as Structure
**Problem:** Current "physical intuition" is keyword matching that returns a string hint.
**Fix:** Hard constraints that VALIDATE actions before execution. Real physics rules.

### 5. Intelligent Memory Injection
**Problem:** Dumps top_k memories into context blindly.
**Fix:** Hybrid — inject 1 high-confidence memory always. Model can request more via tool.

### 6. Active Failure Library
**Problem:** FailureLibrary exists but is passive (only logs, doesn't help).
**Fix:** Extract patterns, inject hints before tool execution.

## Priority Order
1. Fix ReAct loop + Native function calling (they're coupled) ✅ DONE
2. User profile system ✅ DONE
3. Physical intuition as structural validation ✅ DONE
4. Intelligent memory injection ✅ DONE
5. Active failure library ✅ DONE

## NOT Building (Yet)
- Subagent fan-out (needs dispatch_agent tool)
- TTS pipeline (needs audio infrastructure)
- Privacy shield (needs PII detection)
- Executive shadow (needs Gmail API)
- Self-evolution / skill templates (needs failure pattern data first)
