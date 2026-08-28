# AegisX UI Specification

## 1. Purpose

This document is the source of truth for the AegisX frontend experience.

The goal is not to make AegisX look like a collection of impressive AI features. The goal is to make one professional, trustworthy investigation workflow feel real:

**Upload → Ingest → Ask → Retrieve → Rerank → Evidence → Answer → Impact → Action → Approval → Audit**

The interface must communicate that AegisX is a serious system for evidence-backed GxP decision support.

The UI must not look "vibe coded".

---

## 2. Core Product Principle

The frontend must prioritize **working functionality over feature breadth**.

A smaller number of deeply integrated workflows is better than many disconnected screens.

The primary question behind every UI decision is:

> Does this help the user understand what AegisX found, why it believes it, what is affected, and what should happen next?

If not, the element should probably not exist.

---

## 3. Hero Workflow

The entire application should be organized around this flow:

```text
DOCUMENTS
    ↓
INGESTION
    ↓
KNOWLEDGE INDEX
    ↓
USER QUESTION
    ↓
QUERY UNDERSTANDING
    ↓
HYBRID RETRIEVAL
    ↓
RERANKING
    ↓
EVIDENCE
    ↓
GROUNDED ANSWER
    ↓
EXPLANATION
    ↓
BLAST RADIUS
    ↓
RECOMMENDED ACTION
    ↓
HUMAN APPROVAL
    ↓
AUDIT TRAIL
```

The user should be able to move through this naturally without feeling like they are switching between unrelated products.

---

# 4. Visual Direction

## 4.1 Overall Character

AegisX should feel:

- professional
- precise
- controlled
- technical
- trustworthy
- information-dense without being cluttered
- calm under pressure
- suitable for a regulated environment

It should feel closer to a **mission-control investigation workspace** than a marketing website.

## 4.2 Do Not Make It Look Vibe-Coded

Avoid:

- excessive gradients
- generic purple/blue AI aesthetics
- giant floating cards
- excessive rounded rectangles
- random glassmorphism
- huge empty dashboard areas
- meaningless statistics
- fake activity indicators
- decorative AI animations
- oversized headings
- excessive shadows
- arbitrary illustrations
- generic chatbot layouts
- pages created purely to increase feature count
- visually identical cards repeated across the application

Do not use visual decoration to compensate for missing functionality.

## 4.3 Design Language

Prefer:

- strong grid alignment
- restrained borders
- clear hierarchy
- consistent spacing
- purposeful density
- subtle elevation
- compact information panels
- clear state indicators
- precise typography
- meaningful whitespace
- restrained animation

The interface should look deliberately designed, not generated from a component template.

---

# 5. Information Architecture

The application should not expose every possible capability as a separate top-level destination.

Primary navigation should center around the actual workflow.

Recommended structure:

```text
AegisX

Command Centre
Investigate
Knowledge
Impact
Actions
Trust
```

Where appropriate, Investigation can contain:

- Copilot
- Evidence
- Investigation timeline

Knowledge contains:

- Document upload
- Ingestion status
- Sources
- Indexed knowledge

Impact contains:

- Blast Radius
- Dependency relationships

Actions contains:

- Recommendations
- Pending approvals
- Completed actions

Trust contains:

- Audit trail
- System activity
- Evidence/provenance information

Do not add additional top-level areas unless the Bible explicitly requires them.

---

# 6. Command Centre

The Command Centre is not a generic analytics dashboard.

Its purpose is to orient the user and get them into an investigation quickly.

The primary action should be obvious:

**Start an Investigation**

Secondary information can include:

- active investigations
- unresolved findings
- recent changes
- pending approvals
- knowledge source health

Do not overwhelm the page with metrics.

The user should immediately understand:

1. What needs attention?
2. What changed?
3. What can I investigate?
4. What is waiting for my decision?

---

# 7. Knowledge / Document Intake

This is a P0 feature.

The user must be able to upload supported documents.

The interface should make the ingestion process visible.

## 7.1 Upload State

Use a clear drop zone:

```text
Add Knowledge

Drop GxP documents here
or
[ Browse files ]

PDF · DOCX · CSV
```

