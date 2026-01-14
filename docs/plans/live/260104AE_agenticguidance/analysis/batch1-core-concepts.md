# Batch 1: Core Meta-Definitions Audit

**Source:** `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/`
**Audit Date:** 2026-01-11
**Scope:** Core meta-definitions that define the vocabulary and concepts of the guidance system itself

---

## Summary Table

| File | Classification | Actual Type | Usage | Redundancy | Priority | Recommended Action |
|------|---------------|-------------|-------|------------|----------|-------------------|
| definition.yml | Meta-Definition | Definition + Guideline hybrid | 10 refs | Low | Medium | Reclassify prescriptive parts |
| guideline.yml | Meta-Definition | Definition + Guideline hybrid | 10 refs | Low | Medium | Reclassify prescriptive parts |
| example.yml | Meta-Definition | Definition + Guideline hybrid | 2 refs | Low | Medium | Reclassify prescriptive parts |
| path.yml | Definition | Pure Definition | 35 refs | Medium | Low | Keep as-is |
| fence.yml | Definition | Pure Definition | 36 refs | High | Medium | Merge with signpost.yml |
| signpost.yml | Definition | Pure Definition | 23 refs | High | Medium | Merge with fence.yml |
| guidance.yml | Definition | Definition (detailed) | 20 refs | Medium | High | Consolidate with guidance-artifacts.yml |
| friction.yml | Definition | Definition + Examples | 27 refs | Low | Low | Keep as-is |
| steps.yml | Definition | Definition (well-structured) | 2 refs | Low | Low | Keep as-is |
| escalation.yml | Definition | Guideline (mislabeled) | 15 refs | Low | High | Move to guidelines/ |
| guidance-artifacts.yml | Definition | Specification/Reference | 22 refs | Medium | High | Consolidate with guidance.yml |

---

## Detailed Analysis

### 1. definition.yml

**Content Summary:**
```yaml
definition: |
  A definition names a concept and explains what it means.

  Use a definition when:
  - A term is reused across agents, plans, or processes
  - The goal is shared understanding ("what is X?")
  - The content should be stable, concise, and broadly applicable

  Definitions should:
  - Be descriptive (what something is), not prescriptive (what to do)
  - Avoid project-specific details
  - Prefer references to examples
```

**Classification Analysis:**
- **Lines 1-2:** Pure definition ("A definition names a concept...")
- **Lines 4-7:** Guideline ("Use a definition when...")
- **Lines 9-12:** Guideline ("Definitions should...")

**Assessment:**
This is a **hybrid** - the first statement is definitional, but the "Use when" and "Should" sections are prescriptive guidelines. This creates a self-contradiction: it says definitions should be descriptive, not prescriptive, yet includes prescriptive content.

**Usage:** Referenced in 10 files, primarily in planner and teacher agent inputs.

**Recommendation:**
- **Split into two files:**
  - Keep `definitions/definition.yml` with only lines 1-2 (the actual definition)
  - Create `guidelines/definition-authoring.yml` with the "Use when" and "Should" content
- **Priority:** Medium - affects consistency but not blocking

---

### 2. guideline.yml

**Content Summary:**
```yaml
guideline: |
  A guideline is a reusable rule-of-thumb that shapes behavior and decisions.

  Use a guideline when:
  - You need consistent behavior across many tasks or agents ("how to act")
  - You want guardrails (do/don't), quality bars, or safety constraints
  - The content is broadly applicable and can be composed with other guidelines

  Guidelines should:
  - Be actionable and testable where possible
  - Include the minimal rationale needed to avoid misapplication
  - Avoid long examples inline; reference example files instead
  - Avoid duplicating definitions (link to definitions for "what it is")
```

**Classification Analysis:**
- **Lines 1-2:** Pure definition ("A guideline is a reusable rule-of-thumb...")
- **Lines 4-7:** Guideline ("Use a guideline when...")
- **Lines 9-13:** Guideline ("Guidelines should...")

**Assessment:**
Same hybrid pattern as definition.yml. The definitional part is clean, but the authoring guidance is prescriptive.

**Usage:** Referenced in 10 files.

**Recommendation:**
- **Split into two files:**
  - Keep `definitions/guideline.yml` with only the definition
  - Create `guidelines/guideline-authoring.yml` with the prescriptive content
- **Priority:** Medium

---

### 3. example.yml

