---
name: acceptance-criteria
description: PROACTIVELY use when PM persona is defining feature requirements or acceptance criteria. Apply when writing features/*.md files, reviewing acceptance criteria for testability, or converting user needs into measurable conditions. Use to ensure acceptance criteria are testable and avoid unmeasurable patterns.
---

# Acceptance Criteria Guidelines

This skill provides detailed guidance for writing testable, measurable acceptance criteria in feature specifications.

## Core Principle

Write testable, measurable acceptance criteria that can be validated objectively. Avoid patterns that cannot be verified or measured.

## Unmeasurable Patterns (AVOID)

These patterns appear concrete but cannot be objectively validated:

- ✗ **Percentages of unknown totals**: "85% of entities" when total count is unknowable
  - Problem: You can't verify 85% if you don't know the total number
  - Why it's tempting: Sounds precise and quantitative

- ✗ **Vague qualitative claims**: "users feel confident", "high quality", "most cases"
  - Problem: Subjective interpretation, no clear pass/fail
  - Why it's tempting: Captures important user experience goals

- ✗ **Unmeasurable coverage**: "comprehensive", "complete", "thorough"
  - Problem: No way to determine when you've reached "comprehensive"
  - Why it's tempting: Expresses desire for completeness

- ✗ **Subjective assessments**: "intuitive", "easy to use", "clear"
  - Problem: Different users have different standards for "intuitive"
  - Why it's tempting: Represents important UX goals

- ✗ **Time-based claims without baseline**: "fast", "quick", "responsive"
  - Problem: Fast compared to what? What's the threshold?
  - Why it's tempting: Performance matters to users

- ✗ **Unverifiable negatives**: "no confusion", "no questions", "no complaints"
  - Problem: Can't prove a negative; one exception doesn't falsify the claim
  - Why it's tempting: Expresses desired absence of problems

## Measurable Patterns (USE THESE)

These patterns can be objectively validated:

- ✓ **Pattern coverage**: List specific patterns that must be implemented
  - Example: "Recognizes character mentions in these formats: 'Character:', '[Character]', 'Character said'"
  - Why it works: Enumerated list of specific cases to test

- ✓ **Observable behaviors**: User can do X, system shows Y
  - Example: "When user clicks 'Generate', Story Bible displays a preview panel"
  - Why it works: Clear input and expected output

- ✓ **Specific thresholds with measurable totals**: >99% of 100 test cases, <10 errors per 1000 requests
  - Example: "Passes 99 of 100 test cases in the acceptance test suite"
  - Why it works: Known denominator makes percentage verifiable

- ✓ **Testable against known data**: Test story with known entity counts
  - Example: "When run on test-story.md (which contains 5 characters, 3 locations), extracts all 5 characters and all 3 locations"
  - Why it works: Ground truth data enables verification

- ✓ **User-reported metrics with tracking**: Track support requests and response times
  - Example: "Track Story Bible generation errors in telemetry; review error rate monthly"
  - Why it works: Measurable data collection with review process

## Soft Goals vs Acceptance Criteria

Some goals are directional but not testable. These are valuable but must be clearly separated from acceptance criteria.

**When to use Soft Goals**:
- Qualitative user experience aspirations
- Directional improvements without clear thresholds
- Long-term quality goals that evolve over time
- Guiding principles for design decisions

**How to format Soft Goals**:
- Label explicitly as "Qualitative Indicators" or "Soft Goals" (not acceptance criteria)
- Format: "Soft goal: Writers find X helpful for Y"
- Keep separate from testable acceptance criteria in feature specs
- Use to guide design decisions, not to gate completion

**Examples**:

Bad (mixing soft goals with acceptance criteria):
```
Acceptance Criteria:
- Story Bible is comprehensive (what does this mean?)
- Users feel confident using the tool (how do we measure?)
- Most edge cases are handled (which ones? how many?)
```

Good (separate testable criteria from soft goals):
```
Acceptance Criteria:
- Recognizes character mentions in formats: 'Name:', '[Name]', 'Name said'
- Extracts locations mentioned with 'in [Location]' or 'at [Location]'
- Passes 95 of 100 test cases in acceptance test suite

Soft Goals:
- Writers find Story Bible helpful for tracking continuity
- Tool surfaces important story details efficiently
- (Use these to guide design, not to gate completion)
```

## Writing Process

When defining acceptance criteria:

1. **Start with the user behavior**: What does the user do? What do they see?
2. **Identify verifiable conditions**: Can this be tested? What's the pass/fail threshold?
3. **Challenge unmeasurable language**: If you wrote "comprehensive", list the specific patterns instead
4. **Separate soft goals**: If it's a qualitative aspiration, label it explicitly as a soft goal
5. **Create test cases**: For each criterion, imagine the test that would verify it
6. **Review with Developer**: Can these be turned into automated tests?

## Common Pitfalls

**Pitfall**: "System handles 90% of character mentions"
- Problem: 90% of what total? Unknown denominator
- Fix: "System handles these character mention patterns: [list patterns]"

**Pitfall**: "Users can easily generate Story Bibles"
- Problem: "Easily" is subjective
- Fix: "User clicks 'Generate' button, Story Bible displays within 2 seconds"

**Pitfall**: "Tool provides comprehensive character tracking"
- Problem: What makes it "comprehensive"?
- Fix: "Tracks character names, first appearance, relationships, and attributes listed in story"

**Pitfall**: "Most writers find the tool intuitive"
- Problem: "Most" of what sample? "Intuitive" is subjective
- Fix: Make this a soft goal OR "User can generate first Story Bible without reading documentation"

## Review Checklist

Before finalizing acceptance criteria, verify:

- [ ] Each criterion has a clear pass/fail condition
- [ ] Each criterion can be turned into an automated test
- [ ] Percentages have known denominators
- [ ] Qualitative language is moved to soft goals
- [ ] Coverage claims list specific patterns
- [ ] Time-based claims have specific thresholds
- [ ] Negative claims are reframed as positive behaviors

If any criterion fails this checklist, revise or move to soft goals.