Do not create a fake upload interaction.

## 7.2 Processing State

After upload, show actual processing:

```text
Validation Protocol.pdf

Uploading       ✓
Parsing         ✓
Structure       ✓
Chunking        ✓
Indexing        ◌
Ready           -
```

These states must correspond to real backend operations.

Do not animate fake progress independently of the backend.

## 7.3 Knowledge Source List

Each source should expose:

- filename
- document type
- version if available
- ingestion status
- date
- source metadata
- number of indexed retrieval units if available

Clicking a document should allow inspection of its extracted content/provenance.

---

# 8. Copilot

The Copilot is the front door to AegisX's investigation engine.

It must not behave like a generic chatbot.

## 8.1 Initial State

Use contextual prompts rather than an empty chat box.

Example:

```text
ASK AEGISX

Investigate your GxP environment.

[ What changed recently? ]

[ Find affected requirements ]

[ Show me the blast radius ]

[ Explain this finding ]

[ Assess the compliance impact ]
```

The suggestions must invoke real capabilities.

## 8.2 Question State

The user asks a natural-language question.

Example:

> What changed in the manufacturing system and what could it affect?

The system should visibly transition into investigation.

---

# 9. Investigation Execution View

This is one of AegisX's strongest UI opportunities.

Instead of displaying a spinner, show meaningful stages.

Example:

```text
INVESTIGATION

✓ Understanding question
✓ Searching knowledge
✓ Combining semantic and keyword evidence
✓ Reranking candidates
◌ Evaluating evidence
- Building impact relationships
- Preparing assessment
```

Only show stages that actually occur.

Never fabricate execution activity.

The user should feel that AegisX is performing a structured investigation.

---

# 10. Advanced Retrieval Visualization

The advanced retrieval pipeline is a core technical requirement.

The UI should expose it at a conceptual level without drowning the user in implementation details.

Recommended flow:

```text
Question
   ↓
Query Understanding
   ↓
Semantic Search ─────┐
                     ├── Candidate Evidence
Keyword Search ──────┘
                     ↓
                  Reranking
                     ↓
               Evidence Set
                     ↓
              Grounded Answer
```

The user should be able to inspect this through an expandable "How AegisX searched" or "Investigation trace" panel.

Show useful information such as:

- number of candidates retrieved
- retrieval methods used
- reranked evidence count
- selected evidence
- source provenance

Do not expose raw implementation details unless they help explain trust.

---

# 11. Evidence View

Evidence is central to the AegisX identity.

The answer must never be presented as an unsupported block of AI text.

A good result should look conceptually like:

```text
ASSESSMENT

The change may affect validation coverage.

WHY

The affected configuration is referenced by
Requirement R-104 and Validation Test T-22.

EVIDENCE

[ Source 01 ]
Validation Protocol
Section 4.2 · Page 17

[ Source 02 ]
Requirement Specification
R-104 · Page 31

[ Source 03 ]
Change Record
CH-019
```

Each evidence item should be inspectable.

The user should be able to distinguish:

- source evidence
- system-derived relationship
- model interpretation
- uncertainty

---

# 12. Evidence Spine

AegisX should have a recognizable evidence relationship pattern.

Conceptually:

```text
QUESTION
   ↓
EVIDENCE
   ↓
FINDING
   ↓
RELATIONSHIP
   ↓
IMPACT
   ↓
ACTION
```

The UI should make it easy to move backwards through this chain.

For example:

**Why is this requirement affected?**

→ show relationship

→ show source evidence

→ show document section

This should be one of the application's strongest interaction patterns.

---

# 13. Blast Radius

Blast Radius is a primary differentiator.

It should answer:

> If this change or finding is real, what else do I need to care about?

Example:

```text
                     CHANGE
                       │
             Manufacturing Config
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   Requirement       Design          Risk
      R-104           D-21           R-17
        │              │              │
        ↓              ↓              ↓
 Validation         Procedure       Review
   Test T-22          SOP-08         R-31
```

## 13.1 Interaction

Users should be able to:

