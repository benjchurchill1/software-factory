# <PROJECT> design system

Source of truth for how <PROJECT> looks. The approved screens are at
<MOCKUPS_PATH>. Approved by <OWNER> on <APPROVAL_DATE>: "<OWNER_WORDS>".

## Brief

Who uses it: <USERS_AND_SETTING: who, on what device, where>

Character: <CHARACTER: one sentence>

It must not look like: <NOT_LIKE: what to avoid, and any product it must look distinct from>

Visual direction set by: <DIRECTION_OWNER: the owner, or the delegate and the owner's words>

## Tokens

These are the only values allowed. A literal colour, size, radius or shadow
appears only where a token is declared.

```css
<TOKENS: ground and surfaces, ink (text), brand, status ink and tint pairs, reserved colour, focus, radii, shadows, fonts, spacing, motion>
```

Dark mode: <DARK_MODE: in scope, or out of scope for this release and replaced by light only>

## Type

| Role | Size / weight / line height |
| --- | --- |
<TYPE_SCALE: page title, section title, body, small, the product's most important text>

Body text is never smaller than <MIN_TEXT_SIZE>.

## Layout

<LAYOUT: shell, content width, gutters, card treatment, how the aside wraps, what happens at the narrow width>

## Components

Each exists once as a shared component and every screen uses it.

<COMPONENTS: buttons, status chips (glyph and colour), card, list row, form field, the signature component>

## Rules

1. Colour is for meaning. <NEUTRAL_SHARE> of a screen is neutral.
2. <RESERVED_RULE: the one reserved colour and the one act it marks, or "none">
3. Every value comes from a token. A literal outside the token block fails the build.
4. Contrast is checked for every text-on-ground pair, including hover and status tints.
5. Motion: <MOTION_RULE>, gated on `prefers-reduced-motion: no-preference`.
6. Plain words on every screen.

## Key screens

| Screen | Widths | Mockup | Fixture state |
| --- | --- | --- | --- |
<KEY_SCREENS: four to six, each with its mockup link and the fixture state it shows>

## Register rows

Added to <REGISTER_PATH> before the freeze (or, on a build in flight, as new
rows through <RULING_POLICY_PATH>):

<DESIGN_ROWS: DSN-01 to DSN-05 from references/design-definition.md, adapted>