**Content Summary:**
```yaml
example: |
  An example is a concrete illustration of a concept, pattern, or best practice.

  Use an example when:
  - You need to show what good/bad looks like
  - Abstract definitions or guidelines need concrete demonstrations
  - Agents benefit from seeing before/after patterns

  Examples should:
  - Be concrete and specific (real scenarios, not FooBar placeholders)
  - Demonstrate the concept in action, not just describe it
  - Be copyable/adaptable for similar situations
  - Reference the definition or guideline they illustrate
```

**Classification Analysis:**
Same hybrid pattern as definition.yml and guideline.yml.

**Assessment:**
Completes the "meta-trilogy" of definition/guideline/example. All three follow the same pattern and should be treated consistently.

**Usage:** Only 2 references - relatively low usage suggests this may be under-utilized or agents discover examples organically.

**Recommendation:**
- **Split consistently** with definition.yml and guideline.yml
- **Consider:** Creating a single consolidated `guidelines/authoring-guidance-assets.yml` that covers all three
- **Priority:** Medium (consistency with the other two)

---

### 4. path.yml

**Content Summary:**
```yaml
The set of things an agent reads that determines what it does next:
- Processes (`process.yml`, `processes/*.yml`)
- Plans (`docs/plans/**`)
- Folder structure + discoverable docs (manifests, READMEs)

Clear paths -> linear progress. Unclear paths -> guessing, loops, questions.
```

**Classification Analysis:**
- Pure definition with a clear "what is X" structure
- Lists components that constitute a "path"
- Final line is an observation/axiom, not a prescription

**Assessment:**
This is a **clean definition**. It names a concept ("path") and explains what it encompasses. The final line states a consequence rather than instructing behavior.

**Usage:** High usage (35 references) - core concept in the system.

**Recommendation:**
- **Keep as-is** - well-formed definition
- **Priority:** Low (no action needed)

---

### 5. fence.yml

**Content Summary:**
```yaml
Guardrails that prevent wrong work:
- Success criteria that are measurable
- Validation/audit steps appropriate to risk
- Constraints that remove ambiguity (inputs, scope boundaries)
```

**Classification Analysis:**
- Brief definition with examples
- Lists components that constitute a "fence"
- No prescriptive "should do" content

**Assessment:**
Clean definition, but **overlaps conceptually with signpost.yml**. Both are about "agent navigation aids" - signposts point the way, fences prevent wrong turns.

**Usage:** 36 references - heavily used.

**Redundancy Analysis:**
- `fence.yml`: Focuses on constraints/guardrails
- `signpost.yml`: Focuses on examples/definitions/guidance pointing the way
- Together they form a conceptual pair but are split across two files

**Recommendation:**
- **Consider merging** into a single `navigation-aids.yml` that covers both concepts
- Alternatively, keep separate but add explicit cross-references
- **Priority:** Medium (reduces fragmentation)

---

### 6. signpost.yml

**Content Summary:**
```yaml
A teaching artifact that helps agents choose correctly:
- Examples (`examples/*.yml`): show the pattern with realistic values
- Definitions (`definitions.yml`): name concepts + rules of thumb
- Plan guidance: task-specific context + file paths
```

**Classification Analysis:**
- Pure definition listing what signposts are
- Enumerates the types of signposts

**Assessment:**
Clean definition. See fence.yml analysis for redundancy discussion.

**Usage:** 23 references.

**Recommendation:**
- **Merge with fence.yml** into consolidated `navigation-aids.yml` or `agent-guidance-types.yml`
- The pair (path + fence + signpost) forms the "agent navigation vocabulary" and could be consolidated
- **Priority:** Medium

---

### 7. guidance.yml

**Content Summary:**
```yaml
Guidance provides instructions for the orchestration agent to generate prompts...
It contains the context, scope, and specific instructions...

Guidance should include:
- Context about what needs to be done and why
- Specific instructions for the work
- Important details or constraints
- Process file paths

Guidance can include file paths from inputs...

Guidance should NOT include:
- High-level objectives (belong at plan level)
- Completion criteria (belong in success criteria)
- Process steps already in agent processes

Be specific and detailed - this guidance becomes the target agent's instructions.

The orchestration agent reads guidance from plans and generates appropriate prompts.
```

**Classification Analysis:**
- **Lines 1-2:** Definition (what guidance is)
- **Lines 4-9:** Guideline ("should include")
- **Lines 11:** Observation
- **Lines 13-17:** Guideline ("should NOT include")
- **Lines 19-21:** Explanation/context

**Assessment:**
**Significant hybrid** - mixes definition with substantial prescriptive content. The "should include" and "should NOT include" sections are clearly guidelines for authoring guidance.

**Redundancy with guidance-artifacts.yml:**
Both files discuss where guidance goes and what it should contain. `guidance.yml` focuses on content, `guidance-artifacts.yml` focuses on file locations. There's conceptual overlap.

**Usage:** 20 references.

**Recommendation:**
- **High priority consolidation needed**
- Split definitional content from prescriptive content
- Merge with guidance-artifacts.yml into a coherent structure:
  - `definitions/guidance.yml` - What guidance is (2-3 lines)
  - `guidelines/authoring-guidance.yml` - How to write guidance
  - `definitions/guidance-locations.yml` OR integrate locations into the guideline
- **Priority:** High (confusing split between two files)

---

### 8. friction.yml

**Content Summary:**
```yaml
Friction is anything that increases the cognitive load of agents, increases the number of
steps they need to take, or confuses them into doing the wrong thing.

Examples:
- Outdated documentation (wrong paths, missing steps)
- Incorrect file paths in guidance or processes
- Hidden prerequisites (assumed env vars, assumed installed tools)
- Late validation (discovering problems only after large edits)

When friction is discovered, prefer fixing the source (guidance/process/docs) so future agents
do not repeat the same failure.
```

**Classification Analysis:**
- **Lines 1-2:** Pure definition (what friction is)
- **Lines 4-8:** Examples (illustrating the concept)
- **Lines 10-11:** Guideline (what to do when friction is found)

**Assessment:**
Mostly definitional with embedded examples, which is acceptable. The final sentence is prescriptive but is a single actionable principle that naturally follows from the definition.

**Usage:** 27 references - well-used concept.

**Recommendation:**
- **Keep as-is** - the embedded examples are valuable, and the single prescriptive line is a reasonable exception
- Could optionally extract the final line to a guideline, but low value
- **Priority:** Low (acceptable as-is)

---

### 9. steps.yml

**Content Summary:**
```yaml
steps: |
  Steps describe actions to perform - the process, not the outcome.

  A step is:
  - An action an agent takes ("Run tests", "Read file X")
  - Part of a sequence toward a goal
  - Focused on what to do, not what success looks like

  Steps vs Success Criteria:
  - Step: "Run the test suite"
  - Success Criteria: "All tests pass with exit code 0"

  Good steps:
  - Specific and actionable
  - Reference concrete files or commands
  - Ordered logically (dependencies respected)

  Bad steps:
  - Vague ("Make it work")
  - Outcome-focused ("Ensure tests pass") - this is criteria, not a step
  - Missing context on what to act upon

  Related: success-criteria.yml, guidance.yml
```

**Classification Analysis:**
- **Lines 1-7:** Definition (what a step is)
- **Lines 9-11:** Comparative example (clarifying the concept)
- **Lines 13-21:** Quality guidance (good/bad patterns)

**Assessment:**
Well-structured definition with embedded quality guidance. The "good/bad" section is prescriptive but serves to clarify the concept through contrast. Similar pattern to success-criteria.yml (which I also read).

**Usage:** Only 2 references - surprisingly low given importance.

**Recommendation:**
- **Keep as-is** - well-formed, useful for teaching
- May want to reference this more broadly in agent inputs
- **Priority:** Low (no restructuring needed)

---

### 10. escalation.yml

**Content Summary:**
```yaml
escalation: |
    When confidence is low, escalate instead of guessing.

    Triggers:
    - Missing required inputs
    - Ambiguous instructions or conflicting requirements
    - Repeated failures (e.g., 3 attempts without progress)
```

**Classification Analysis:**
- **Line 2:** Prescriptive rule ("escalate instead of guessing")
- **Lines 4-7:** Trigger conditions (when to apply the rule)

**Assessment:**
This is **100% a guideline, not a definition**. It does not answer "what is escalation?" but rather "when should you escalate?" It belongs in `guidelines/`.

The content is a behavioral rule with clear triggers - exactly what guidelines are for.

**Usage:** 15 references.

**Recommendation:**
- **Move to `guidelines/escalation.yml`**
- Optionally create a true definition: "Escalation is the act of pausing work and requesting human input when an agent cannot proceed confidently."
- **Priority:** High (clear misclassification)

---

### 11. guidance-artifacts.yml

**Content Summary:**
```yaml
guidance_artifacts:
  description: |
    Put information where agents will actually read it.
    This file defines where different types of agent guidance should be stored.

  process_files:
    standard_format:
      format: "process.yml"
      structure: [goal, loop_context, inputs, outputs, steps, guidelines]
      when_to_use: "Use process.yml for all single-agent workflows..."
      examples: [...]
    alternative_format:
      format: "process.mmd"
      description: "Mermaid flowchart format..."
      when_to_use: "Only use process.mmd for complex multi-agent orchestration..."
      requirements: [...]
      rationale: "..."

  other_artifacts:
    processes_folder: {path, purpose}
    definitions: {path, purpose}
    guidelines: {path, purpose}
    examples: {path, purpose}
    manifest: {path, purpose}
```

**Classification Analysis:**
This is a **specification/reference document** rather than a simple definition. It:
- Defines where artifacts should be stored (reference)
- Prescribes format choices (guideline)
- Lists examples and structure (specification)

**Assessment:**
Too large and complex for the definitions folder. It's more of a "reference" or "specification" document. The content is valuable but misplaced.

**Redundancy with guidance.yml:**
- `guidance.yml`: What guidance content should contain
- `guidance-artifacts.yml`: Where guidance artifacts go

These should be consolidated or clearly cross-referenced.

**Usage:** 22 references.

**Recommendation:**
- **Consolidate with guidance.yml** into a coherent authoring guide
- Consider moving to a `specifications/` or `references/` folder
- At minimum, split:
  - `definitions/guidance-artifacts.yml` -> brief definition of artifact types
  - `specifications/process-file-format.yml` -> the detailed format spec
- **Priority:** High (oversized for definitions folder, overlaps with guidance.yml)

---

## Recommendations Summary

### High Priority Actions

1. **Move escalation.yml to guidelines/**
   - File: `definitions/escalation.yml` -> `guidelines/escalation.yml`
   - Reason: Content is 100% prescriptive (when/how to act), not definitional
   - Optionally create a true definition to replace it

2. **Consolidate guidance.yml + guidance-artifacts.yml**
   - Current state: Two files with overlapping concerns
   - Target state:
     - `definitions/guidance.yml` - Brief definition (what guidance is)
     - `guidelines/authoring-guidance.yml` - How to write guidance, what to include/exclude
     - `specifications/process-file-format.yml` - Detailed format specifications
   - Reason: Reduces confusion, respects definition vs guideline distinction

### Medium Priority Actions

3. **Split meta-definitions (definition.yml, guideline.yml, example.yml)**
   - Current: Each is a hybrid of definition + authoring guidance
   - Target: Pure definitions + consolidated `guidelines/authoring-assets.yml`
   - Reason: Self-consistency (these files violate their own principles)

4. **Consolidate fence.yml + signpost.yml**
   - Option A: Merge into `definitions/navigation-aids.yml`
   - Option B: Keep separate with explicit cross-references
   - Reason: Conceptually paired, reduces fragmentation

### Low Priority Actions

5. **Keep as-is:**
   - `path.yml` - Clean definition, high usage
   - `friction.yml` - Acceptable hybrid with valuable examples
   - `steps.yml` - Well-structured, useful teaching content

---

## Proposed File Structure After Cleanup

```
definitions/
  definition.yml          # Brief: "A definition names a concept..."
  guideline.yml           # Brief: "A guideline is a rule-of-thumb..."
  example.yml             # Brief: "An example is a concrete illustration..."
  path.yml                # Keep as-is
  fence.yml               # Merge with signpost or keep with cross-ref
  signpost.yml            # Merge with fence or keep with cross-ref
  guidance.yml            # Brief definition only
  friction.yml            # Keep as-is
  steps.yml               # Keep as-is

guidelines/
  escalation.yml          # Moved from definitions
  authoring-assets.yml    # New: consolidated authoring guidance for definition/guideline/example
  authoring-guidance.yml  # New: how to write plan guidance (from guidance.yml)

specifications/
  process-file-format.yml # New: detailed process.yml structure (from guidance-artifacts.yml)
```

---

## Metrics

| Category | Count |
|----------|-------|
| Files Audited | 11 |
| Keep As-Is | 3 |
| Reclassify (move to guidelines) | 1 |
| Split (separate definition from guideline) | 4 |
| Merge (consolidate related files) | 2 |
| Total Actions | 7 |

---

## Next Steps

1. Create implementation plan with specific file changes
2. Identify dependencies (which agents reference these files)
3. Update agent inputs after restructuring
4. Validate no broken references post-cleanup