- select a node
- inspect why it is connected
- see supporting evidence
- distinguish direct vs inferred relationships where applicable
- trace downstream impact
- return to the source finding

Do not create visually impressive graph edges without supporting data.

---

# 14. Impact Before Action

AegisX should go beyond showing a static blast radius.

Where supported by the actual implementation, show the effect of a proposed action.

Example:

```text
CURRENT STATE

7 affected items

        ↓

PROPOSED ACTION

Update validation procedure
Re-run validation test
Review requirement

        ↓

PROJECTED STATE

2 items remain for human review
```

This gives the user an intuitive understanding of why an action matters.

Do not present projections as facts.

Clearly label them as proposed/projected outcomes when appropriate.

---

# 15. Remediation and Actions

AegisX should recommend actions, not silently execute consequential changes.

Example:

```text
RECOMMENDED ACTION

Review validation procedure
and re-run Validation Test T-22.

Reason:
The changed configuration is referenced
by the validation evidence.

[ Review Evidence ]

[ Request Approval ]
```

The user should understand:

- what action is proposed
- why it is proposed
- what evidence supports it
- what could be affected
- whether approval is required

---

# 16. Human Approval

Actions requiring human authority must visibly remain under human control.

Example:

```text
ACTION REQUIRES APPROVAL

Update Validation Procedure

Reason
...

Evidence
...

Impact
...

[ Approve ]
[ Reject ]
```

Do not make approval look like a decorative confirmation dialog.

It is a meaningful governance step.

---

# 17. Audit Trail

The audit interface should show a chronological record of meaningful events.

Example:

```text
10:42  Document uploaded
10:43  Document indexed
10:45  Investigation started
10:45  Evidence retrieved
10:46  Finding generated
10:47  Action proposed
10:49  Approval requested
10:51  Action approved
```

The audit trail should make the investigation reconstructable.

---

# 18. Explainability

The UI must explain the system without pretending to expose hidden model reasoning.

Do not display fabricated "chain of thought".

Instead expose observable evidence and system decisions:

- question received
- retrieval performed
- sources selected
- evidence used
- relationships identified
- conclusion produced
- uncertainty
- recommended action

Use language such as:

**Evidence used**

**Why this item is affected**

**How this relationship was established**

**What remains uncertain**

Do not label generated speculation as verified evidence.

---

# 19. Confidence and Uncertainty

Confidence indicators should be meaningful.

Avoid arbitrary percentages such as:

> 97% confidence

unless they correspond to an actual defined measure.

Prefer:

- High evidence support
- Moderate evidence support
- Limited evidence
- Insufficient evidence

Where uncertainty exists, make it visible.

AegisX should prefer:

> Insufficient evidence to determine impact.

over a confident unsupported conclusion.

---

# 20. Loading, Empty, and Error States

Every major feature must have proper states.

## Loading

Explain what is happening.

Bad:

```text
Loading...
```

Better:

```text
Retrieving relevant evidence...
```

## Empty

Explain what the user should do.

Example:

```text
No knowledge sources yet.

Upload your GxP documents to begin an investigation.

[ Add Knowledge ]
```

## Error

Explain:

- what failed
- whether anything was changed
- what the user can do next

Do not expose raw stack traces in the normal UI.

---

# 21. Guided Demo / Product Tour

The application should include a guided experience that teaches the product progressively.

Recommended sequence:

### Step 1
Add knowledge.

### Step 2
Ask AegisX a question.

### Step 3
Watch the investigation execute.

### Step 4
Inspect retrieved evidence.

### Step 5
Inspect the grounded answer.

### Step 6
Open the Blast Radius.

### Step 7
Inspect the proposed action.

### Step 8
Review approval and audit information.

The tour should demonstrate the real product.

Do not use the tour to hide missing functionality.

---

# 22. Animation

Animation must communicate state or causality.

Good uses:

- retrieval progressing
- graph relationships appearing when established
- investigation timeline updating
- panel transitions
- approval state changing

Bad uses:

- constant floating elements
- excessive particle effects
- decorative glowing borders
- animations unrelated to system state
- fake processing animations

When in doubt, remove the animation.

---

# 23. Color Semantics

