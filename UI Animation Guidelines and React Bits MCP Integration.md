# UI Animation Guidelines and React Bits MCP Integration

## Purpose

Enhance the website experience using professional UI animations and interactive components without compromising usability, clarity, or product credibility.

Animations should improve the user experience, not distract from the product.

The priority order is:

1. Professional design
2. Clear user experience
3. Performance
4. Visual polish
5. Animation

---

# React Bits MCP Integration

Use the React Bits MCP server to access high-quality React animation components and UI effects.

Initialize the MCP server:

```bash
npx shadcn@latest mcp init --client claude
```

The MCP server can be used to discover and integrate suitable React Bits components into the project.

Use React Bits selectively for:

- Smooth page transitions
- Micro-interactions
- Loading states
- Highlighting important sections
- Improving visual hierarchy
- Making the guided tour experience more engaging

---

# Animation Philosophy

## Rule: Professional First

Animations should make the product feel:

- Modern
- Polished
- Reliable
- Production-ready

Avoid animations that make the website feel:

- Like an AI-generated template
- Like a portfolio gimmick
- Overly flashy
- Distracting

The goal is a product experience, not a showcase of animations.

---

# Acceptable Animation Examples

## 1. Subtle Entry Animations

Use:

- Fade-in
- Slight slide-up
- Smooth section reveal

Example:

A dashboard section appearing smoothly when entering the page.

---

## 2. Micro-interactions

Use:

- Button hover states
- Smooth transitions
- Card elevation changes
- Loading indicators

Example:

A button gently changes state when hovered.

---

## 3. Guided Tour Enhancements

Animations can improve the judge demo experience:

- Highlight important components
- Smoothly move focus between sections
- Animate workflow progression

Example:

```text
Input
  ↓
Processing
  ↓
AI Pipeline
  ↓
Output
```

Each stage can appear sequentially.

---

# Avoid

Do not use:

- Excessive floating elements
- Random background animations
- Unnecessary particles
- Overuse of gradients
- Animations everywhere
- Components that do not serve a purpose

Avoid the "AI startup landing page" look where everything moves but nothing communicates.

---

# Component Selection Criteria

Before adding any React Bits component, ask:

## Does this improve understanding?

If yes:
- Consider adding it.

If no:
- Do not add it.

---

## Does this improve the demo?

For judge-facing features:

Priority components:

1. Guided tour interactions
2. Feature demonstrations
3. Workflow visualization
4. Loading/progress states
5. Important result highlighting

---

# Design Consistency

All animations must follow:

- Existing color system
- Existing typography
- Existing spacing rules
- Existing component style

Do not introduce random design patterns.

The website should feel like one coherent product.

---

# Final Principle

Animations are a supporting layer.

The product should still look professional with animations disabled.

The goal is:

> "A well-engineered product with thoughtful interactions."

Not:

> "A website showing off animations."