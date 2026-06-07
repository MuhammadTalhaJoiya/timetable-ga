# Product

## Register

product

## Users

University admin staff — scheduling coordinators responsible for building semester timetables across courses, teachers, rooms, and time slots. They are non-technical but detail-oriented; they understand constraints (teacher clashes, room capacity) but don't care about genetic algorithms. They use the tool under deadline pressure to produce a conflict-free schedule and export it for distribution.

## Product Purpose

An automated university timetable scheduler powered by a Genetic Algorithm. The tool ingests courses, teachers, rooms, and timeslots; evolves a conflict-free assignment over 100 generations; and presents the result as a sortable weekly schedule with a CSV export. Success means zero conflicts and a schedule a coordinator can hand off immediately.

## Brand Personality

Smart, precise, efficient. The tool should feel capable and trustworthy — like a well-engineered internal system that does its job without drama. Quiet confidence: the GA complexity is invisible; the schedule is front and center.

## References

Notion / Airtable — clean whitespace, table-first layouts, accessible to non-technical users without feeling dumbed down. The data is always the hero; the UI recedes.

## Anti-references

- Generic SaaS / Bootstrap defaults — blue primary buttons, identical card grids, looks like every other admin panel built in an afternoon
- Heavy enterprise bloat — SAP / Oracle density, grey everywhere, legacy-feeling forms
- Overly playful / consumer app — big illustrations, pastel colors, onboarding tooltips, feels like a mobile game
- Academic / university PDF aesthetic — Times New Roman, clip art, 2005 university portal vibes

## Design Principles

1. **Data first, chrome last.** The schedule is the product. Every element that isn't data or a direct action on data is overhead — reduce it.
2. **Institutional confidence.** Feels like it belongs in a university admin suite. Structured, authoritative, precise — not a startup landing page.
3. **Complexity hidden, clarity exposed.** The GA runs under the hood; the coordinator sees conflict counts and a clean table, nothing more. Fitness scores and generation numbers are secondary detail.
4. **Trust through legibility.** Conflict status must be immediately readable — color, label, and number must agree. No ambiguity about what the algorithm produced.
5. **Progressive density.** The home page is an overview; the result page is detail. Density increases with intent, never by default.

## Accessibility & Inclusion

WCAG 2.1 AA. All text must meet minimum contrast ratios (4.5:1 body, 3:1 large text). Interactive controls need visible focus states. Tables must have proper headers for screen reader navigation.
