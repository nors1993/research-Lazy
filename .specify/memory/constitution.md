# SpecKit Constitution

## Core Principles

### I. Code Quality (NON-NEGOTIABLE)

All code MUST adhere to the following quality standards:
- **Type Safety**: TypeScript/JavaScript projects MUST enable strict mode; Python projects MUST use type hints. Type suppression (`as any`, `@ts-ignore`) is FORBIDDEN.
- **Static Analysis**: Code MUST pass linting (ESLint, Pylint) with zero warnings before merge. Pre-commit hooks MUST enforce this.
- **Error Handling**: All functions MUST handle errors explicitly. Empty catch blocks (`catch(e) {}`) are FORBIDDEN.
- **Documentation**: Public APIs MUST have documentation. Complex logic requires inline comments explaining the "why", not the "what".
- **Single Responsibility**: Functions and modules MUST do one thing. Functions exceeding 50 lines SHOULD be refactored.

**Rationale**: Technical debt compounds. Enforcing quality gates prevents accumulation of unmaintainable code.

### II. Testing Standards (NON-NEGOTIABLE)

Testing is not optional—it is a core part of implementation:
- **Test-First Development**: Tests MUST be written BEFORE implementation. Red-Green-Refactor cycle is MANDATORY.
- **Coverage Thresholds**: Unit tests MUST achieve 80% line coverage; critical paths MUST be 100%.
- **Test Independence**: Each test MUST be independently runnable. Shared state between tests is FORBIDDEN.
- **Integration Tests**: Required for: library contracts, inter-service communication, shared schemas, and data persistence.
- **Test Naming**: Tests MUST follow `{method}_{scenario}_{expected}` convention. Vague names like "test1" are FORBIDDEN.

**Rationale**: Tests are the safety net that enables refactoring and prevents regressions. Poor tests provide false confidence.

### III. User Experience Consistency

Consistent UX builds trust and reduces cognitive load:
- **Design System Compliance**: All UI components MUST follow established design tokens (colors, spacing, typography, motion).
- **Interaction Patterns**: Similar actions MUST have similar interactions. Users MUST NOT learn different patterns for equivalent tasks.
- **Accessibility**: All interactive elements MUST be keyboard navigable; WCAG 2.1 AA compliance is REQUIRED.
- **Error Messaging**: Error messages MUST be human-readable, actionable, and consistent in tone across the application.
- **Responsive Behavior**: Layouts MUST adapt gracefully to viewport changes. Breakpoints MUST be defined and tested.

**Rationale**: Inconsistent UX creates friction, increases support load, and signals professional immaturity.

### IV. Performance Requirements

Performance is a feature—deadlines must be met:
- **Response Time**: API endpoints MUST respond within 200ms p95 for typical operations; heavy operations MUST complete within 5s p95.
- **Memory Efficiency**: Applications MUST not exceed 200MB baseline memory usage; streaming MUST be used for large data processing.
- **Bundle Size**: Frontend bundles MUST be code-split; initial load MUST be under 500KB gzipped.
- **Database Queries**: N+1 queries are FORBIDDEN. All queries MUST use appropriate indexing.
- **Caching Strategy**: Expensive operations MUST be cached with appropriate invalidation. Cache hit rates SHOULD exceed 80% for repeated operations.

**Rationale**: Users abandon slow applications. Performance requirements prevent technical debt from degrading user experience.

### V. Observability & Debugging

Systems must be debuggable in production:
- **Structured Logging**: All operations MUST log with appropriate levels (DEBUG, INFO, WARN, ERROR). Structured JSON logging REQUIRED for production.
- **Tracing**: Distributed tracing REQUIRED for multi-service architectures. Correlation IDs MUST propagate across boundaries.
- **Metrics**: Key metrics (request rate, error rate, latency percentiles) MUST be exposed. Dashboards MUST be auto-generated.
- **Alerting**: Alert thresholds MUST be defined for critical failures. Alert fatigue MUST be avoided through appropriate thresholds.

**Rationale**: Production issues are inevitable. Observability determines how quickly they can be diagnosed and resolved.

## Quality Standards

### Code Review Gates

All changes MUST pass through these gates before merge:
1. **Lint + Type Check**: Zero warnings/errors
2. **Unit Tests**: 80%+ coverage, all passing
3. **Integration Tests**: All passing (if applicable)
4. **Code Review**: At least one approval from a reviewer with relevant domain knowledge
5. **CI Pipeline**: All stages passing

### Technical Debt Management

- Technical debt MUST be tracked in the project backlog with explicit "tech debt" labels
- Debt that blocks feature development MUST be prioritized for immediate resolution
- Debt exceeding 2 sprints of effort requires explicit approval before being deferred

## Development Workflow

### Task Implementation Requirements

- Tasks MUST be implemented in the order defined in tasks.md
- Each task MUST include corresponding tests (unless explicitly marked optional)
- Commit messages MUST follow conventional commits format: `type(scope): description`
- PRs MUST reference the originating task ID

### Verification Checklist

Before marking any task complete:
- [ ] Code passes `lsp_diagnostics` with zero errors
- [ ] All tests pass (unit + integration)
- [ ] Code follows established patterns in the codebase
- [ ] Documentation updated if API surface changed
- [ ] No hardcoded secrets or credentials

## Governance

### Amendment Procedure

1. Proposed changes MUST be documented with rationale
2. Changes affecting core principles require unanimous approval
3. Changes to quality standards require majority approval
4. All amendments MUST update the version number following semantic versioning

### Versioning Policy

- **MAJOR**: Backward incompatible governance/principle removals or redefinitions
- **MINOR**: New principle/section added or materially expanded guidance
- **PATCH**: Clarifications, wording, typo fixes, non-semantic refinements

### Compliance Verification

- All PRs MUST verify compliance with applicable principles
- Complex implementations MUST document how they satisfy performance requirements
- Deviations from principles require explicit justification in the PR

**Version**: 1.0.0 | **Ratified**: 2026-05-07 | **Last Amended**: 2026-05-07