Colors must communicate meaning consistently.

Suggested semantic categories:

- neutral - information
- positive - verified/healthy/complete
- warning - needs attention
- critical - risk/problem
- pending - waiting for action
- inferred - system interpretation rather than direct evidence

Do not use color merely for decoration.

Never rely on color alone to communicate state.

---

# 24. Typography

Typography should prioritize readability and hierarchy.

Use a restrained type scale.

Hierarchy should clearly distinguish:

1. application/product
2. page
3. investigation
4. finding
5. evidence
6. metadata

Avoid enormous hero headings inside application workflows.

The product is information-heavy. Typography should support scanning.

---

# 25. Components

Build a small, consistent design system rather than creating one-off components for every page.

Important reusable components:

- App shell
- Navigation
- Evidence card
- Source citation
- Investigation timeline
- Retrieval trace
- Finding panel
- Impact graph
- Action panel
- Approval panel
- Status badge
- Metadata row
- Empty state
- Error state
- Loading state
- Guided-tour overlay

Components should support consistent spacing and behavior.

---

# 26. Responsiveness

The primary demo target is desktop.

The interface should still behave sensibly on smaller screens.

Do not optimize mobile at the expense of the desktop investigation experience.

---

# 27. Accessibility

The interface should support:

- keyboard navigation
- visible focus
- readable contrast
- meaningful labels
- semantic structure
- non-color state indicators
- accessible graph interactions where possible

---

# 28. Demo Mode

The demo may use a controlled dataset to guarantee a compelling story.

However:

**Demo mode must use the same product surfaces as the real workflow.**

Do not create a separate fake frontend that bypasses the actual system.

The ideal demo should be capable of showing:

```text
1. Upload known documents
2. Process them
3. Ask the Copilot
4. Retrieve evidence
5. Rerank evidence
6. Generate grounded response
7. Inspect sources
8. Open Blast Radius
9. Review recommended action
10. Show human approval
11. Show audit trail
```

---

# 29. What Must NOT Be Added Right Now

Do not expand:

- Supplier Intelligence
- extra analytics
- unnecessary dashboard metrics
- unnecessary agents
- unnecessary pages
- decorative AI features
- features that do not strengthen the evidence loop

New features require explicit justification against the core workflow.

---

# 30. Priority Levels

## P0 - Must Work

- Document upload
- Document ingestion
- Structured processing
- Knowledge indexing
- Advanced retrieval
- Hybrid retrieval
- Reranking
- Evidence provenance
- Copilot
- Grounded answers
- Evidence inspection
- Investigation trace
- Blast Radius based on real relationships

## P1 - Must Feel Excellent

- Information architecture
- Copilot UX
- Investigation timeline
- Evidence interactions
- Explainability
- Action review
- Human approval UX
- Audit trail
- Guided demo

## P2 - Polish

- animation
- micro-interactions
- visual refinement
- transitions
- final demo polish

## P3 - New Features

Only after P0 and P1 are genuinely working.

---

# 31. Definition of a Good AegisX Screen

Before adding a screen, ask:

1. What user decision does this screen support?
2. What real data does it display?
3. What action can the user take?
4. How does it connect to the investigation?
5. Does it help explain AegisX?
6. Could this information live inside an existing workflow instead?

If the screen cannot answer these questions, do not build it.

---

# 32. Definition of a Successful AegisX Demo

The judge should be able to understand this story without a long technical explanation:

> AegisX receives the organization's knowledge, investigates a question using that knowledge, shows the evidence behind its answer, traces what the finding affects, recommends what should happen next, keeps consequential actions under human control, and records what happened.

The visual experience should reinforce that story from beginning to end.

---

# 33. Final Frontend Rule

**Do not optimize for how many features AegisX can display.**

Optimize for:

> **How convincingly can AegisX demonstrate one trustworthy evidence-to-decision workflow?**

The core experience must feel real.

The evidence must be real.

The retrieval must be real.

The Copilot must be real.

The impact graph must be grounded in actual relationships.

The UI should make all of this understandable without overwhelming the user.

**Build the real evidence loop first. Then make it beautiful.**
