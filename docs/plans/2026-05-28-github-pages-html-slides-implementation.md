# GitHub Pages HTML Slides Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a static HTML slide deck for GitHub Pages deployment.

**Architecture:** Implement `docs/index.html` as a self-contained page. Use semantic slide sections, inline CSS variables, inline SVG/HTML diagrams, a small canvas grid animation, and vanilla JavaScript for navigation.

**Tech Stack:** HTML, CSS, SVG, Canvas, vanilla JavaScript.

---

### Task 1: Create The Static Deck

**Files:**
- Create: `docs/index.html`

**Steps:**
1. Add a responsive 16:9 deck shell with keyboard, button, wheel, and touch navigation.
2. Add 12 slides covering product story, architecture, tools, live gates, Odoo flow, Telegram card intake, commands, verification, and judging takeaway.
3. Include documentation-grade code blocks for `make` targets, Odoo upgrade, OpenClaw setup, live gateway, and tests.
4. Keep all CSS and JavaScript inline so GitHub Pages does not need a build step.

### Task 2: Verify Static Quality

**Files:**
- Validate: `docs/index.html`

**Steps:**
1. Run a static scan to ensure no local absolute paths or secret-looking values are embedded.
2. Run `git diff --check`.
3. Optionally open `docs/index.html` directly in a browser.
